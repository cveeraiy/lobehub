from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.services.bot.platforms.feishu.definition import FEISHU_API_BASE, LARK_API_BASE

MAX_FEISHU_TEXT_LENGTH = 4000


class FeishuApiError(RuntimeError):
    pass


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, platform: str = "feishu") -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_base = LARK_API_BASE if platform == "lark" else FEISHU_API_BASE
        self._tenant_access_token: str | None = None
        self._tenant_access_token_expires_at = 0.0

    async def get_tenant_access_token(self, client: httpx.AsyncClient | None = None) -> str:
        if self._tenant_access_token and time.time() < self._tenant_access_token_expires_at:
            return self._tenant_access_token

        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            response = await http_client.post(
                f"{self.api_base}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
        except httpx.HTTPError as exc:
            raise FeishuApiError("Failed to authenticate with Feishu/Lark API") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise FeishuApiError(f"Feishu/Lark auth failed: {response.status_code} {response.text}")
        data = response.json()
        if not isinstance(data, dict) or data.get("code") != 0 or not data.get("tenant_access_token"):
            raise FeishuApiError(f"Feishu/Lark auth failed: {data.get('code')} {data.get('msg')}".strip())

        self._tenant_access_token = str(data["tenant_access_token"])
        expires_in = data.get("expire")
        self._tenant_access_token_expires_at = time.time() + max(int(expires_in or 7200) - 300, 60)
        return self._tenant_access_token

    async def reply_message(
        self,
        message_id: str,
        text: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10)
        try:
            token = await self.get_tenant_access_token(http_client)
            response = await http_client.post(
                f"{self.api_base}/im/v1/messages/{message_id}/reply",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "content": json.dumps({"text": _truncate_text(text)}),
                    "msg_type": "text",
                },
            )
        except httpx.HTTPError as exc:
            raise FeishuApiError("Failed to reply to Feishu/Lark message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        if not response.is_success:
            raise FeishuApiError(f"Feishu/Lark reply failed: {response.status_code} {response.text}")
        data = response.json()
        if not isinstance(data, dict) or data.get("code") != 0:
            raise FeishuApiError(f"Feishu/Lark reply failed: {data.get('code')} {data.get('msg')}".strip())
        return data

    async def send_reply(self, event_message: dict[str, Any], text: str) -> dict[str, Any]:
        message_id = event_message.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            raise FeishuApiError("Feishu/Lark reply requires message_id")
        return await self.reply_message(message_id, text)


def _truncate_text(text: str) -> str:
    if len(text) > MAX_FEISHU_TEXT_LENGTH:
        return text[: MAX_FEISHU_TEXT_LENGTH - 3] + "..."
    return text
