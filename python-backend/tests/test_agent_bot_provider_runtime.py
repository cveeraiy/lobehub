import pytest
from fastapi import HTTPException

from app.models.agent_ops import AgentBotProvider
from app.routers.agent_bot_providers import _start_runtime_for_provider
from app.services.bot.runtime_status import clear_bot_runtime_status, get_bot_runtime_status


def _provider(platform: str, application_id: str, *, enabled: bool = True) -> AgentBotProvider:
    return AgentBotProvider(
        id=f"{platform}-provider",
        agent_id="agent-1",
        user_id="user-1",
        platform=platform,
        application_id=application_id,
        enabled=enabled,
    )


def test_start_runtime_for_webhook_provider_marks_connected():
    clear_bot_runtime_status("telegram", "telegram-app")

    result = _start_runtime_for_provider(_provider("telegram", "telegram-app"))

    assert result["connect_status"] == "connected"
    assert result["connection_mode"] == "webhook"
    assert get_bot_runtime_status("telegram", "telegram-app")["status"] == "connected"


def test_start_runtime_for_websocket_provider_marks_started():
    clear_bot_runtime_status("discord", "discord-app")

    result = _start_runtime_for_provider(_provider("discord", "discord-app"))

    assert result["connect_status"] == "started"
    assert result["connection_mode"] == "websocket"
    assert result["runtime"] == "python-local"
    assert get_bot_runtime_status("discord", "discord-app")["status"] == "connected"


def test_start_runtime_for_polling_provider_marks_started():
    clear_bot_runtime_status("wechat", "wechat-app")

    result = _start_runtime_for_provider(_provider("wechat", "wechat-app"))

    assert result["connect_status"] == "started"
    assert result["connection_mode"] == "polling"
    assert get_bot_runtime_status("wechat", "wechat-app")["status"] == "connected"


def test_start_runtime_rejects_disabled_provider():
    with pytest.raises(HTTPException) as exc_info:
        _start_runtime_for_provider(_provider("discord", "disabled-app", enabled=False))

    assert exc_info.value.status_code == 400
