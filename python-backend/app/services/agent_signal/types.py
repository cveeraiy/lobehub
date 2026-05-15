"""Core types for the agent signal pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Signal:
    """An inbound signal from an external source."""

    source: str  # e.g. "cron", "webhook", "task_complete", "user_action"
    type: str  # semantic type: "schedule_trigger", "document_updated", etc.
    agent_id: str | None = None
    user_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    scope: str | None = None  # optional namespace for dedup
    dedup_key: str | None = None  # if set, duplicate signals are suppressed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SignalAction:
    """An action the orchestrator should take in response to a signal."""

    type: str  # "run_task", "send_message", "create_brief", "noop"
    agent_id: str | None = None
    task_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalPolicy:
    """A routing rule that maps signal patterns to actions.

    The TS implementation supports complex policy trees; this is a
    simplified flat version suitable for initial parity.
    """

    id: str
    name: str
    # Match criteria
    source_pattern: str | None = None  # glob pattern on signal.source
    type_pattern: str | None = None  # glob pattern on signal.type
    agent_id: str | None = None  # if set, only match this agent
    # Action template
    action_type: str = "run_task"
    action_params: dict[str, Any] = field(default_factory=dict)
    # Controls
    enabled: bool = True
    cooldown_seconds: int = 0  # minimum interval between firings
    max_firings_per_hour: int = 0  # 0 = unlimited
