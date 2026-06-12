from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.slack.client import SlackClient


@pytest.mark.asyncio
async def test_slack_client_posts_thread_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "ts": "1710000002.000100"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SlackClient("xoxb-token").post_message(
            "C123",
            "hello",
            thread_ts="1710000000.000100",
            client=client,
        )

    assert result == {"ok": True, "ts": "1710000002.000100"}
    assert str(requests[0].url) == "https://slack.com/api/chat.postMessage"
    assert requests[0].headers["authorization"] == "Bearer xoxb-token"
    assert requests[0].headers["content-type"] == "application/x-www-form-urlencoded; charset=utf-8"
    assert requests[0].content == b"channel=C123&text=hello&thread_ts=1710000000.000100"


@pytest.mark.asyncio
async def test_slack_client_send_reply_uses_event_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str | None]] = []

    async def fake_post_message(
        self: SlackClient,
        channel: str,
        text: str,
        *,
        thread_ts: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, object]:
        calls.append({"channel": channel, "text": text, "thread_ts": thread_ts})
        return {"ok": True}

    monkeypatch.setattr(SlackClient, "post_message", fake_post_message)

    result = await SlackClient("xoxb-token").send_reply(
        {"channel": "C123", "ts": "1710000000.000100", "text": "hello"},
        "hello back",
    )

    assert result == {"ok": True}
    assert calls == [
        {
            "channel": "C123",
            "text": "hello back",
            "thread_ts": "1710000000.000100",
        }
    ]
