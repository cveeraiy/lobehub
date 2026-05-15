"""HookDispatcher — central hub for registering and dispatching agent lifecycle hooks.

Mirrors TS ``agentRuntime/hooks/HookDispatcher.ts``.

Local mode: hooks stored in memory, handler functions called directly.
Production mode: webhook configs delivered via HTTP POST.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from app.services.agent_runtime_hooks.types import (
    AgentHook,
    AgentHookEvent,
    AgentHookType,
    AgentHookWebhook,
    SerializedHook,
    ToolCallHookEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Webhook delivery helpers
# ---------------------------------------------------------------------------

async def _fetch_deliver(url: str, payload: dict[str, Any]) -> None:
    """Deliver a webhook via plain HTTP POST."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            logger.debug("Webhook delivered via fetch: %s (status: %d)", url, resp.status_code)
    except Exception as exc:
        logger.debug("Webhook fetch delivery failed: %s %s", url, exc)
        # Hook errors should not affect main flow


async def _deliver_webhook(webhook: AgentHookWebhook, payload: dict[str, Any]) -> None:
    """Deliver a webhook via HTTP POST (fetch or qstash)."""
    url = webhook.url

    # Resolve relative URLs
    if not url.startswith("http"):
        base = os.environ.get("INTERNAL_APP_URL") or os.environ.get("APP_URL", "")
        url = urljoin(base, url) if base else url

    if webhook.delivery == "qstash":
        # QStash not available in Python — fall back to fetch
        logger.debug("QStash delivery not available in Python, falling back to fetch")
        await _fetch_deliver(url, payload)
    else:
        await _fetch_deliver(url, payload)


def _build_webhook_payload(
    event: dict[str, Any],
    event_fields: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build webhook payload, optionally filtering to specified fields."""
    if event_fields:
        return {k: v for k, v in event.items() if k in event_fields and k != "finalState"}

    # Default: include everything except finalState (too large)
    return {k: v for k, v in event.items() if k != "finalState"}


# ---------------------------------------------------------------------------
# HookDispatcher
# ---------------------------------------------------------------------------

class HookDispatcher:
    """Central hub for registering and dispatching agent lifecycle hooks.

    Local mode: hooks stored in memory, handler functions called directly.
    Production mode: webhook configs persisted in AgentState.metadata._hooks,
    delivered via HTTP POST.
    """

    def __init__(self) -> None:
        # Maps operationId → list[AgentHook]
        self._hooks: dict[str, list[AgentHook]] = {}

    # ---- Registration ----

    def register(self, operation_id: str, hooks: list[AgentHook]) -> None:
        """Register hooks for an operation."""
        if not hooks:
            return

        existing = self._hooks.get(operation_id, [])
        self._hooks[operation_id] = existing + list(hooks)

        logger.debug(
            "[%s] Registered %d hooks: %s",
            operation_id,
            len(hooks),
            ", ".join(f"{h.type}:{h.id}" for h in hooks),
        )

    def unregister(self, operation_id: str) -> None:
        """Unregister all hooks for an operation (cleanup)."""
        self._hooks.pop(operation_id, None)
        logger.debug("[%s] Unregistered all hooks", operation_id)

    def has_hooks(self, operation_id: str) -> bool:
        """Check if any hooks are registered for an operation."""
        return len(self._hooks.get(operation_id, [])) > 0

    # ---- Serialization ----

    def get_serialized_hooks(self, operation_id: str) -> list[SerializedHook] | None:
        """Get serialized hooks for an operation (for production mode persistence)."""
        hooks = self._hooks.get(operation_id)
        if not hooks:
            return None

        return [
            SerializedHook(id=h.id, type=h.type, webhook=h.webhook)
            for h in hooks
            if h.webhook is not None
        ]

    # ---- Dispatch ----

    async def dispatch(
        self,
        operation_id: str,
        hook_type: AgentHookType,
        event: AgentHookEvent,
        serialized_hooks: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Dispatch hooks for a given event type.

        In local mode: calls handler functions from memory.
        In production mode: delivers webhooks from serialized config.
        """
        # Local mode: call handler functions directly
        local_hooks = [
            h for h in self._hooks.get(operation_id, [])
            if h.type == hook_type
        ]

        for hook in local_hooks:
            try:
                logger.debug("[%s][%s] Dispatching local hook: %s", operation_id, hook_type, hook.id)
                await hook.handler(event)
            except Exception as exc:
                logger.debug(
                    "[%s][%s] Hook error (non-fatal): %s %s",
                    operation_id, hook_type, hook.id, exc,
                )
                # Hook errors should NOT affect main execution flow

        # Production mode: deliver via webhooks from serialized config
        if serialized_hooks:
            webhook_hooks = [
                SerializedHook.from_dict(h)
                for h in serialized_hooks
                if h.get("type") == hook_type and h.get("webhook")
            ]

            for hook in webhook_hooks:
                try:
                    logger.debug(
                        "[%s][%s] Delivering webhook hook: %s → %s",
                        operation_id, hook_type, hook.id, hook.webhook.url,
                    )
                    webhook_payload = _build_webhook_payload(
                        event, hook.webhook.event_fields
                    )
                    await _deliver_webhook(hook.webhook, {
                        **webhook_payload,
                        "hookId": hook.id,
                        "hookType": hook_type,
                        **(hook.webhook.body or {}),
                    })
                except Exception as exc:
                    logger.debug(
                        "[%s][%s] Webhook delivery error (non-fatal): %s %s",
                        operation_id, hook_type, hook.id, exc,
                    )

    async def dispatch_before_tool_call(
        self,
        operation_id: str,
        event: ToolCallHookEvent,
    ) -> Optional[dict[str, Any]]:
        """Dispatch beforeToolCall hooks with mock support.

        Returns ``{"content": "...", "is_mocked": True}`` if any handler
        called ``event.mock()``, otherwise ``None``.
        """
        hooks = [
            h for h in self._hooks.get(operation_id, [])
            if h.type == "beforeToolCall"
        ]
        if not hooks:
            return None

        for hook in hooks:
            try:
                logger.debug("[%s][beforeToolCall] Dispatching: %s", operation_id, hook.id)
                # Convert ToolCallHookEvent to dict for handler
                event_dict: AgentHookEvent = {
                    "operation_id": event.operation_id,
                    "tool_name": event.tool_name,
                    "tool_args": event.tool_args,
                    "identifier": event.identifier,
                    "api_name": event.api_name,
                    "step_index": event.step_index,
                    "agent_id": event.agent_id,
                    "user_id": event.user_id,
                    "topic_id": event.topic_id,
                    "mock": event.mock,
                }
                await hook.handler(event_dict)
            except Exception as exc:
                logger.debug(
                    "[%s][beforeToolCall] Hook error (non-fatal): %s %s",
                    operation_id, hook.id, exc,
                )

        if event.is_mocked:
            return {"content": event.mocked_content, "is_mocked": True}
        return None


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

hook_dispatcher = HookDispatcher()
