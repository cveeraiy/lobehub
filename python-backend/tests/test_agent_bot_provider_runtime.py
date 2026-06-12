import pytest
from fastapi import HTTPException

from app.models.agent_ops import AgentBotProvider
from app.routers.agent_bot_providers import _start_runtime_for_provider
from app.services.bot.platforms.wechat.client import fetch_qr_code, poll_qr_status
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


class _FakeResponse:
    def __init__(self, payload: dict, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.content = b"{}"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._payload


class _FakeWechatClient:
    def __init__(self, payload: dict) -> None:
        self.calls: list[dict] = []
        self.payload = payload

    async def get(self, url: str, **kwargs):
        self.calls.append({"kwargs": kwargs, "url": url})
        return _FakeResponse(self.payload)


@pytest.mark.asyncio
async def test_fetch_qr_code_calls_ilink_qrcode_endpoint():
    client = _FakeWechatClient({"qrcode": "qr-1", "qrcode_img_content": "image"})

    result = await fetch_qr_code(api_base="https://wechat.example.com/", client=client)

    assert result == {"qrcode": "qr-1", "qrcode_img_content": "image"}
    assert client.calls == [
        {
            "kwargs": {"params": {"bot_type": 3}},
            "url": "https://wechat.example.com/ilink/bot/get_bot_qrcode",
        }
    ]


@pytest.mark.asyncio
async def test_poll_qr_status_sends_qrcode_and_client_version_header():
    client = _FakeWechatClient({"status": "scaned"})

    result = await poll_qr_status("qr=special&chars", client=client)

    assert result == {"status": "scaned"}
    assert client.calls[0]["url"].endswith("/ilink/bot/get_qrcode_status")
    assert client.calls[0]["kwargs"] == {
        "headers": {"iLink-App-ClientVersion": "1"},
        "params": {"qrcode": "qr=special&chars"},
    }
