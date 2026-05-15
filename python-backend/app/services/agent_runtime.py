"""Agent Runtime — LangGraph-based step execution engine with Langfuse tracing.

Replaces the monolithic chat-loop with a proper agent orchestration layer:
- StateGraph with LLM / Tool / HumanReview nodes
- Postgres-backed checkpointer for operation persistence
- Langfuse callback handler for full execution tracing
- Operation lifecycle: create → run → (tool loop) → done/error/interrupted

Usage::

    from app.services.agent_runtime import AgentRuntimeService

    runtime = AgentRuntimeService()
    op = await runtime.create_operation(user_id, messages, model="openai/gpt-4o")
    async for event in runtime.stream_operation(op["operation_id"]):
        print(event)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, Literal, Optional, Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.config import settings
from app.services.abort_signal import AbortError, AbortSignal, is_abort_error, throw_if_aborted
from app.services.agent_runtime_hooks import HookDispatcher, hook_dispatcher
from app.services.agent_runtime_types import (
    CostInfo,
    StepCompletionReason,
    StepLifecycleCallbacks,
    StepPresentationData,
    UsageTracker,
)
from app.services.content_policy import ContentPolicyViolationError as _ContentPolicyViolationError
from app.services.error_classification import classify_tool_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

from typing import TypedDict


class UsageInfo(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_cost: float


class AgentState(TypedDict, total=False):
    """LangGraph agent state — persisted via checkpointer."""
    messages: list[dict[str, Any]]
    status: Literal["idle", "running", "waiting_for_human", "done", "error", "interrupted"]
    step_count: int
    max_steps: int
    usage: UsageInfo
    error: Optional[dict[str, Any]]
    metadata: dict[str, Any]
    # Human-in-the-loop
    pending_tool_calls: Optional[list[dict[str, Any]]]
    human_decision: Optional[dict[str, Any]]
    # Internal
    model: str
    api_key: Optional[str]
    api_base: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    tools: Optional[list[dict[str, Any]]]
    system_prompt: Optional[str]
    kb_ids: Optional[list[str]]
    enable_memory: bool
    require_human_approval: bool
    # DB context for tool execution
    user_id: str
    session_id: Optional[str]
    agent_id: Optional[str]
    # --- New: cost tracking ---
    cost: Optional[dict[str, float]]
    # --- New: context compression ---
    compression_enabled: bool
    compression_max_tokens: int
    # --- New: fallback models ---
    fallback_models: Optional[list[str]]
    # --- New: abort signal (not serialized — injected at runtime) ---
    _abort_signal: Optional[Any]
    # --- New: hook metadata for serialized hooks ---
    _hooks: Optional[list[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Langfuse integration
# ---------------------------------------------------------------------------

_langfuse_client = None


def _get_langfuse():
    """Lazy-init Langfuse client."""
    global _langfuse_client
    if _langfuse_client is None and settings.langfuse_enabled:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            logger.info("Langfuse tracing initialized (host=%s)", settings.langfuse_host)
        except Exception:
            logger.warning("Failed to initialize Langfuse", exc_info=True)
    return _langfuse_client


def _create_langfuse_handler(
    operation_id: str,
    user_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Any]:
    """Create a Langfuse callback handler for a single operation trace."""
    langfuse = _get_langfuse()
    if langfuse is None:
        return None
    try:
        from langfuse.callback import CallbackHandler
        return CallbackHandler(
            trace_name=f"agent-operation-{operation_id[:8]}",
            trace_id=operation_id,
            user_id=user_id,
            trace_metadata=metadata or {},
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        logger.warning("Failed to create Langfuse handler", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Message conversion helpers
# ---------------------------------------------------------------------------

def _dicts_to_lc_messages(messages: list[dict[str, Any]]) -> list[BaseMessage]:
    """Convert OpenAI-format message dicts to LangChain BaseMessage objects."""
    result: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            kwargs: dict[str, Any] = {"content": content or ""}
            if msg.get("tool_calls"):
                kwargs["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "args": json.loads(tc["function"]["arguments"])
                        if isinstance(tc.get("function", {}).get("arguments"), str)
                        else tc.get("function", {}).get("arguments", {}),
                    }
                    for tc in msg["tool_calls"]
                ]
            result.append(AIMessage(**kwargs))
        elif role == "tool":
            result.append(ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
            ))
        else:
            result.append(HumanMessage(content=content))
    return result


def _lc_message_to_dict(msg: BaseMessage) -> dict[str, Any]:
    """Convert a LangChain BaseMessage back to OpenAI-format dict."""
    if isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    elif isinstance(msg, AIMessage):
        d: dict[str, Any] = {"role": "assistant", "content": msg.content or None}
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.get("id", tc.get("name", "")),
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("args", {})),
                    },
                }
                for tc in msg.tool_calls
            ]
        return d
    elif isinstance(msg, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": msg.tool_call_id,
            "content": msg.content,
        }
    elif isinstance(msg, HumanMessage):
        return {"role": "user", "content": msg.content}
    return {"role": "user", "content": str(msg.content)}


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

def _route_after_llm(state: AgentState) -> str:
    """Decide where to go after LLM node."""
    # Check step limit
    if state.get("step_count", 0) >= state.get("max_steps", 25):
        return "finish"

    # Check for tool calls
    pending = state.get("pending_tool_calls")
    if not pending:
        return "finish"

    # Has tool calls — check if human approval required
    if state.get("require_human_approval", False):
        return "human_review"

    return "tools"


def _route_after_human_review(state: AgentState) -> str:
    """After human review, either execute tools or go back to LLM."""
    decision = state.get("human_decision", {})
    if isinstance(decision, dict) and decision.get("approved") is False:
        # Rejected — go back to LLM with rejection message
        return "llm"
    return "tools"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_agent_graph() -> StateGraph:
    """Build the LangGraph agent state graph.

    Flow::

        START → context → llm → (tools? / human_review? / finish)
                                   ↓           ↓
                                 tools  ← human_review
                                   ↓
                                  llm  (loop)
    """
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("context", context_node)
    graph.add_node("llm", llm_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("tools", tool_node)

    # Edges
    graph.add_edge(START, "context")
    graph.add_edge("context", "llm")

    graph.add_conditional_edges(
        "llm",
        _route_after_llm,
        {
            "finish": END,
            "tools": "tools",
            "human_review": "human_review",
        },
    )

    graph.add_conditional_edges(
        "human_review",
        _route_after_human_review,
        {
            "tools": "tools",
            "llm": "llm",
        },
    )

    graph.add_edge("tools", "llm")

    return graph


# ---------------------------------------------------------------------------
# Checkpointer
# ---------------------------------------------------------------------------

_checkpointer = None
_checkpointer_lock = asyncio.Lock()


async def _get_checkpointer():
    """Get or create the Postgres checkpointer (or MemorySaver fallback)."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    async with _checkpointer_lock:
        if _checkpointer is not None:
            return _checkpointer

        # Try Postgres checkpointer using the same DB
        try:
            # langgraph-checkpoint-postgres needs a raw psycopg connection string
            db_url = settings.database_url
            # Convert asyncpg URL to psycopg format for checkpointer
            pg_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            checkpointer = AsyncPostgresSaver.from_conn_string(pg_url)
            await checkpointer.setup()
            _checkpointer = checkpointer
            logger.info("LangGraph checkpointer: Postgres")
        except Exception:
            if not settings.debug:
                logger.error(
                    "Postgres checkpointer failed and debug=False; "
                    "MemorySaver is unsafe for production (state lost on restart)",
                    exc_info=True,
                )
                raise RuntimeError(
                    "Cannot start agent runtime: Postgres checkpointer unavailable. "
                    "Set DEBUG=true to allow in-memory fallback."
                )
            logger.warning("Postgres checkpointer failed, using MemorySaver (debug mode only)", exc_info=True)
            _checkpointer = MemorySaver()

        return _checkpointer


# ---------------------------------------------------------------------------
# Compiled graph singleton
# ---------------------------------------------------------------------------

_compiled_graph = None
_graph_lock = asyncio.Lock()


async def _get_compiled_graph():
    """Lazy-compile the agent graph with checkpointer."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    async with _graph_lock:
        if _compiled_graph is not None:
            return _compiled_graph

        checkpointer = await _get_checkpointer()
        graph = build_agent_graph()
        _compiled_graph = graph.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_review"],
        )
        logger.info("LangGraph agent graph compiled")
        return _compiled_graph


# ---------------------------------------------------------------------------
# AgentRuntimeService
# ---------------------------------------------------------------------------

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

        graph = await _get_compiled_graph()
        config = {
            "configurable": {"thread_id": operation_id},
        }

        # Langfuse callback
        callbacks = []
        langfuse_handler = _create_langfuse_handler(
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

        graph = await _get_compiled_graph()
        config = {
            "configurable": {"thread_id": operation_id},
        }

        # Langfuse
        callbacks = []
        langfuse_handler = _create_langfuse_handler(
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

        graph = await _get_compiled_graph()
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

        graph = await _get_compiled_graph()
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
