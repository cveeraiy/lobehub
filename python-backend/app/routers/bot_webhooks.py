"""Unauthenticated inbound bot webhook routes.

Mirrors TS: src/handlers/api/agent/webhooks/[platform]/[[...appId]]/route.ts
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.agent_ops import AgentBotProvider
from app.routers.agent_bot_providers import _decode_credentials
from app.services.bot.bridge import bot_bridge
from app.services.bot.inbound import normalize_inbound_webhook
from app.services.bot.platforms import platform_registry
from app.services.bot.platforms.teams.client import BotFrameworkAuthError, validate_bot_framework_authorization
from app.services.bot.platforms.webex.client import WebexApiError, WebexClient
from app.services.bot.runtime_status import update_bot_runtime_status

router = APIRouter(prefix="/api/agent/webhooks", tags=["Bot Webhooks"])


@router.post("/bot-callback")
async def handle_bot_callback():
    """Retired TS queue callback transport.

    Python bot webhooks enqueue work directly through the bot bridge, so the
    old TS callback endpoint is intentionally not active.
    """
    raise HTTPException(
        status.HTTP_410_GONE,
        "Bot callback transport is retired; use platform webhook endpoints instead",
    )


def _decrypt_lark_event(encrypted: str, encrypt_key: str) -> dict[str, Any]:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(encrypt_key.encode())
    key = digest.finalize()
    encrypted_body = base64.b64decode(encrypted)
    iv = encrypted_body[:16]
    ciphertext = encrypted_body[16:]
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    value = json.loads(plaintext.decode())
    if not isinstance(value, dict):
        raise ValueError("decrypted event must be an object")
    return value


def _sign_qq_webhook_response(event_ts: str, plain_token: str, app_secret: str) -> str:
    seed_text = app_secret
    while len(seed_text) < 32:
        seed_text = seed_text * 2
    seed = seed_text[:32].encode()
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    return private_key.sign((event_ts + plain_token).encode()).hex()


@router.post("/{platform}/{application_id}")
async def handle_bot_webhook(
    platform: str,
    application_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    x_line_signature: str | None = Header(default=None),
    x_slack_request_timestamp: str | None = Header(default=None),
    x_slack_signature: str | None = Header(default=None),
    x_spark_signature: str | None = Header(default=None),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if platform_registry.get(platform) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bot configured for this platform")

    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.platform == platform,
            AgentBotProvider.application_id == application_id,
            AgentBotProvider.enabled.is_(True),
        )
    )
    provider = (await session.execute(stmt)).scalars().first()
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No bot configured for {platform}")

    credentials = _decode_credentials(provider.credentials)
    if platform == "telegram":
        expected_secret = credentials.get("secretToken")
        if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Telegram secret token")
    raw_body = await request.body()
    if platform == "line":
        channel_secret = credentials.get("channelSecret")
        if not channel_secret:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "LINE channel secret is not configured")
        digest = hmac.new(channel_secret.encode(), raw_body, hashlib.sha256).digest()
        expected_signature = base64.b64encode(digest).decode()
        if not x_line_signature or not hmac.compare_digest(x_line_signature, expected_signature):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid LINE signature")
    if platform == "slack":
        signing_secret = credentials.get("signingSecret")
        if not signing_secret:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Slack signing secret is not configured")
        if not x_slack_request_timestamp or not x_slack_signature:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Slack signature headers")
        base_string = b"v0:" + x_slack_request_timestamp.encode() + b":" + raw_body
        digest = hmac.new(signing_secret.encode(), base_string, hashlib.sha256).hexdigest()
        expected_signature = f"v0={digest}"
        if not hmac.compare_digest(x_slack_signature, expected_signature):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Slack signature")
    if platform == "webex":
        webhook_secret = credentials.get("webhookSecret")
        if not webhook_secret:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Webex webhook secret is not configured")
        expected_signature = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha1).hexdigest()
        if not x_spark_signature or not hmac.compare_digest(x_spark_signature, expected_signature):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Webex signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Webhook payload must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Webhook payload must be a JSON object")
    if platform in {"feishu", "lark"} and payload.get("encrypt"):
        encrypt_key = credentials.get("encryptKey")
        if not encrypt_key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Encrypted event but no encrypt key configured")
        try:
            payload = _decrypt_lark_event(str(payload["encrypt"]), encrypt_key)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Decryption failed") from exc
    if platform in {"feishu", "lark"}:
        verification_token = credentials.get("verificationToken")
        if verification_token:
            header = payload.get("header")
            token = header.get("token") if isinstance(header, dict) else payload.get("token")
            if token != verification_token:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid verification token")
    if platform == "qq" and payload.get("op") == 13:
        data = payload.get("d")
        if not isinstance(data, dict) or not data.get("event_ts") or not data.get("plain_token"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing QQ verification data")
        app_secret = credentials.get("appSecret")
        if not app_secret:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "QQ app secret is not configured")
        plain_token = str(data["plain_token"])
        return {
            "plain_token": plain_token,
            "signature": _sign_qq_webhook_response(str(data["event_ts"]), plain_token, app_secret),
        }
    if platform == "teams":
        try:
            await validate_bot_framework_authorization(
                authorization,
                app_id=application_id,
                service_url=payload.get("serviceUrl") if isinstance(payload.get("serviceUrl"), str) else None,
            )
        except BotFrameworkAuthError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if platform == "webex":
        data = payload.get("data")
        message_id = data.get("id") if isinstance(data, dict) else None
        has_content = isinstance(data, dict) and (
            isinstance(data.get("text"), str)
            or isinstance(data.get("markdown"), str)
            or isinstance(data.get("files"), list)
            or isinstance(data.get("attachments"), list)
        )
        bot_token = credentials.get("botToken")
        if message_id and not has_content and isinstance(bot_token, str) and bot_token:
            try:
                message = await WebexClient(bot_token).get_message(str(message_id))
            except WebexApiError as exc:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
            payload = {**payload, "data": {**data, **message}}

    result = normalize_inbound_webhook(platform, application_id, payload)
    if platform == "slack" and result.reason == "url_verification":
        challenge = payload.get("challenge")
        return {"challenge": challenge}
    if platform in {"feishu", "lark"} and result.reason == "url_verification":
        challenge = payload.get("challenge")
        return {"challenge": challenge}
    if result.status == "accepted":
        update_bot_runtime_status(platform, application_id, "connected")
        if result.message is not None:
            dispatch = await bot_bridge.enqueue(
                provider,
                result.message,
                credentials,
                background_tasks=background_tasks,
            )
            response = result.to_dict()
            response["dispatch"] = dispatch.to_dict()
            return response

    return result.to_dict()
