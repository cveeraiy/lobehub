"""Agent Runtime package — LangGraph-based step execution engine.

Usage::

    from app.services.agent_runtime import AgentRuntimeService, agent_runtime

    op = await agent_runtime.create_operation(user_id, messages, model="openai/gpt-4o")
    async for event in agent_runtime.stream_operation(op["operation_id"]):
        print(event)
"""

from app.services.agent_runtime.service import AgentRuntimeService, agent_runtime
from app.services.agent_runtime.state import AgentState, UsageInfo

__all__ = [
    "AgentRuntimeService",
    "AgentState",
    "UsageInfo",
    "agent_runtime",
]
