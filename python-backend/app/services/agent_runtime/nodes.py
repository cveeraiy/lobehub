"""LangGraph node functions for the agent runtime.

Contains: context_node, llm_node, human_review_node, tool_node
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from langgraph.types import interrupt

from app.services.abort_signal import AbortSignal
from app.services.agent_runtime.state import AgentState, UsageInfo
from app.services.agent_runtime_hooks import hook_dispatcher
from app.services.error_classification import classify_tool_error

logger = logging.getLogger(__name__)


async def context_node(state: AgentState) -> dict[str, Any]:
    """Inject RAG + memory context into messages (first step only).

    Also runs context compression if enabled and token count is high.
    """
    # Cooperative abort check
    signal = state.get("_abort_signal")
    if isinstance(signal, AbortSignal):
        signal.throw_if_aborted("Aborted before context injection")

    messages = state.get("messages", [])

    # Context compression on subsequent steps (when messages grow large)
    if state.get("step_count", 0) > 0:
        if state.get("compression_enabled", False):
            from app.services.context_compressor import compress_context
            compressed, was_compressed = await compress_context(
                messages,
                model=state.get("model", "openai/gpt-4o-mini"),
                api_key=state.get("api_key"),
                max_tokens=state.get("compression_max_tokens", 100_000),
            )
            if was_compressed:
                return {"messages": compressed}
        return {}

    from app.services import chat_service

    user_id = state.get("user_id", "")
    kb_ids = state.get("kb_ids")
    enable_memory = state.get("enable_memory", True)
    api_key = state.get("api_key")

    # build_context needs a DB session — we create a short-lived one
    from app.db import async_session_factory
    async with async_session_factory() as session:
        augmented = await chat_service.build_context(
            session, user_id, messages,
            kb_ids=kb_ids,
            enable_memory=enable_memory,
            api_key=api_key,
        )

    return {"messages": augmented}


async def llm_node(state: AgentState) -> dict[str, Any]:
    """Call LLM via litellm, return updated messages + usage + cost.

    Supports:
    - Cooperative abort check before the LLM call
    - Content policy enforcement (pre-LLM input + post-LLM output)
    - Multi-model fallback on retryable errors
    - Reasoning/thinking content extraction
    - Per-step and cumulative cost tracking
    """
    from app.services.content_policy import (
        ContentPolicyViolationError,
        check_content_post_llm,
        check_content_pre_llm,
        detect_policy_violation_error,
    )

    # Cooperative abort check
    signal = state.get("_abort_signal")
    if isinstance(signal, AbortSignal):
        signal.throw_if_aborted("Aborted before LLM call")

    messages = state.get("messages", [])
    model = state.get("model", "openai/gpt-4o")
    step_count = state.get("step_count", 0)
    op_id = state.get("metadata", {}).get("operation_id", "?")

    # --- Content policy: pre-LLM input check ---
    pre_violation = await check_content_pre_llm(messages)
    if pre_violation:
        logger.warning(
            "[%s] Content policy violation (pre-LLM): %s [%s]",
            op_id, pre_violation.category, pre_violation.source,
        )
        raise ContentPolicyViolationError(
            pre_violation.message, violation=pre_violation,
        )

    extra_kwargs: dict[str, Any] = {}
    if state.get("tools"):
        extra_kwargs["tools"] = state["tools"]

    start_time = time.time()

    # Use model fallback if configured; catch provider content policy errors
    try:
        fallback_models = state.get("fallback_models")
        if fallback_models:
            from app.services.model_fallback import chat_with_fallback
            response = await chat_with_fallback(
                messages,
                model=model,
                fallback_models=fallback_models,
                stream=False,
                temperature=state.get("temperature"),
                max_tokens=state.get("max_tokens"),
                api_key=state.get("api_key"),
                api_base=state.get("api_base"),
                extra_kwargs=extra_kwargs or None,
            )
        else:
            from app.services import llm_service
            response = await llm_service.chat(
                messages,
                model=model,
                stream=False,
                temperature=state.get("temperature"),
                max_tokens=state.get("max_tokens"),
                api_key=state.get("api_key"),
                api_base=state.get("api_base"),
                extra_kwargs=extra_kwargs or None,
            )
    except ContentPolicyViolationError:
        raise
    except Exception as exc:
        # Detect provider-side content policy errors and normalize
        policy_msg = detect_policy_violation_error(exc)
        if policy_msg:
            logger.warning("[%s] Provider content policy error: %s", op_id, exc)
            raise ContentPolicyViolationError(policy_msg)
        raise

    elapsed = time.time() - start_time

    choice = response.choices[0]
    assistant_msg = choice.message

    # Build assistant message dict
    new_msg: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_msg.content or None,
    }

    # Extract reasoning/thinking content (returned by some models)
    reasoning: Optional[str] = None
    if hasattr(assistant_msg, "reasoning_content") and assistant_msg.reasoning_content:
        reasoning = assistant_msg.reasoning_content
    elif hasattr(assistant_msg, "thinking") and assistant_msg.thinking:
        reasoning = assistant_msg.thinking

    if reasoning:
        new_msg["reasoning"] = reasoning

    if getattr(assistant_msg, "tool_calls", None):
        new_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in assistant_msg.tool_calls
        ]

    # --- Content policy: post-LLM output check ---
    output_text = assistant_msg.content or ""
    if output_text:
        post_violation = await check_content_post_llm(output_text)
        if post_violation:
            logger.warning(
                "[%s] Content policy violation (post-LLM output): %s [%s]",
                op_id, post_violation.category, post_violation.source,
            )
            raise ContentPolicyViolationError(
                post_violation.message, violation=post_violation,
            )

    # Accumulate usage
    prev_usage = state.get("usage", {})
    input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
    new_usage: UsageInfo = {
        "input_tokens": prev_usage.get("input_tokens", 0) + input_tokens,
        "output_tokens": prev_usage.get("output_tokens", 0) + output_tokens,
        "total_tokens": prev_usage.get("total_tokens", 0) + input_tokens + output_tokens,
    }

    # Cost tracking
    from app.services.agent_runtime_types import _estimate_cost
    step_cost = _estimate_cost(input_tokens, output_tokens, model)
    prev_cost = state.get("cost", {})
    new_cost = {
        "total": (prev_cost.get("total", 0.0) if prev_cost else 0.0) + step_cost,
        "step": step_cost,
        "step_input_tokens": input_tokens,
        "step_output_tokens": output_tokens,
    }

    updated_messages = list(messages) + [new_msg]

    total_tokens = new_usage["total_tokens"]
    total_cost = new_cost["total"]
    logger.info(
        "[%s] LLM step %d: %s, %d in / %d out tokens, $%.4f (total: %d tok / $%.4f), %.2fs",
        op_id, step_count, model,
        input_tokens, output_tokens, step_cost,
        total_tokens, total_cost, elapsed,
    )

    return {
        "messages": updated_messages,
        "usage": new_usage,
        "cost": new_cost,
        "step_count": step_count + 1,
        "status": "running",
        "pending_tool_calls": (
            new_msg.get("tool_calls") if new_msg.get("tool_calls") else None
        ),
    }


async def human_review_node(state: AgentState) -> dict[str, Any]:
    """Pause for human approval of pending tool calls.

    Uses LangGraph's ``interrupt()`` to suspend the graph. The router
    resumes with ``Command(resume={"approved": True/False, ...})``.
    """
    pending = state.get("pending_tool_calls")
    if not pending:
        return {"status": "running"}

    # Interrupt — execution pauses here until resumed
    decision = interrupt({
        "type": "tool_approval",
        "pending_tool_calls": pending,
        "message": "Agent wants to execute tool calls. Approve or reject.",
    })

    # After resume, decision is the value passed via Command(resume=...)
    if isinstance(decision, dict) and decision.get("approved") is False:
        # User rejected — add a message explaining rejection
        reason = decision.get("reason", "Tool call rejected by user.")
        rejection_msg: dict[str, Any] = {"role": "user", "content": reason}
        return {
            "messages": list(state.get("messages", [])) + [rejection_msg],
            "pending_tool_calls": None,
            "human_decision": decision,
            "status": "running",
        }

    # Approved (or auto-approved)
    return {
        "pending_tool_calls": state.get("pending_tool_calls"),
        "human_decision": {"approved": True},
        "status": "running",
    }


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Execute pending tool calls via the existing tool_execution service.

    Enhanced with:
    - Cooperative abort check before each tool call
    - beforeToolCall hook dispatch (supports mock)
    - Error classification (replan / retry / stop)
    - afterToolCall hook dispatch
    """
    from app.services.tool_execution import execute_tool_call_with_context
    from app.db import async_session_factory
    from app.services.agent_runtime_hooks.types import ToolCallHookEvent

    pending = state.get("pending_tool_calls")
    if not pending:
        return {"pending_tool_calls": None}

    messages = list(state.get("messages", []))
    user_id = state.get("user_id", "")
    op_id = state.get("metadata", {}).get("operation_id", "")
    step_count = state.get("step_count", 0)

    async with async_session_factory() as session:
        for tc in pending:
            # Cooperative abort check
            signal = state.get("_abort_signal")
            if isinstance(signal, AbortSignal):
                signal.throw_if_aborted("Aborted before tool execution")

            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})
            except json.JSONDecodeError:
                args = {}

            # beforeToolCall hook — supports mock
            tool_event = ToolCallHookEvent(
                operation_id=op_id,
                tool_name=fn_name,
                tool_args=args,
                identifier=fn_name,
                api_name=fn_name,
                step_index=step_count,
                agent_id=state.get("agent_id", ""),
                user_id=user_id,
            )
            mock_result = await hook_dispatcher.dispatch_before_tool_call(op_id, tool_event)

            if mock_result and mock_result.get("is_mocked"):
                # Hook mocked this tool call — skip execution
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": mock_result["content"],
                })
                logger.info("[%s] Tool %s mocked by hook", op_id, fn_name)
                continue

            start = time.time()
            tool_error: Optional[Exception] = None
            result: str = ""
            try:
                result = await execute_tool_call_with_context(
                    fn_name, args, session=session, user_id=user_id,
                )
            except Exception as exc:
                tool_error = exc
                # Classify the error
                classified = classify_tool_error(exc)
                logger.warning(
                    "[%s] Tool %s error (%s): %s",
                    op_id, fn_name, classified.kind, classified.message,
                )
                result = json.dumps({
                    "error": True,
                    "kind": classified.kind,
                    "message": classified.message,
                    "code": classified.code,
                })

            elapsed = time.time() - start

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result,
            })

            # afterToolCall hook
            try:
                await hook_dispatcher.dispatch(
                    op_id,
                    "afterToolCall",
                    {
                        "operation_id": op_id,
                        "tool_name": fn_name,
                        "tool_args": args,
                        "result": result[:2000],  # Truncate for webhook
                        "is_success": tool_error is None,
                        "execution_time_ms": elapsed * 1000,
                        "step_index": step_count,
                    },
                    state.get("_hooks"),
                )
            except Exception:
                pass  # Hook errors are non-fatal

            if tool_error:
                # toolCallError hook
                try:
                    await hook_dispatcher.dispatch(
                        op_id,
                        "toolCallError",
                        {
                            "operation_id": op_id,
                            "tool_name": fn_name,
                            "error": str(tool_error),
                            "kind": classify_tool_error(tool_error).kind,
                        },
                        state.get("_hooks"),
                    )
                except Exception:
                    pass

            logger.info(
                "[%s] Tool %s %s in %.2fs",
                op_id, fn_name,
                "failed" if tool_error else "executed",
                elapsed,
            )

    return {
        "messages": messages,
        "pending_tool_calls": None,
    }
