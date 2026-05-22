"""AI Agent Service — unified orchestration layer for agent execution.

Mirrors the TS ``AiAgentService`` in ``src/server/services/aiAgent/index.ts``.
"""

from app.services.ai_agent.types import (
    AgentError,
    AgentErrorType,
    AppContext,
    ExecAgentParams,
    ExecAgentResult,
    ExecGroupAgentParams,
    ExecGroupAgentResult,
    ExecSubAgentTaskParams,
    ExecSubAgentTaskResult,
)


def __getattr__(name: str):
    if name == "AiAgentService":
        from app.services.ai_agent.service import AiAgentService

        return AiAgentService
    raise AttributeError(name)

__all__ = [
    "AiAgentService",
    "AgentError",
    "AgentErrorType",
    "AppContext",
    "ExecAgentParams",
    "ExecAgentResult",
    "ExecGroupAgentParams",
    "ExecGroupAgentResult",
    "ExecSubAgentTaskParams",
    "ExecSubAgentTaskResult",
]
