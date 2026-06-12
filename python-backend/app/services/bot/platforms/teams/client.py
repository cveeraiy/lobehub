from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import JWTError, jwt

from app.services.bot.platforms.teams.definition import MICROSOFT_BOT_SCOPE, MICROSOFT_BOT_TOKEN_URL

BOT_FRAMEWORK_OPENID_CONFIG_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"
BOT_FRAMEWORK_ISSUER = "https://api.botframework.com"


class BotFrameworkAuthError(ValueError):
    pass


_openid_cache: dict[str, Any] | None = None
_openid_cache_at = 0.0
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_at = 0.0
_access_token_cache: dict[tuple[str, str], tuple[str, float]] = {}
_CACHE_TTL_SECONDS = 3600


async def _get_openid_metadata(client: httpx.AsyncClient) -> dict[str, Any]:
    global _openid_cache, _openid_cache_at
    if _openid_cache and time.monotonic() - _openid_cache_at < _CACHE_TTL_SECONDS:
        return _openid_cache

    response = await client.get(BOT_FRAMEWORK_OPENID_CONFIG_URL)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data.get("jwks_uri"):
        raise BotFrameworkAuthError("Bot Framework OpenID metadata is invalid")
    _openid_cache = data
    _openid_cache_at = time.monotonic()
    return data


async def _get_openid_keys(client: httpx.AsyncClient) -> dict[str, Any]:
    global _jwks_cache, _jwks_cache_at
    if _jwks_cache and time.monotonic() - _jwks_cache_at < _CACHE_TTL_SECONDS:
        return _jwks_cache

    metadata = await _get_openid_metadata(client)
    response = await client.get(str(metadata["jwks_uri"]))
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
        raise BotFrameworkAuthError("Bot Framework JWKS document is invalid")
    _jwks_cache = data
    _jwks_cache_at = time.monotonic()
    return data


async def validate_bot_framework_authorization(
    authorization: str | None,
    *,
    app_id: str,
    service_url: str | None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise BotFrameworkAuthError("Missing Bot Framework bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise BotFrameworkAuthError("Missing Bot Framework bearer token")

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10)
    assert client is not None
    try:
        jwks = await _get_openid_keys(client)
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=app_id,
            issuer=BOT_FRAMEWORK_ISSUER,
            options={"verify_at_hash": False},
        )
    except (JWTError, httpx.HTTPError) as exc:
        raise BotFrameworkAuthError(f"Invalid Bot Framework bearer token: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    token_service_url = payload.get("serviceUrl")
    if service_url and token_service_url and token_service_url != service_url:
        raise BotFrameworkAuthError("Bot Framework token serviceUrl does not match activity")
    return payload


@dataclass(frozen=True)
class TeamsConnectorClient:
    app_id: str
    app_password: str

    async def get_access_token(self, client: httpx.AsyncClient | None = None) -> str:
        cache_key = (self.app_id, self.app_password)
        cached = _access_token_cache.get(cache_key)
        now = time.monotonic()
        if cached and cached[1] > now:
            return cached[0]

        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=10)
        assert client is not None
        try:
            response = await client.post(
                MICROSOFT_BOT_TOKEN_URL,
                data={
                    "client_id": self.app_id,
                    "client_secret": self.app_password,
                    "grant_type": "client_credentials",
                    "scope": MICROSOFT_BOT_SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if owns_client:
                await client.aclose()

        token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise BotFrameworkAuthError("Microsoft token response did not include access_token")
        expires_in = data.get("expires_in", 3600) if isinstance(data, dict) else 3600
        _access_token_cache[cache_key] = (token, now + max(int(expires_in) - 300, 60))
        return token

    async def send_reply(
        self,
        activity: dict[str, Any],
        text: str,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        service_url = str(activity["serviceUrl"]).rstrip("/")
        conversation = activity["conversation"]
        conversation_id = conversation["id"]
        activity_id = activity["id"]
        token = await self.get_access_token(client)
        payload = {
            "type": "message",
            "text": text,
            "from": activity.get("recipient"),
            "recipient": activity.get("from"),
            "replyToId": activity_id,
        }
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=10)
        assert client is not None
        try:
            response = await client.post(
                f"{service_url}/v3/conversations/{conversation_id}/activities/{activity_id}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
            return data if isinstance(data, dict) else {}
        finally:
            if owns_client:
                await client.aclose()
