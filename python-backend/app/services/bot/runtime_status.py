from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

BotRuntimeStatus = Literal["connected", "connecting", "disconnected", "failed", "starting"]

_runtime_statuses: dict[tuple[str, str], dict[str, object]] = {}


def _now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def get_bot_runtime_status(platform: str, application_id: str) -> dict[str, object]:
    key = (platform, application_id)
    snapshot = _runtime_statuses.get(key)
    if snapshot:
        return dict(snapshot)
    return {
        "application_id": application_id,
        "platform": platform,
        "status": "disconnected",
        "updated_at": _now_ms(),
    }


def update_bot_runtime_status(
    platform: str,
    application_id: str,
    status: BotRuntimeStatus,
    error_message: str | None = None,
) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "application_id": application_id,
        "platform": platform,
        "status": status,
        "updated_at": _now_ms(),
    }
    if error_message:
        snapshot["error_message"] = error_message
    _runtime_statuses[(platform, application_id)] = snapshot
    return dict(snapshot)


def clear_bot_runtime_status(platform: str, application_id: str) -> dict[str, object]:
    return update_bot_runtime_status(platform, application_id, "disconnected")
