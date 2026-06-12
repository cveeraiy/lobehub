from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.telegram.client import TelegramClient


@pytest.mark.asyncio
async def test_telegram_client_sends_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TelegramClient("bot-token").send_message(
            "-100123",
            "hello",
            message_thread_id=7,
            reply_to_message_id=41,
            client=client,
        )

    assert result == {"ok": True, "result": {"message_id": 42}}
    assert str(requests[0].url) == "https://api.telegram.org/botbot-token/sendMessage"
    assert requests[0].read() == (
        b'{"chat_id":"-100123","text":"hello","message_thread_id":7,'
        b'"reply_parameters":{"message_id":41}}'
    )


@pytest.mark.asyncio
async def test_telegram_client_send_reply_uses_inbound_activity_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_send_message(
        self: TelegramClient,
        chat_id: str,
        text: str,
        *,
        message_thread_id: int | None = None,
        reply_to_message_id: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, object]:
        calls.append(
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "reply_to_message_id": reply_to_message_id,
                "text": text,
            }
        )
        return {"ok": True}

    monkeypatch.setattr(TelegramClient, "send_message", fake_send_message)

    result = await TelegramClient("bot-token").send_reply(
        {
            "message_id": 41,
            "message_thread_id": 7,
            "chat": {"id": -100123},
        },
        "hello",
    )

    assert result == {"ok": True}
    assert calls == [
        {
            "chat_id": "-100123",
            "message_thread_id": 7,
            "reply_to_message_id": 41,
            "text": "hello",
        }
    ]
