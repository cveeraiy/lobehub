from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.qq.client import QQClient


@pytest.mark.asyncio
async def test_qq_client_sends_group_reply() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://bots.qq.com/app/getAppAccessToken":
            return httpx.Response(200, json={"access_token": "access-token", "expires_in": 7200})
        return httpx.Response(200, json={"id": "reply-msg"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await QQClient("app-id", "app-secret").send_text(
            "/v2/groups/group-openid/messages",
            "hello",
            msg_id="msg-1",
            client=client,
        )

    assert result == {"id": "reply-msg"}
    assert requests[0].read() == b'{"appId":"app-id","clientSecret":"app-secret"}'
    assert str(requests[1].url) == "https://api.sgroup.qq.com/v2/groups/group-openid/messages"
    assert requests[1].headers["authorization"] == "QQBot access-token"
    assert requests[1].read() == b'{"content":"hello","msg_type":0,"msg_id":"msg-1"}'


@pytest.mark.asyncio
async def test_qq_client_send_reply_uses_group_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str | None]] = []

    async def fake_send_text(
        self: QQClient,
        path: str,
        content: str,
        *,
        msg_id: str | None = None,
        event_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, object]:
        calls.append({"content": content, "event_id": event_id, "msg_id": msg_id, "path": path})
        return {"id": "reply-msg"}

    monkeypatch.setattr(QQClient, "send_text", fake_send_text)

    result = await QQClient("app-id", "secret").send_reply(
        {"id": "msg-1", "group_openid": "group-openid"},
        "hello",
    )

    assert result == {"id": "reply-msg"}
    assert calls == [
        {
            "content": "hello",
            "event_id": None,
            "msg_id": "msg-1",
            "path": "/v2/groups/group-openid/messages",
        }
    ]


@pytest.mark.asyncio
async def test_qq_client_send_reply_uses_c2c_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_send_text(
        self: QQClient,
        path: str,
        content: str,
        *,
        msg_id: str | None = None,
        event_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, object]:
        calls.append(path)
        return {"id": "reply-msg"}

    monkeypatch.setattr(QQClient, "send_text", fake_send_text)

    await QQClient("app-id", "secret").send_reply({"author": {"id": "openid"}}, "hello")

    assert calls == ["/v2/users/openid/messages"]
