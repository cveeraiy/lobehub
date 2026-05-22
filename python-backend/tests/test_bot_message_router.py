from types import SimpleNamespace

import pytest

from app.routers import bot_message
from app.routers.bot_message import BotActionBody
from app.services.tool_execution.service import execute_tool_call

pytestmark = pytest.mark.asyncio


async def test_send_message_dispatches_to_slack(monkeypatch):
    calls = {}

    async def fake_resolve_bot(session, user_id, bot_id):
        calls["resolve"] = (session, user_id, bot_id)
        return SimpleNamespace(platform="slack", application_id="app-1", enabled=True), {"botToken": "xoxb-token"}

    class FakeSlackClient:
        def __init__(self, bot_token):
            calls["token"] = bot_token

        async def post_message(self, channel, text, *, thread_ts=None):
            calls["post"] = (channel, text, thread_ts)
            return {"ts": "1710000000.000100"}

    monkeypatch.setattr(bot_message, "_resolve_bot", fake_resolve_bot)
    monkeypatch.setattr(bot_message, "SlackClient", FakeSlackClient)

    response = await bot_message.send_message(
        BotActionBody(bot_id="bot-1", channel_id="C1", content="hello", reply_to="1709999999.000001"),
        user_id="user-1",
        session=object(),
    )

    assert response == {"channelId": "C1", "messageId": "1710000000.000100", "platform": "slack"}
    assert calls["token"] == "xoxb-token"
    assert calls["post"] == ("C1", "hello", "1709999999.000001")


async def test_read_messages_dispatches_to_discord(monkeypatch):
    async def fake_resolve_bot(session, user_id, bot_id):
        return SimpleNamespace(platform="discord", application_id="app-1", enabled=True), {"botToken": "bot-token"}

    async def fake_discord_request(token, method, path, *, json_body=None, params=None):
        assert token == "bot-token"
        assert method == "GET"
        assert path == "/channels/C1/messages"
        assert params == {"before": "m9", "after": None, "limit": 5}
        return [
            {
                "id": "m8",
                "content": "hello",
                "author": {"id": "u1", "username": "Ada"},
                "timestamp": "2026-05-20T00:00:00Z",
            }
        ]

    monkeypatch.setattr(bot_message, "_resolve_bot", fake_resolve_bot)
    monkeypatch.setattr(bot_message, "_discord_request", fake_discord_request)

    response = await bot_message.read_messages(
        botId="bot-1",
        channelId="C1",
        limit=5,
        before="m9",
        user_id="user-1",
        session=object(),
    )

    assert response["channelId"] == "C1"
    assert response["platform"] == "discord"
    assert response["totalFetched"] == 1
    assert response["messages"][0]["author"] == {"id": "u1", "name": "Ada"}


async def test_pin_message_dispatches_to_telegram(monkeypatch):
    calls = {}

    async def fake_resolve_bot(session, user_id, bot_id):
        return SimpleNamespace(platform="telegram", application_id="app-1", enabled=True), {"botToken": "tg-token"}

    async def fake_telegram_call(token, method, payload):
        calls["telegram"] = (token, method, payload)
        return {"ok": True, "result": True}

    monkeypatch.setattr(bot_message, "_resolve_bot", fake_resolve_bot)
    monkeypatch.setattr(bot_message, "_telegram_call", fake_telegram_call)

    response = await bot_message.pin_message(
        BotActionBody(bot_id="bot-1", channel_id="123", message_id="456"),
        user_id="user-1",
        session=object(),
    )

    assert response == {"messageId": "456", "success": True}
    assert calls["telegram"] == (
        "tg-token",
        "pinChatMessage",
        {"chat_id": "123", "message_id": 456, "disable_notification": True},
    )


async def test_context_backed_plain_tool_returns_context_error():
    response = await execute_tool_call("memory_search", {"query": "alpha"})

    assert "requires runtime context" in response
    assert "execute_tool_call_with_context" in response
