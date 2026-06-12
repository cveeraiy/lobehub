from __future__ import annotations

from app.services.bot.runtime_status import (
    clear_bot_runtime_status,
    get_bot_runtime_status,
    update_bot_runtime_status,
)


def test_runtime_status_defaults_to_disconnected() -> None:
    snapshot = get_bot_runtime_status("telegram", "runtime-default-test")

    assert snapshot["application_id"] == "runtime-default-test"
    assert snapshot["platform"] == "telegram"
    assert snapshot["status"] == "disconnected"
    assert isinstance(snapshot["updated_at"], int)


def test_runtime_status_updates_and_clears() -> None:
    connected = update_bot_runtime_status("telegram", "runtime-update-test", "connected")

    assert connected["status"] == "connected"
    assert get_bot_runtime_status("telegram", "runtime-update-test")["status"] == "connected"

    disconnected = clear_bot_runtime_status("telegram", "runtime-update-test")

    assert disconnected["status"] == "disconnected"
    assert get_bot_runtime_status("telegram", "runtime-update-test")["status"] == "disconnected"
