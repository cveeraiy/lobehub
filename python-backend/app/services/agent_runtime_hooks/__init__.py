"""Agent Runtime Hooks — lifecycle hook system for agent execution.

Mirrors the TS HookDispatcher from ``agentRuntime/hooks/``.
"""

from app.services.agent_runtime_hooks.dispatcher import HookDispatcher, hook_dispatcher
from app.services.agent_runtime_hooks.types import (
    AgentHook,
    AgentHookEvent,
    AgentHookType,
    AgentHookWebhook,
    SerializedHook,
    ToolCallHookEvent,
)

__all__ = [
    "AgentHook",
    "AgentHookEvent",
    "AgentHookType",
    "AgentHookWebhook",
    "HookDispatcher",
    "SerializedHook",
    "ToolCallHookEvent",
    "hook_dispatcher",
]
