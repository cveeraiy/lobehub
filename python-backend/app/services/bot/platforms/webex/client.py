from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.webex.definition import MAX_WEBEX_MESSAGE_LENGTH, WEBEX_API_BASE


class WebexApiError(RuntimeError):
    pass


class WebexClient:
    def __init__(self, bot_token: str, *, api_base: str = WEBEX_API_BASE) -> None:
        self.bot_token = bot_token
        self.api_base = api_base.rstrip("/")

    async def create_message(
        self,
        room_id: str,
        text: str,
        *,
        parent_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "markdown": text[:MAX_WEBEX_MESSAGE_LENGTH],
            "roomId": room_id,
        }
        if parent_id:
            payload["parentId"] = parent_id

        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.post(
                f"{self.api_base}/messages",
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise WebexApiError("Failed to create Webex message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise WebexApiError(f"Webex create message failed: {response.status_code} {response.text}")
        data = response.json()
        if not isinstance(data, dict):
            raise WebexApiError("Webex create message returned an invalid response")
        return data

    async def get_message(
        self,
        message_id: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.get(
                f"{self.api_base}/messages/{message_id}",
                headers={"Authorization": f"Bearer {self.bot_token}"},
            )
        except httpx.HTTPError as exc:
            raise WebexApiError("Failed to fetch Webex message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise WebexApiError(f"Webex get message failed: {response.status_code} {response.text}")
        data = response.json()
        if not isinstance(data, dict):
            raise WebexApiError("Webex get message returned an invalid response")
        return data

    async def send_reply(self, event: dict[str, Any], text: str) -> dict[str, Any]:
        data = event.get("data") if isinstance(event.get("data"), dict) else event
        room_id = data.get("roomId") if isinstance(data, dict) else None
        if room_id is None:
            raise WebexApiError("Webex reply requires data.roomId")
        parent_id = data.get("parentId") or data.get("id")
        return await self.create_message(
            str(room_id),
            text,
            parent_id=str(parent_id) if parent_id is not None else None,
        )
