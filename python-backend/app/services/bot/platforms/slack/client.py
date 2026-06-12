from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.slack.definition import SLACK_API_BASE


class SlackApiError(RuntimeError):
    pass


class SlackClient:
    def __init__(self, bot_token: str, *, api_base: str = SLACK_API_BASE) -> None:
        self.bot_token = bot_token
        self.api_base = api_base.rstrip("/")

    async def post_message(
        self,
        channel: str,
        text: str,
        *,
        thread_ts: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        data = {
            "channel": channel,
            "text": text[:39_997] + "..." if len(text) > 40_000 else text,
        }
        if thread_ts:
            data["thread_ts"] = thread_ts

        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.post(
                f"{self.api_base}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                },
                data=data,
            )
        except httpx.HTTPError as exc:
            raise SlackApiError("Failed to post Slack message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise SlackApiError(f"Slack chat.postMessage failed: {response.status_code} {response.text}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SlackApiError("Slack chat.postMessage returned an invalid response")
        if payload.get("ok") is not True:
            raise SlackApiError(f"Slack chat.postMessage failed: {payload.get('error') or 'unknown_error'}")
        return payload

    async def send_reply(self, event: dict[str, Any], text: str) -> dict[str, Any]:
        channel = event.get("channel")
        if channel is None:
            raise SlackApiError("Slack reply requires event.channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        return await self.post_message(
            str(channel),
            text,
            thread_ts=str(thread_ts) if thread_ts is not None else None,
        )
