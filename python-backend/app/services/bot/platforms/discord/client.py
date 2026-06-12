from __future__ import annotations

from typing import Any

import httpx

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordApiError(RuntimeError):
    pass


class DiscordClient:
    def __init__(self, bot_token: str, *, api_base: str = DISCORD_API_BASE) -> None:
        self.bot_token = bot_token
        self.api_base = api_base.rstrip("/")

    async def create_message(
        self,
        channel_id: str,
        content: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.post(
                f"{self.api_base}/channels/{channel_id}/messages",
                headers={
                    "Authorization": f"Bot {self.bot_token}",
                    "Content-Type": "application/json",
                },
                json={"content": content[:2000]},
            )
        except httpx.HTTPError as exc:
            raise DiscordApiError("Failed to send Discord message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise DiscordApiError(f"Discord createMessage failed: {response.status_code} {response.text}")

        data = response.json()
        if not isinstance(data, dict):
            raise DiscordApiError("Discord createMessage returned an invalid response")
        return data

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        channel_id = activity.get("channel_id")
        if channel_id is None:
            raise DiscordApiError("Discord reply requires channel_id")
        return await self.create_message(str(channel_id), text)
