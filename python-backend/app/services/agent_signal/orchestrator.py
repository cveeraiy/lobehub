"""Signal orchestrator — routes signals through policies to processors."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import time
from typing import Any, Awaitable, Callable, Optional

from app.services.agent_signal.types import Signal, SignalAction, SignalPolicy

logger = logging.getLogger(__name__)

ActionHandler = Callable[[SignalAction], Awaitable[None]]


class SignalOrchestrator:
    """Central hub that receives signals, evaluates policies, and dispatches actions.

    Simplified version of the TS orchestrator. The full TS version has:
    - Feature gating per-user
    - Store-backed policy persistence
    - Observability spans (OpenTelemetry)
    - Middleware pipeline
    This Python version is intentionally smaller; extend as needed.
    """

    def __init__(self) -> None:
        self._policies: list[SignalPolicy] = []
        self._handlers: dict[str, ActionHandler] = {}
        self._dedup_cache: dict[str, float] = {}  # dedup_key → last_fired_ts
        self._firing_counts: dict[str, list[float]] = {}  # policy_id → [ts, ...]

    # ── Configuration ────────────────────────────────────────────────

    def register_policy(self, policy: SignalPolicy) -> None:
        self._policies.append(policy)
        logger.debug("Registered signal policy: %s", policy.name)

    def register_handler(self, action_type: str, handler: ActionHandler) -> None:
        self._handlers[action_type] = handler

    # ── Core dispatch ────────────────────────────────────────────────

    async def emit(self, signal: Signal) -> list[SignalAction]:
        """Evaluate signal against all policies, dispatch matching actions.

        Returns the list of actions that were dispatched.
        """
        logger.debug(
            "Signal received: source=%s type=%s agent=%s",
            signal.source, signal.type, signal.agent_id,
        )

        # Dedup check
        if signal.dedup_key:
            last_fired = self._dedup_cache.get(signal.dedup_key)
            if last_fired is not None:
                logger.debug("Signal deduped: %s", signal.dedup_key)
                return []
            self._dedup_cache[signal.dedup_key] = time.time()

        matched_actions: list[SignalAction] = []

        for policy in self._policies:
            if not policy.enabled:
                continue
            if not self._matches(policy, signal):
                continue
            if not self._rate_ok(policy):
                logger.debug("Policy %s rate-limited", policy.id)
                continue

            action = SignalAction(
                type=policy.action_type,
                agent_id=signal.agent_id or policy.agent_id,
                task_id=policy.action_params.get("task_id"),
                params={**policy.action_params, "signal": signal.payload},
            )
            matched_actions.append(action)

        # Dispatch actions concurrently
        if matched_actions:
            await asyncio.gather(
                *(self._dispatch(a) for a in matched_actions),
                return_exceptions=True,
            )

        return matched_actions

    # ── Internals ────────────────────────────────────────────────────

    def _matches(self, policy: SignalPolicy, signal: Signal) -> bool:
        if policy.source_pattern and not fnmatch.fnmatch(signal.source, policy.source_pattern):
            return False
        if policy.type_pattern and not fnmatch.fnmatch(signal.type, policy.type_pattern):
            return False
        if policy.agent_id and policy.agent_id != signal.agent_id:
            return False
        return True

    def _rate_ok(self, policy: SignalPolicy) -> bool:
        now = time.time()

        # Cooldown check
        if policy.cooldown_seconds > 0:
            firings = self._firing_counts.get(policy.id, [])
            if firings and (now - firings[-1]) < policy.cooldown_seconds:
                return False

        # Max firings per hour
        if policy.max_firings_per_hour > 0:
            firings = self._firing_counts.get(policy.id, [])
            hour_ago = now - 3600
            recent = [t for t in firings if t > hour_ago]
            if len(recent) >= policy.max_firings_per_hour:
                return False

        # Record firing
        self._firing_counts.setdefault(policy.id, []).append(now)
        return True

    async def _dispatch(self, action: SignalAction) -> None:
        handler = self._handlers.get(action.type)
        if handler is None:
            logger.warning("No handler registered for action type: %s", action.type)
            return
        try:
            await handler(action)
        except Exception:
            logger.exception("Action handler failed: %s", action.type)

    # ── Maintenance ──────────────────────────────────────────────────

    def cleanup_dedup_cache(self, max_age_seconds: int = 3600) -> int:
        """Remove stale dedup entries. Returns number of evicted entries."""
        cutoff = time.time() - max_age_seconds
        stale = [k for k, v in self._dedup_cache.items() if v < cutoff]
        for k in stale:
            del self._dedup_cache[k]
        return len(stale)


# ── Module-level singleton ────────────────────────────────────────────
_orchestrator: SignalOrchestrator | None = None


def get_orchestrator() -> SignalOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SignalOrchestrator()
    return _orchestrator
