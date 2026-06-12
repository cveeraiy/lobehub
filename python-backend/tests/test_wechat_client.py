from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.wechat.client import WechatClient


@pytest.mark.asyncio
async def test_wechat_client_sends_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ret": 0})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WechatClient("bot-token").send_message(
            "user-1@im.wechat",
            "hello",
            "ctx-token",
            client=client,
        )

    assert result == {"ret": 0}
    assert str(requests[0].url) == "https://ilinkai.weixin.qq.com/ilink/bot/sendmessage"
    assert requests[0].headers["authorization"] == "Bearer bot-token"
    assert requests[0].headers["authorizationtype"] == "ilink_bot_token"
    body = requests[0].read()
    assert b'"context_token":"ctx-token"' in body
    assert b'"message_state":2' in body
    assert b'"message_type":2' in body
    assert b'"to_user_id":"user-1@im.wechat"' in body
    assert b'"text":"hello"' in body


@pytest.mark.asyncio
async def test_wechat_client_send_reply_uses_inbound_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_send_message(
        self: WechatClient,
        to_user_id: str,
        text: str,
        context_token: str = "",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, object]:
        calls.append({"context_token": context_token, "text": text, "to_user_id": to_user_id})
        return {"ret": 0}

    monkeypatch.setattr(WechatClient, "send_message", fake_send_message)

    result = await WechatClient("bot-token").send_reply(
        {"context_token": "ctx-token", "from_user_id": "user-1@im.wechat"},
        "hello",
    )

    assert result == {"ret": 0}
    assert calls == [
        {
            "context_token": "ctx-token",
            "text": "hello",
            "to_user_id": "user-1@im.wechat",
        }
    ]
