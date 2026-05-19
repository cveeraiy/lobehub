from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.telegram.definition import TELEGRAM_API_BASE


class TelegramApiError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, bot_token: str, *, api_base: str = TELEGRAM_API_BASE) -> None:
        self.bot_token = bot_token
        self.api_base = api_base.rstrip("/")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        message_thread_id: int | None = None,
        reply_to_message_id: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        if reply_to_message_id is not None:
            payload["reply_parameters"] = {"message_id": reply_to_message_id}

        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.post(
                f"{self.api_base}/bot{self.bot_token}/sendMessage",
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise TelegramApiError("Failed to send Telegram message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise TelegramApiError(f"Telegram sendMessage failed: {response.status_code} {response.text}")

        data = response.json()
        if not isinstance(data, dict):
            raise TelegramApiError("Telegram sendMessage returned an invalid response")
        return data

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        chat = activity.get("chat")
        if not isinstance(chat, dict) or chat.get("id") is None:
            raise TelegramApiError("Telegram reply requires chat.id")

        message_id = activity.get("message_id")
        thread_id = activity.get("message_thread_id")
        return await self.send_message(
            str(chat["id"]),
            text,
            message_thread_id=thread_id if isinstance(thread_id, int) else None,
            reply_to_message_id=message_id if isinstance(message_id, int) else None,
        )
