from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.line.client import LineClient, line_recipient_id


def test_line_recipient_id_prefers_conversation_scope() -> None:
    assert line_recipient_id({"type": "user", "userId": "Uuser"}) == "Uuser"
    assert line_recipient_id({"type": "group", "groupId": "Ggroup", "userId": "Uuser"}) == "Ggroup"
    assert line_recipient_id({"type": "room", "roomId": "Rroom", "userId": "Uuser"}) == "Rroom"


@pytest.mark.asyncio
async def test_line_client_pushes_text_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await LineClient("access-token").push_text("Uuser", "hello", client=client)

    assert result == {}
    assert str(requests[0].url) == "https://api.line.me/v2/bot/message/push"
    assert requests[0].headers["authorization"] == "Bearer access-token"
    assert requests[0].read() == b'{"to":"Uuser","messages":[{"type":"text","text":"hello"}]}'


@pytest.mark.asyncio
async def test_line_client_send_reply_uses_source_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_push_text(
        self: LineClient,
        to: str,
        text: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, object]:
        calls.append({"text": text, "to": to})
        return {}

    monkeypatch.setattr(LineClient, "push_text", fake_push_text)

    result = await LineClient("access-token").send_reply(
        {"source": {"type": "group", "groupId": "Ggroup", "userId": "Uuser"}},
        "hello",
    )

    assert result == {}
    assert calls == [{"text": "hello", "to": "Ggroup"}]
