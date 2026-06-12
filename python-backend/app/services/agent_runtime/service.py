"""AgentRuntimeService — high-level agent execution service.

Wraps the LangGraph compiled graph and provides operation management,
streaming, and human-in-the-loop support.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator, Optional

from langgraph.types import Command

from app.config import settings
from app.services.abort_signal import AbortError, AbortSignal, throw_if_aborted
from app.services.agent_runtime.checkpointer import get_compiled_graph
from app.services.agent_runtime.langfuse import create_langfuse_handler
from app.services.agent_runtime.state import AgentState
from app.services.agent_runtime_hooks import HookDispatcher, hook_dispatcher
from app.services.agent_runtime_types import (
    StepCompletionReason,
    StepLifecycleCallbacks,
    StepPresentationData,
)
from app.services.content_policy import ContentPolicyViolationError as _ContentPolicyViolationError

logger = logging.getLogger(__name__)

# In-memory operation registry (maps operation_id → metadata)
_operations: dict[str, dict[str, Any]] = {}
# In-memory event buffers for SSE streaming
_event_buffers: dict[str, asyncio.Queue] = {}

# TTL for stale operations (seconds) — auto-evict after this period
_OPERATION_TTL_SECONDS = 3600  # 1 hour


def _evict_stale_operations() -> int:
    """Remove operations older than _OPERATION_TTL_SECONDS. Returns count evicted."""
    now = time.time()
    stale_ids = [
        op_id for op_id, op in _operations.items()
        if (now - op.get("created_at", now)) > _OPERATION_TTL_SECONDS
        and op.get("status") in ("done", "error", "interrupted", None)
    ]
    for op_id in stale_ids:
        _operations.pop(op_id, None)
        _event_buffers.pop(op_id, None)
    return len(stale_ids)


class AgentRuntimeService:
    """High-level agent execution service.

    Wraps the LangGraph compiled graph and provides
    operation management, streaming, and human-in-the-loop support.
    """

    async def create_operation(
        self,
        user_id: str,
        messages: list[dict[str, Any]],
        *,
        model: str = "openai/gpt-4o",
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        kb_ids: Optional[list[str]] = None,
        enable_memory: bool = True,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        require_human_approval: Optional[bool] = None,
        max_steps: Optional[int] = None,
        # --- New parameters ---
        hooks: Optional[list[Any]] = None,
        signal: Optional[AbortSignal] = None,
        compression_enabled: bool = False,
        compression_max_tokens: int = 100_000,
        fallback_models: Optional[list[str]] = None,
        lifecycle_callbacks: Optional[StepLifecycleCallbacks] = None,
    ) -> dict[str, Any]:
        """Create a new agent operation (does NOT start execution).

        Returns ``{"operation_id": "...", "status": "idle"}``.
        """
        # Check abort before any work
        throw_if_aborted(signal, "Aborted before operation creation")

        # Evict stale operations to prevent unbounded memory growth
        evicted = _evict_stale_operations()
        if evicted:
            logger.debug("Evicted %d stale operations", evicted)

        operation_id = str(uuid.uuid4())

        # Prepend system prompt if provided
        final_messages = list(messages)
        if system_prompt:
            final_messages.insert(0, {"role": "system", "content": system_prompt})

        initial_state: AgentState = {
            "messages": final_messages,
            "status": "idle",
            "step_count": 0,
            "max_steps": max_steps or settings.agent_max_steps,
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "error": None,
            "metadata": {
                "operation_id": operation_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "created_at": time.time(),
            },
            "model": model,
            "api_key": api_key,
            "api_base": api_base,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "system_prompt": system_prompt,
            "kb_ids": kb_ids,
            "enable_memory": enable_memory,
            "require_human_approval": (
                require_human_approval
                if require_human_approval is not None
                else settings.agent_require_human_approval
            ),
            "user_id": user_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "pending_tool_calls": None,
            "human_decision": None,
            # New fields
            "cost": {"total": 0.0},
            "compression_enabled": compression_enabled,
            "compression_max_tokens": compression_max_tokens,
            "fallback_models": fallback_models,
        }

        # Register hooks
        hooks_registered = False
        if hooks:
            hook_dispatcher.register(operation_id, hooks)
            hooks_registered = True
            # Store serialized webhook hooks in state for production mode
            serialized = hook_dispatcher.get_serialized_hooks(operation_id)
            if serialized:
                initial_state["_hooks"] = [h.to_dict() for h in serialized]

        _operations[operation_id] = {
            "initial_state": initial_state,
            "status": "idle",
            "user_id": user_id,
            "created_at": time.time(),
            "abort_signal": signal,
            "lifecycle_callbacks": lifecycle_callbacks,
        }

        _event_buffers[operation_id] = asyncio.Queue()

        logger.info("[%s] Operation created (model=%s, tools=%d, hooks=%d, compression=%s)",
                     operation_id, model, len(tools or []),
                     len(hooks or []), compression_enabled)

        return {"operation_id": operation_id, "status": "idle"}

    async def run_operation(
        self,
        operation_id: str,
        *,
        resume_value: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute (or resume) an agent operation to completion.

        Enhanced with:
        - Abort signal injection into graph state
        - beforeStep / afterStep lifecycle hook dispatch
        - onComplete / onError hooks on termination
        - Structured StepPresentationData in afterStep events

        Returns the final state dict.
        """
        op = _operations.get(operation_id)
        if not op:
            raise ValueError(f"Operation {operation_id} not found")

        # Abort check before starting
        abort_signal: Optional[AbortSignal] = op.get("abort_signal")
        if abort_signal:
            abort_signal.throw_if_aborted("Aborted before run_operation")

        graph = await get_compiled_graph()
        config = {
            "configurable": {"thread_id": operation_id},
        }

        # Langfuse callback
        callbacks = []
        langfuse_handler = create_langfuse_handler(
            operation_id,
            op["user_id"],
            op.get("initial_state", {}).get("metadata"),
        )
        if langfuse_handler:
            callbacks.append(langfuse_handler)
        if callbacks:
            config["callbacks"] = callbacks

        event_q = _event_buffers.get(operation_id)
        lifecycle_cbs: Optional[StepLifecycleCallbacks] = op.get("lifecycle_callbacks")

        try:
            op["status"] = "running"
            if event_q:
                await event_q.put({"type": "operation_start", "operation_id": operation_id})

            # Inject abort signal into initial state
            initial_state = op.get("initial_state", {})
            if abort_signal:
                initial_state["_abort_signal"] = abort_signal

            # --- beforeStep hook ---
            step_index = initial_state.get("step_count", 0)
            await self._dispatch_before_step(operation_id, step_index, initial_state)

            start_at = time.time()

            if resume_value is not None:
                # Resume from interrupt (human-in-the-loop)
                result = await graph.ainvoke(
                    Command(resume=resume_value),
                    config=config,
                )
            else:
                # Fresh run
                result = await graph.ainvoke(
                    initial_state,
                    config=config,
                )

            elapsed_ms = (time.time() - start_at) * 1000

            # Determine final status
            final_status = result.get("status", "done")
            if result.get("error"):
                final_status = "error"
            elif final_status == "running":
                final_status = "done"

            result["status"] = final_status
            op["status"] = final_status

            # --- afterStep hook with structured presentation data ---
            await self._dispatch_after_step(
                operation_id, step_index, result, elapsed_ms,
            )

            if event_q:
                await event_q.put({
                    "type": "operation_complete",
                    "operation_id": operation_id,
                    "status": final_status,
                    "usage": result.get("usage"),
                    "cost": result.get("cost"),
                    "step_count": result.get("step_count", 0),
                })

            # --- onComplete hook ---
            completion_reason = self._determine_completion_reason(result)
            await self._dispatch_completion_hooks(
                operation_id, result, completion_reason,
            )

            # Lifecycle callback
            if lifecycle_cbs and lifecycle_cbs.on_complete:
                try:
                    await lifecycle_cbs.on_complete(result)
                except Exception:
                    pass

            # Flush Langfuse
            if langfuse_handler:
                try:
                    langfuse_handler.flush()
                except Exception:
                    pass

            logger.info("[%s] Operation completed: status=%s, steps=%d, cost=$%.4f",
                         operation_id, final_status, result.get("step_count", 0),
                         result.get("cost", {}).get("total", 0.0) if result.get("cost") else 0.0)

            return result

        except AbortError:
            op["status"] = "interrupted"
            # Cleanup hooks on abort
            hook_dispatcher.unregister(operation_id)

            if event_q:
                await event_q.put({
                    "type": "interrupted",
                    "operation_id": operation_id,
                    "reason": "aborted",
                })

            logger.info("[%s] Operation aborted", operation_id)
            raise

        except _ContentPolicyViolationError as exc:
            op["status"] = "error"
            violation = getattr(exc, "violation", None)
            error_info = {
                "type": "ContentPolicyViolation",
                "message": str(exc),
                "category": violation.category if violation else "unknown",
                "source": violation.source if violation else "unknown",
            }

            if event_q:
                await event_q.put({
                    "type": "content_policy_violation",
                    "operation_id": operation_id,
                    "error": error_info,
                })

            error_state = op.get("initial_state", {})
            error_state["status"] = "error"
            error_state["error"] = error_info
            await self._dispatch_completion_hooks(operation_id, error_state, "error")

            logger.warning("[%s] Content policy violation: %s", operation_id, exc)
            raise

        except Exception as exc:
            op["status"] = "error"
            error_info = {"type": type(exc).__name__, "message": str(exc)}

            if event_q:
                await event_q.put({
                    "type": "error",
                    "operation_id": operation_id,
                    "error": error_info,
                })

            # --- onError hook ---
            error_state = op.get("initial_state", {})
            error_state["status"] = "error"
            error_state["error"] = error_info
            await self._dispatch_completion_hooks(operation_id, error_state, "error")

            logger.error("[%s] Operation failed: %s", operation_id, exc, exc_info=True)
            raise

        finally:
            # Signal stream end
            if event_q:
                await event_q.put({"type": "stream_end"})
            # Always cleanup hook registrations
            hook_dispatcher.unregister(operation_id)

    async def stream_operation(
        self,
        operation_id: str,
        *,
        resume_value: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run operation and yield SSE-compatible events.

        Yields dicts like:
        - ``{"type": "step_start", "step": 0}``
        - ``{"type": "llm_content", "content": "...", "step": 0}``
        - ``{"type": "tool_call", "tool": "web_search", "args": {...}}``
        - ``{"type": "tool_result", "tool": "web_search", "content": "..."}``
        - ``{"type": "human_intervention", "pending_tool_calls": [...]}``
        - ``{"type": "operation_complete", "usage": {...}}``
        - ``{"type": "error", "error": {...}}``
        """
        op = _operations.get(operation_id)
        if not op:
            yield {"type": "error", "error": {"message": f"Operation {operation_id} not found"}}
            return

        graph = await get_compiled_graph()
        config = {
            "configurable": {"thread_id": operation_id},
        }

        # Langfuse
        callbacks = []
        langfuse_handler = create_langfuse_handler(
            operation_id,
            op["user_id"],
            op.get("initial_state", {}).get("metadata"),
        )
        if langfuse_handler:
            callbacks.append(langfuse_handler)
        if callbacks:
            config["callbacks"] = callbacks

        try:
            op["status"] = "running"

            if resume_value is not None:
                input_val = Command(resume=resume_value)
            else:
                input_val = op["initial_state"]

            prev_step = -1

            async for event in graph.astream_events(input_val, config=config, version="v2"):
                kind = event.get("event", "")
                data = event.get("data", {})
                name = event.get("name", "")

                # Step transitions
                if kind == "on_chain_start" and name in ("llm", "tools", "context", "human_review"):
                    step = data.get("input", {}).get("step_count", prev_step + 1) if isinstance(data.get("input"), dict) else prev_step + 1
                    prev_step = step
                    yield {"type": "step_start", "node": name, "step": step}

                # LLM token streaming
                elif kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {"type": "llm_content", "content": chunk.content}

                # Tool calls detected
                elif kind == "on_chain_end" and name == "llm":
                    output = data.get("output", {})
                    if isinstance(output, dict) and output.get("pending_tool_calls"):
                        yield {
                            "type": "tool_calls",
                            "tool_calls": output["pending_tool_calls"],
                        }

                # Human intervention
                elif kind == "on_chain_start" and name == "human_review":
                    pending = data.get("input", {}).get("pending_tool_calls") if isinstance(data.get("input"), dict) else None
                    if pending:
                        yield {
                            "type": "human_intervention",
                            "pending_tool_calls": pending,
                        }

                # Tool execution results
                elif kind == "on_chain_end" and name == "tools":
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        new_msgs = output.get("messages", [])
                        for msg in new_msgs:
                            if isinstance(msg, dict) and msg.get("role") == "tool":
                                yield {
                                    "type": "tool_result",
                                    "tool_call_id": msg.get("tool_call_id", ""),
                                    "content": msg.get("content", ""),
                                }

            # Get final state
            snapshot = await graph.aget_state(config)
            final_state = snapshot.values if snapshot else {}

            final_status = final_state.get("status", "done")
            if final_status == "running":
                # Check if interrupted (waiting for human)
                if snapshot and snapshot.next:
                    final_status = "waiting_for_human"
                else:
                    final_status = "done"

            op["status"] = final_status

            yield {
                "type": "operation_complete",
                "operation_id": operation_id,
                "status": final_status,
                "usage": final_state.get("usage"),
                "step_count": final_state.get("step_count", 0),
            }

        except Exception as exc:
            op["status"] = "error"
            yield {
                "type": "error",
                "operation_id": operation_id,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
            logger.error("[%s] Stream failed: %s", operation_id, exc, exc_info=True)

        finally:
            if langfuse_handler:
                try:
                    langfuse_handler.flush()
                except Exception:
                    pass

    async def get_status(self, operation_id: str) -> Optional[dict[str, Any]]:
        """Get current operation status from checkpointer."""
        op = _operations.get(operation_id)
        if not op:
            return None

        graph = await get_compiled_graph()
        config = {"configurable": {"thread_id": operation_id}}

        try:
            snapshot = await graph.aget_state(config)
            if not snapshot or not snapshot.values:
                return {
                    "operation_id": operation_id,
                    "status": op.get("status", "idle"),
                    "created_at": op.get("created_at"),
                }

            state = snapshot.values
            is_interrupted = bool(snapshot.next)

            return {
                "operation_id": operation_id,
                "status": "waiting_for_human" if is_interrupted else state.get("status", op.get("status")),
                "step_count": state.get("step_count", 0),
                "usage": state.get("usage"),
                "error": state.get("error"),
                "pending_tool_calls": state.get("pending_tool_calls") if is_interrupted else None,
                "is_active": state.get("status") in ("running", "idle"),
                "needs_human_input": is_interrupted,
                "created_at": op.get("created_at"),
                "message_count": len(state.get("messages", [])),
            }
        except Exception:
            return {
                "operation_id": operation_id,
                "status": op.get("status", "unknown"),
                "created_at": op.get("created_at"),
            }

    async def interrupt_operation(self, operation_id: str) -> bool:
        """Interrupt a running operation.

        Also triggers the abort signal so cooperative checks in graph nodes
        will raise AbortError at the next checkpoint.
        """
        op = _operations.get(operation_id)
        if not op:
            return False

        if op.get("status") in ("done", "error", "interrupted"):
            return False

        op["status"] = "interrupted"

        # Trigger abort signal for cooperative cancellation
        abort_signal: Optional[AbortSignal] = op.get("abort_signal")
        if abort_signal:
            abort_signal.abort("Operation interrupted by user")

        graph = await get_compiled_graph()
        config = {"configurable": {"thread_id": operation_id}}
        try:
            snapshot = await graph.aget_state(config)
            if snapshot and snapshot.values:
                await graph.aupdate_state(
                    config,
                    {"status": "interrupted"},
                )
        except Exception:
            logger.warning("[%s] Failed to update interrupted state", operation_id, exc_info=True)

        event_q = _event_buffers.get(operation_id)
        if event_q:
            await event_q.put({"type": "interrupted", "operation_id": operation_id})
            await event_q.put({"type": "stream_end"})

        logger.info("[%s] Operation interrupted", operation_id)
        return True

    async def resume_with_tool_result(
        self,
        operation_id: str,
        *,
        approved: bool = True,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resume an interrupted operation after human review.

        If ``approved=True``, the pending tools will be executed.
        If ``approved=False``, the rejection reason is sent back to the LLM.
        """
        resume_value = {"approved": approved}
        if reason:
            resume_value["reason"] = reason

        return await self.run_operation(operation_id, resume_value=resume_value)

    async def stream_resume(
        self,
        operation_id: str,
        *,
        approved: bool = True,
        reason: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Resume interrupted operation via streaming."""
        resume_value = {"approved": approved}
        if reason:
            resume_value["reason"] = reason

        async for event in self.stream_operation(operation_id, resume_value=resume_value):
            yield event

    def list_operations(self, user_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List all operations, optionally filtered by user_id."""
        results = []
        for op_id, op in _operations.items():
            if user_id and op.get("user_id") != user_id:
                continue
            results.append({
                "operation_id": op_id,
                "status": op.get("status", "unknown"),
                "user_id": op.get("user_id"),
                "created_at": op.get("created_at"),
            })
        return sorted(results, key=lambda x: x.get("created_at", 0), reverse=True)

    async def cleanup_operation(self, operation_id: str) -> bool:
        """Remove an operation from memory."""
        if operation_id in _operations:
            del _operations[operation_id]
        if operation_id in _event_buffers:
            del _event_buffers[operation_id]
        # Cleanup hooks
        hook_dispatcher.unregister(operation_id)
        return True

    # ------------------------------------------------------------------
    # Private lifecycle hook helpers
    # ------------------------------------------------------------------

    async def _dispatch_before_step(
        self,
        operation_id: str,
        step_index: int,
        state: dict[str, Any],
    ) -> None:
        """Dispatch ``beforeStep`` hooks. Errors are logged but never raised."""
        try:
            metadata = state.get("metadata", {})
            await hook_dispatcher.dispatch(
                operation_id,
                "beforeStep",
                {
                    "operationId": operation_id,
                    "agentId": metadata.get("agent_id", ""),
                    "userId": metadata.get("user_id", ""),
                    "stepIndex": step_index,
                    "steps": state.get("step_count", 0),
                },
                state.get("_hooks"),
            )
        except Exception as exc:
            logger.debug("[%s] beforeStep hook error: %s", operation_id, exc)

    async def _dispatch_after_step(
        self,
        operation_id: str,
        step_index: int,
        result: dict[str, Any],
        elapsed_ms: float,
    ) -> None:
        """Dispatch ``afterStep`` hooks with structured presentation data."""
        try:
            presentation = self._build_step_presentation_data(result, elapsed_ms)
            metadata = result.get("metadata", {})
            usage = result.get("usage", {})
            cost = result.get("cost", {})

            await hook_dispatcher.dispatch(
                operation_id,
                "afterStep",
                {
                    "operationId": operation_id,
                    "agentId": metadata.get("agent_id", ""),
                    "userId": metadata.get("user_id", ""),
                    "stepIndex": step_index,
                    "steps": result.get("step_count", 0),
                    "status": result.get("status"),
                    # Presentation data
                    "stepType": presentation.step_type,
                    "executionTimeMs": presentation.execution_time_ms,
                    "thinking": presentation.thinking,
                    "content": presentation.content,
                    "reasoning": presentation.reasoning,
                    "toolsCalling": presentation.tools_calling,
                    "toolsResult": presentation.tools_result,
                    # Step-level usage
                    "stepCost": presentation.step_cost,
                    "stepInputTokens": presentation.step_input_tokens,
                    "stepOutputTokens": presentation.step_output_tokens,
                    "stepTotalTokens": presentation.step_total_tokens,
                    # Cumulative totals
                    "totalCost": presentation.total_cost,
                    "totalInputTokens": presentation.total_input_tokens,
                    "totalOutputTokens": presentation.total_output_tokens,
                    "totalTokens": presentation.total_tokens,
                    "totalSteps": presentation.total_steps,
                },
                result.get("_hooks"),
            )
        except Exception as exc:
            logger.debug("[%s] afterStep hook error: %s", operation_id, exc)

    async def _dispatch_completion_hooks(
        self,
        operation_id: str,
        state: dict[str, Any],
        reason: str,
    ) -> None:
        """Dispatch ``onComplete`` (and ``onError``) hooks. Fire-and-forget."""
        try:
            metadata = state.get("metadata", {})
            usage = state.get("usage", {})
            cost = state.get("cost", {})

            event = {
                "operationId": operation_id,
                "agentId": metadata.get("agent_id", ""),
                "userId": metadata.get("user_id", ""),
                "reason": reason,
                "status": state.get("status", reason),
                "steps": state.get("step_count", 0),
                "totalTokens": usage.get("total_tokens", 0),
                "cost": cost.get("total", 0.0) if cost else 0.0,
                "errorDetail": state.get("error"),
            }

            await hook_dispatcher.dispatch(
                operation_id, "onComplete", event, state.get("_hooks"),
            )

            if reason == "error":
                await hook_dispatcher.dispatch(
                    operation_id, "onError", event, state.get("_hooks"),
                )
        except Exception as exc:
            logger.debug("[%s] Completion hook error: %s", operation_id, exc)

    @staticmethod
    def _determine_completion_reason(state: dict[str, Any]) -> StepCompletionReason:
        """Determine the completion reason from final state."""
        status = state.get("status")
        if status == "done":
            return "done"
        if status == "error":
            return "error"
        if status == "interrupted":
            return "interrupted"
        if status == "waiting_for_human":
            return "waiting_for_human"

        max_steps = state.get("max_steps", 25)
        step_count = state.get("step_count", 0)
        if max_steps and step_count >= max_steps:
            return "max_steps"

        cost = state.get("cost", {})
        cost_limit = state.get("metadata", {}).get("cost_limit")
        if cost_limit and cost and cost.get("total", 0) >= cost_limit:
            return "cost_limit"

        return "done"

    @staticmethod
    def _build_step_presentation_data(
        result: dict[str, Any],
        elapsed_ms: float,
    ) -> StepPresentationData:
        """Build structured StepPresentationData from a graph result."""
        usage = result.get("usage", {})
        cost = result.get("cost", {})
        messages = result.get("messages", [])

        # Find the last assistant message for content/reasoning
        content: Optional[str] = None
        reasoning: Optional[str] = None
        tools_calling: Optional[list[dict[str, Any]]] = None

        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content")
                reasoning = msg.get("reasoning")
                if msg.get("tool_calls"):
                    tools_calling = [
                        {
                            "identifier": tc.get("function", {}).get("name", ""),
                            "apiName": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", ""),
                        }
                        for tc in msg["tool_calls"]
                    ]
                break

        # Detect step type
        pending = result.get("pending_tool_calls")
        is_tool_phase = bool(pending) or bool(tools_calling)

        return StepPresentationData(
            step_type="call_tool" if is_tool_phase else "call_llm",
            execution_time_ms=elapsed_ms,
            thinking=not is_tool_phase,
            content=content,
            reasoning=reasoning,
            tools_calling=tools_calling,
            # Step-level cost from this run
            step_cost=cost.get("step") if cost else None,
            step_input_tokens=cost.get("step_input_tokens") if cost else None,
            step_output_tokens=cost.get("step_output_tokens") if cost else None,
            step_total_tokens=(
                (cost.get("step_input_tokens", 0) + cost.get("step_output_tokens", 0))
                if cost and cost.get("step_input_tokens") is not None
                else None
            ),
            # Cumulative totals
            total_cost=cost.get("total", 0.0) if cost else 0.0,
            total_input_tokens=usage.get("input_tokens", 0),
            total_output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            total_steps=result.get("step_count", 0),
        )


# Module-level singleton
agent_runtime = AgentRuntimeService()
