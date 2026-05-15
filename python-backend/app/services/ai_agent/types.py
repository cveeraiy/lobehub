"""Types for the AI Agent Service.

Mirrors TS types: ExecAgentParams, ExecAgentResult, InternalExecAgentParams,
ExecGroupAgentParams/Result, ExecSubAgentTaskParams/Result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class AgentErrorType(str, Enum):
    AGENT_NOT_FOUND = "AgentNotFound"
    VALIDATION_ERROR = "ValidationError"
    ABORTED = "Aborted"
    RUNTIME_ERROR = "ServerAgentRuntimeError"
    CONTENT_POLICY = "ContentPolicyViolation"
    TOOL_EXECUTION_ERROR = "ToolExecutionError"


@dataclass
class AgentError:
    type: AgentErrorType
    message: str
    body: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type.value, "message": self.message}
        if self.body:
            d["body"] = self.body
        return d


# ---------------------------------------------------------------------------
# AppContext — mirrors TS AppContext
# ---------------------------------------------------------------------------

@dataclass
class AppContext:
    session_id: Optional[str] = None
    topic_id: Optional[str] = None
    thread_id: Optional[str] = None
    group_id: Optional[str] = None
    agent_id: Optional[str] = None
    scope: Optional[str] = None  # 'chat' | 'page' | 'task'
    document_id: Optional[str] = None
    task_id: Optional[str] = None
    default_task_assignee_agent_id: Optional[str] = None
    trigger: Optional[str] = None  # 'cron' | 'chat' | 'api' | 'task'
    source_message_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Human approval
# ---------------------------------------------------------------------------

@dataclass
class ResumeApproval:
    decision: Literal["approved", "rejected", "rejected_continue"]
    parent_message_id: str
    tool_call_id: str
    rejection_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# ExecAgent params / result
# ---------------------------------------------------------------------------

@dataclass
class ExecAgentParams:
    prompt: str
    agent_id: Optional[str] = None
    slug: Optional[str] = None
    app_context: Optional[AppContext] = None
    auto_start: bool = True
    model: Optional[str] = None
    provider: Optional[str] = None
    instructions: Optional[str] = None
    file_ids: Optional[list[str]] = None
    files: Optional[list[dict[str, Any]]] = None
    existing_message_ids: Optional[list[str]] = None
    stream: Optional[bool] = True
    title: Optional[str] = None
    trigger: Optional[str] = None
    cron_job_id: Optional[str] = None
    task_id: Optional[str] = None
    max_steps: Optional[int] = None
    initial_step_count: Optional[int] = None
    disable_tools: bool = False
    hooks: Optional[list[dict[str, Any]]] = None
    user_intervention_config: Optional[dict[str, Any]] = None
    resume: bool = False
    resume_approval: Optional[ResumeApproval] = None
    parent_message_id: Optional[str] = None
    additional_plugin_ids: Optional[list[str]] = None
    function_tools: Optional[list[dict[str, Any]]] = None
    # Internal fields set by the service
    bot_context: Optional[dict[str, Any]] = None
    eval_context: Optional[dict[str, Any]] = None


@dataclass
class ExecAgentResult:
    success: bool
    operation_id: str
    topic_id: str
    agent_id: str
    assistant_message_id: str
    user_message_id: str
    status: str = "created"
    auto_started: bool = False
    error: Optional[str] = None
    message: str = "Agent operation created successfully"
    created_at: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "operation_id": self.operation_id,
            "topic_id": self.topic_id,
            "agent_id": self.agent_id,
            "assistant_message_id": self.assistant_message_id,
            "user_message_id": self.user_message_id,
            "status": self.status,
            "auto_started": self.auto_started,
            "error": self.error,
            "message": self.message,
            "created_at": self.created_at,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# ExecGroupAgent params / result
# ---------------------------------------------------------------------------

@dataclass
class ExecGroupAgentParams:
    agent_id: str
    group_id: str
    message: str
    topic_id: Optional[str] = None
    new_topic: Optional[dict[str, Any]] = None


@dataclass
class ExecGroupAgentResult:
    success: bool
    operation_id: str
    topic_id: str
    assistant_message_id: str
    user_message_id: str
    is_create_new_topic: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "operation_id": self.operation_id,
            "topic_id": self.topic_id,
            "assistant_message_id": self.assistant_message_id,
            "user_message_id": self.user_message_id,
            "is_create_new_topic": self.is_create_new_topic,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# ExecSubAgentTask params / result
# ---------------------------------------------------------------------------

@dataclass
class ExecSubAgentTaskParams:
    agent_id: str
    topic_id: str
    instruction: str
    parent_message_id: str
    group_id: Optional[str] = None
    title: Optional[str] = None
    parent_operation_id: Optional[str] = None


@dataclass
class ExecSubAgentTaskResult:
    success: bool
    operation_id: str
    thread_id: str
    assistant_message_id: str
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "operation_id": self.operation_id,
            "thread_id": self.thread_id,
            "assistant_message_id": self.assistant_message_id,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Tool manifest types
# ---------------------------------------------------------------------------

@dataclass
class ToolManifest:
    identifier: str
    api: list[dict[str, Any]] = field(default_factory=list)
    meta: Optional[dict[str, Any]] = None
    system_role: Optional[str] = None
    type: str = "default"


# ---------------------------------------------------------------------------
# Lifecycle hook types
# ---------------------------------------------------------------------------

@dataclass
class StepEvent:
    operation_id: str
    step_count: int
    status: str
    usage: Optional[dict[str, Any]] = None
    messages: Optional[list[dict[str, Any]]] = None
    error: Optional[Any] = None
    reason: Optional[str] = None
    final_state: Optional[dict[str, Any]] = None
