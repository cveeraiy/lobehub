"""Agent Runtime Hook types.

Mirrors TS ``agentRuntime/hooks/types.ts``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Hook type enum (string literal union in TS)
# ---------------------------------------------------------------------------

AgentHookType = Literal[
    "beforeStep",
    "afterStep",
    "beforeToolCall",
    "afterToolCall",
    "beforeCallAgent",
    "afterCallAgent",
    "callAgentError",
    "toolCallError",
    "beforeCompact",
    "afterCompact",
    "compactError",
    "beforeHumanIntervention",
    "afterHumanIntervention",
    "onStopByHumanIntervention",
    "onComplete",
    "onError",
]

# ---------------------------------------------------------------------------
# Hook event — base dict-like payload dispatched to handlers
# ---------------------------------------------------------------------------

AgentHookEvent = dict[str, Any]


@dataclass
class ToolCallHookEvent:
    """Specialized event for beforeToolCall — supports ``mock()``."""

    operation_id: str
    tool_name: str
    tool_args: dict[str, Any]
    identifier: str = ""
    api_name: str = ""
    # Additional context
    step_index: int = 0
    agent_id: str = ""
    user_id: str = ""
    topic_id: str = ""

    # Private mutable state — set by HookDispatcher
    _mocked: bool = field(default=False, init=False, repr=False)
    _mocked_content: str = field(default="", init=False, repr=False)

    def mock(self, result: dict[str, Any] | None = None) -> None:
        """Mock the tool call result — skip actual execution.

        ``result`` must have a non-empty ``content`` string key.
        """
        if result and isinstance(result.get("content"), str) and len(result["content"]) > 0:
            self._mocked = True
            self._mocked_content = result["content"]

    @property
    def is_mocked(self) -> bool:
        return self._mocked

    @property
    def mocked_content(self) -> str:
        return self._mocked_content


# ---------------------------------------------------------------------------
# Webhook delivery config
# ---------------------------------------------------------------------------

@dataclass
class AgentHookWebhook:
    """Webhook delivery configuration for production mode."""

    url: str
    delivery: Literal["fetch", "qstash", "temporal"] = "fetch"
    body: dict[str, Any] | None = None
    event_fields: list[str] | None = None


# ---------------------------------------------------------------------------
# Hook definition
# ---------------------------------------------------------------------------

@dataclass
class AgentHook:
    """Hook definition — consumers register these with execAgent."""

    id: str
    type: AgentHookType
    handler: Callable[[AgentHookEvent], Awaitable[None]]
    webhook: AgentHookWebhook | None = None


# ---------------------------------------------------------------------------
# Serialized hook (for Redis/state persistence — no handler function)
# ---------------------------------------------------------------------------

@dataclass
class SerializedHook:
    """Serialized hook config stored in AgentState metadata.

    Only contains webhook info (handler functions can't be serialized).
    """

    id: str
    type: AgentHookType
    webhook: AgentHookWebhook

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "webhook": {
                "url": self.webhook.url,
                "delivery": self.webhook.delivery,
                **({"body": self.webhook.body} if self.webhook.body else {}),
                **({"event_fields": self.webhook.event_fields} if self.webhook.event_fields else {}),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SerializedHook:
        wh = data.get("webhook", {})
        return cls(
            id=data["id"],
            type=data["type"],
            webhook=AgentHookWebhook(
                url=wh["url"],
                delivery=wh.get("delivery", "fetch"),
                body=wh.get("body"),
                event_fields=wh.get("event_fields"),
            ),
        )
