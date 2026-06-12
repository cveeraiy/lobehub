from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.line.definition import LINE_API_BASE


class LineApiError(RuntimeError):
    pass


def line_recipient_id(source: dict[str, Any]) -> str | None:
    source_type = source.get("type")
    if source_type == "group":
        value = source.get("groupId")
    elif source_type == "room":
        value = source.get("roomId")
    else:
        value = source.get("userId")
    return str(value) if value is not None else None


class LineClient:
    def __init__(self, channel_access_token: str, *, api_base: str = LINE_API_BASE) -> None:
        self.channel_access_token = channel_access_token
        self.api_base = api_base.rstrip("/")

    async def push_text(
        self,
        to: str,
        text: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.post(
                f"{self.api_base}/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {self.channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={"to": to, "messages": [{"type": "text", "text": text}]},
            )
        except httpx.HTTPError as exc:
            raise LineApiError("Failed to push LINE message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise LineApiError(f"LINE push message failed: {response.status_code} {response.text}")
        if not response.content:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def send_reply(self, event: dict[str, Any], text: str) -> dict[str, Any]:
        source = event.get("source")
        if not isinstance(source, dict):
            raise LineApiError("LINE reply requires event.source")
        recipient = line_recipient_id(source)
        if not recipient:
            raise LineApiError("LINE reply requires a source recipient id")
        return await self.push_text(recipient, text)
