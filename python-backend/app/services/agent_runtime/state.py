"""Agent state definitions for the LangGraph agent runtime."""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict


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
