from __future__ import annotations

import time
from typing import Any

import httpx

from app.services.bot.platforms.qq.definition import QQ_AUTH_URL

QQ_API_BASE = "https://api.sgroup.qq.com"
MAX_QQ_TEXT_LENGTH = 2000


class QQApiError(RuntimeError):
    pass


class QQClient:
    def __init__(self, app_id: str, app_secret: str, *, api_base: str = QQ_API_BASE) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_base = api_base.rstrip("/")
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    async def get_access_token(self, client: httpx.AsyncClient | None = None) -> str:
        if self._access_token and time.time() < self._access_token_expires_at:
            return self._access_token

        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.post(
                QQ_AUTH_URL,
                json={"appId": self.app_id, "clientSecret": self.app_secret},
            )
        except httpx.HTTPError as exc:
            raise QQApiError("Failed to authenticate with QQ API") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise QQApiError(f"QQ auth failed: {response.status_code} {response.text}")
        data = response.json()
        if not isinstance(data, dict) or not data.get("access_token"):
            raise QQApiError("QQ auth failed: missing access_token")

        self._access_token = str(data["access_token"])
        expires_in = int(data.get("expires_in") or 7200)
        self._access_token_expires_at = time.time() + max(expires_in - 300, 60)
        return self._access_token

    async def send_text(
        self,
        path: str,
        content: str,
        *,
        msg_id: str | None = None,
        event_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "content": _truncate_text(content),
            "msg_type": 0,
        }
        if msg_id:
            body["msg_id"] = msg_id
        if event_id:
            body["event_id"] = event_id

        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            token = await self.get_access_token(http_client)
            response = await http_client.post(
                f"{self.api_base}{path}",
                headers={
                    "Authorization": f"QQBot {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        except httpx.HTTPError as exc:
            raise QQApiError("Failed to send QQ message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise QQApiError(f"QQ send message failed: {response.status_code} {response.text}")
        if not response.content:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def send_reply(self, event: dict[str, Any], text: str) -> dict[str, Any]:
        msg_id = str(event["id"]) if event.get("id") is not None else None
        event_id = str(event["event_id"]) if event.get("event_id") is not None else None

        if event.get("group_openid"):
            return await self.send_text(
                f"/v2/groups/{event['group_openid']}/messages",
                text,
                msg_id=msg_id,
                event_id=event_id,
            )
        if event.get("channel_id"):
            return await self.send_text(
                f"/channels/{event['channel_id']}/messages",
                text,
                msg_id=msg_id,
                event_id=event_id,
            )
        if event.get("guild_id"):
            return await self.send_text(
                f"/dms/{event['guild_id']}/messages",
                text,
                msg_id=msg_id,
                event_id=event_id,
            )
        author = event.get("author")
        if isinstance(author, dict) and author.get("id"):
            return await self.send_text(
                f"/v2/users/{author['id']}/messages",
                text,
                msg_id=msg_id,
                event_id=event_id,
            )

        raise QQApiError("QQ reply requires group_openid, author.id, channel_id, or guild_id")


def _truncate_text(text: str) -> str:
    if len(text) > MAX_QQ_TEXT_LENGTH:
        return text[: MAX_QQ_TEXT_LENGTH - 3] + "..."
    return text
