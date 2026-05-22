from __future__ import annotations

import base64
import random
import uuid
from typing import Any

import httpx

WECHAT_API_BASE = "https://ilinkai.weixin.qq.com"
MAX_WECHAT_TEXT_LENGTH = 2000


class WechatApiError(RuntimeError):
    pass


def _random_uin() -> str:
    return base64.b64encode(str(random.randint(0, 0xFFFF_FFFF)).encode()).decode()


def _chunk_text(text: str) -> list[str]:
    if not text:
        return [""]
    return [text[index : index + MAX_WECHAT_TEXT_LENGTH] for index in range(0, len(text), MAX_WECHAT_TEXT_LENGTH)]


async def fetch_qr_code(
    *,
    api_base: str = WECHAT_API_BASE,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=15)
    try:
        response = await http_client.get(
            f"{api_base.rstrip('/')}/ilink/bot/get_bot_qrcode",
            params={"bot_type": 3},
        )
        if not response.is_success:
            raise WechatApiError(f"iLink get_bot_qrcode failed: {response.status_code} {response.text}")
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            raise WechatApiError("iLink get_bot_qrcode returned an invalid response")
        return payload
    except httpx.HTTPError as exc:
        raise WechatApiError("Failed to fetch WeChat QR code") from exc
    finally:
        if close_client:
            await http_client.aclose()


async def poll_qr_status(
    qrcode: str,
    *,
    api_base: str = WECHAT_API_BASE,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    close_client = client is None
    http_client = client or httpx.AsyncClient(timeout=15)
    try:
        response = await http_client.get(
            f"{api_base.rstrip('/')}/ilink/bot/get_qrcode_status",
            headers={"iLink-App-ClientVersion": "1"},
            params={"qrcode": qrcode},
        )
        if not response.is_success:
            raise WechatApiError(f"iLink get_qrcode_status failed: {response.status_code} {response.text}")
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict):
            raise WechatApiError("iLink get_qrcode_status returned an invalid response")
        return payload
    except httpx.HTTPError as exc:
        raise WechatApiError("Failed to poll WeChat QR status") from exc
    finally:
        if close_client:
            await http_client.aclose()


class WechatClient:
    def __init__(self, bot_token: str, *, api_base: str = WECHAT_API_BASE) -> None:
        self.bot_token = bot_token
        self.api_base = api_base.rstrip("/")

    async def send_message(
        self,
        to_user_id: str,
        text: str,
        context_token: str = "",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        close_client = client is None
        http_client = client or httpx.AsyncClient(timeout=15)
        last_payload: dict[str, Any] = {"ret": 0}
        try:
            for chunk in _chunk_text(text):
                response = await http_client.post(
                    f"{self.api_base}/ilink/bot/sendmessage",
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "AuthorizationType": "ilink_bot_token",
                        "Content-Type": "application/json",
                        "X-WECHAT-UIN": _random_uin(),
                    },
                    json={
                        "base_info": {"channel_version": "1.0.0"},
                        "msg": {
                            "client_id": str(uuid.uuid4()),
                            "context_token": context_token,
                            "from_user_id": "",
                            "item_list": [{"text_item": {"text": chunk}, "type": 1}],
                            "message_state": 2,
                            "message_type": 2,
                            "to_user_id": to_user_id,
                        },
                    },
                )
                if not response.is_success:
                    raise WechatApiError(f"WeChat sendmessage failed: {response.status_code} {response.text}")
                payload = response.json() if response.content else {}
                if isinstance(payload, dict):
                    ret = payload.get("ret")
                    if isinstance(ret, int) and ret != 0:
                        raise WechatApiError(str(payload.get("errmsg") or f"WeChat sendmessage failed: ret={ret}"))
                    last_payload = payload
        except httpx.HTTPError as exc:
            raise WechatApiError("Failed to send WeChat message") from exc
        finally:
            if close_client:
                await http_client.aclose()

        return last_payload

    async def send_reply(self, event: dict[str, Any], text: str) -> dict[str, Any]:
        to_user_id = event.get("from_user_id")
        if not isinstance(to_user_id, str) or not to_user_id:
            raise WechatApiError("WeChat reply requires from_user_id")
        context_token = event.get("context_token")
        return await self.send_message(
            to_user_id,
            text,
            context_token if isinstance(context_token, str) else "",
        )
