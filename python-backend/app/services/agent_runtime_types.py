"""Agent Runtime types — structured step events, lifecycle callbacks, operation params.

Mirrors TS ``agentRuntime/types.ts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Optional

# ---------------------------------------------------------------------------
# Step completion reason
# ---------------------------------------------------------------------------

StepCompletionReason = Literal[
    "done",
    "error",
    "interrupted",
    "max_steps",
    "cost_limit",
    "waiting_for_human",
]

# ---------------------------------------------------------------------------
# Step presentation data — enriched step result for hooks & webhooks
# ---------------------------------------------------------------------------

@dataclass
class StepPresentationData:
    """Structured data for a completed step, mirroring TS ``StepPresentationData``."""

    step_type: Literal["call_llm", "call_tool"]
    execution_time_ms: float
    thinking: bool

    # Cumulative totals
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_steps: int = 0

    # Step-level usage (LLM steps only)
    step_cost: Optional[float] = None
    step_input_tokens: Optional[int] = None
    step_output_tokens: Optional[int] = None
    step_total_tokens: Optional[int] = None

    # LLM output
    content: Optional[str] = None
    reasoning: Optional[str] = None

    # Tool calls from LLM
    tools_calling: Optional[list[dict[str, Any]]] = None
    # Tool results (call_tool steps)
    tools_result: Optional[list[dict[str, Any]]] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "step_type": self.step_type,
            "execution_time_ms": self.execution_time_ms,
            "thinking": self.thinking,
            "total_cost": self.total_cost,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_steps": self.total_steps,
        }
        if self.step_cost is not None:
            d["step_cost"] = self.step_cost
        if self.step_input_tokens is not None:
            d["step_input_tokens"] = self.step_input_tokens
        if self.step_output_tokens is not None:
            d["step_output_tokens"] = self.step_output_tokens
        if self.step_total_tokens is not None:
            d["step_total_tokens"] = self.step_total_tokens
        if self.content is not None:
            d["content"] = self.content
        if self.reasoning is not None:
            d["reasoning"] = self.reasoning
        if self.tools_calling:
            d["tools_calling"] = self.tools_calling
        if self.tools_result:
            d["tools_result"] = self.tools_result
        return d


# ---------------------------------------------------------------------------
# Step lifecycle callbacks
# ---------------------------------------------------------------------------

@dataclass
class StepLifecycleCallbacks:
    """Callbacks injected at operation creation time.

    Mirrors TS ``StepLifecycleCallbacks``.
    """

    on_before_step: Optional[Callable[..., Awaitable[None]]] = None
    on_after_step: Optional[Callable[..., Awaitable[None]]] = None
    on_complete: Optional[Callable[..., Awaitable[None]]] = None


# ---------------------------------------------------------------------------
# Operation tool set
# ---------------------------------------------------------------------------

@dataclass
class OperationToolSet:
    """Tool set for an operation."""

    manifest_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    executor_map: Optional[dict[str, Any]] = None
    source_map: Optional[dict[str, str]] = None
    tools: Optional[list[dict[str, Any]]] = None
    enabled_tool_ids: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Operation creation params
# ---------------------------------------------------------------------------

@dataclass
class OperationCreationParams:
    """Parameters for creating a new agent operation."""

    operation_id: str
    initial_messages: list[dict[str, Any]]
    tool_set: OperationToolSet

    agent_config: Optional[dict[str, Any]] = None
    app_context: Optional[dict[str, Any]] = None
    model_runtime_config: Optional[dict[str, Any]] = None
    user_id: Optional[str] = None
    auto_start: bool = True
    stream: Optional[bool] = True
    max_steps: Optional[int] = None
    hooks: Optional[list[Any]] = None  # list[AgentHook]
    signal: Optional[Any] = None  # AbortSignal
    user_memory: Optional[dict[str, Any]] = None
    user_timezone: Optional[str] = None
    user_intervention_config: Optional[dict[str, Any]] = None
    initial_step_count: int = 0
    lifecycle_callbacks: Optional[StepLifecycleCallbacks] = None


@dataclass
class OperationCreationResult:
    """Result of creating an agent operation."""

    operation_id: str
    success: bool
    auto_started: bool = False
    message_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Execution params & result
# ---------------------------------------------------------------------------

@dataclass
class AgentExecutionParams:
    """Parameters for executing a single step."""

    operation_id: str
    step_index: int
    context: Optional[dict[str, Any]] = None
    human_input: Optional[Any] = None
    approved_tool_call: Optional[Any] = None
    rejection_reason: Optional[str] = None
    reject_and_continue: bool = False
    tool_message_id: Optional[str] = None
    external_retry_count: int = 0


@dataclass
class AgentExecutionResult:
    """Result of a single step execution."""

    success: bool
    next_step_scheduled: bool
    state: dict[str, Any]
    step_result: Optional[dict[str, Any]] = None
    locked: bool = False


# ---------------------------------------------------------------------------
# Operation status
# ---------------------------------------------------------------------------

@dataclass
class OperationStatusResult:
    """Comprehensive operation status."""

    operation_id: str
    is_active: bool
    is_completed: bool
    has_error: bool
    needs_human_input: bool
    current_state: dict[str, Any]
    metadata: dict[str, Any]
    stats: dict[str, Any]
    execution_history: Optional[list[dict[str, Any]]] = None
    recent_events: Optional[list[dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

@dataclass
class CostInfo:
    """Cumulative cost tracking for an operation."""

    total: float = 0.0
    llm_cost: float = 0.0
    tool_cost: float = 0.0

    def add_step_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        """Calculate and add cost for a single step. Returns the step cost."""
        step_cost = _estimate_cost(input_tokens, output_tokens, model)
        self.total += step_cost
        self.llm_cost += step_cost
        return step_cost


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------

@dataclass
class UsageTracker:
    """Cumulative usage tracking for an operation."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    api_calls: int = 0
    tool_calls: int = 0

    def add_llm_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.api_calls += 1

    def add_tool_call(self, count: int = 1) -> None:
        self.tool_calls += count

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm": {
                "tokens": {
                    "input": self.input_tokens,
                    "output": self.output_tokens,
                    "total": self.total_tokens,
                },
                "apiCalls": self.api_calls,
            },
            "tools": {
                "totalCalls": self.tool_calls,
            },
        }


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

# Approximate cost per 1M tokens for common models (input, output)
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
}


def _estimate_cost(input_tokens: int, output_tokens: int, model: str = "") -> float:
    """Estimate cost in USD for a given token count and model."""
    # Normalize model name
    model_key = model.lower().split("/")[-1] if model else ""

    # Try exact match, then prefix match
    pricing = _MODEL_PRICING.get(model_key)
    if not pricing:
        for key, p in _MODEL_PRICING.items():
            if key in model_key:
                pricing = p
                break

    if not pricing:
        # Default: roughly gpt-4o pricing
        pricing = (2.50, 10.00)

    input_cost = (input_tokens / 1_000_000) * pricing[0]
    output_cost = (output_tokens / 1_000_000) * pricing[1]
    return input_cost + output_cost
