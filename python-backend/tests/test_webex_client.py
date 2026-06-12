from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.webex.client import WebexClient


@pytest.mark.asyncio
async def test_webex_client_creates_threaded_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "webex-reply-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WebexClient("bot-token").create_message(
            "room-1",
            "hello",
            parent_id="parent-1",
            client=client,
        )

    assert result == {"id": "webex-reply-1"}
    assert str(requests[0].url) == "https://webexapis.com/v1/messages"
    assert requests[0].headers["Authorization"] == "Bearer bot-token"
    assert requests[0].read() == b'{"markdown":"hello","roomId":"room-1","parentId":"parent-1"}'


@pytest.mark.asyncio
async def test_webex_client_gets_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "webex-msg-1", "text": "hello"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WebexClient("bot-token").get_message("webex-msg-1", client=client)

    assert result == {"id": "webex-msg-1", "text": "hello"}
    assert str(requests[0].url) == "https://webexapis.com/v1/messages/webex-msg-1"
    assert requests[0].headers["Authorization"] == "Bearer bot-token"


@pytest.mark.asyncio
async def test_webex_client_send_reply_uses_webhook_data_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str | None]] = []

    async def fake_create_message(
        self: WebexClient,
        room_id: str,
        text: str,
        *,
        parent_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, str]:
        calls.append({"parent_id": parent_id, "room_id": room_id, "text": text})
        return {"id": "reply-1"}

    monkeypatch.setattr(WebexClient, "create_message", fake_create_message)

    result = await WebexClient("bot-token").send_reply(
        {"data": {"id": "webex-msg-1", "roomId": "room-1"}},
        "hello back",
    )

    assert result == {"id": "reply-1"}
    assert calls == [{"parent_id": "webex-msg-1", "room_id": "room-1", "text": "hello back"}]
