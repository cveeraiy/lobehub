from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.discord.client import DiscordClient


@pytest.mark.asyncio
async def test_discord_client_creates_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "discord-msg-1", "content": "hello"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await DiscordClient("bot-token").create_message("channel-1", "hello", client=client)

    assert result == {"id": "discord-msg-1", "content": "hello"}
    assert str(requests[0].url) == "https://discord.com/api/v10/channels/channel-1/messages"
    assert requests[0].headers["Authorization"] == "Bot bot-token"
    assert requests[0].read() == b'{"content":"hello"}'


@pytest.mark.asyncio
async def test_discord_client_send_reply_uses_inbound_channel_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_create_message(
        self: DiscordClient,
        channel_id: str,
        content: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, str]:
        calls.append({"channel_id": channel_id, "content": content})
        return {"id": "reply-1"}

    monkeypatch.setattr(DiscordClient, "create_message", fake_create_message)

    result = await DiscordClient("bot-token").send_reply({"channel_id": "channel-1"}, "hello")

    assert result == {"id": "reply-1"}
    assert calls == [{"channel_id": "channel-1", "content": "hello"}]
