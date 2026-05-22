"""OAuth device-flow endpoints for provider authentication."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.ai_infra import AiProvider
from app.services.key_vault.service import KeyVaultService

router = APIRouter(prefix="/api/oauth-device-flow", tags=["OAuth Device Flow"])

GITHUB_COPILOT_CONFIG = {
    "clientId": "Iv1.b507a08c87ecfe98",
    "defaultPollingInterval": 5,
    "deviceCodeEndpoint": "https://github.com/login/device/code",
    "scopes": ["read:user"],
    "tokenEndpoint": "https://github.com/login/oauth/access_token",
    "tokenExchangeEndpoint": "https://api.github.com/copilot_internal/v2/token",
}


class ProviderBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: str = Field(alias="providerId")


class PollBody(ProviderBody):
    device_code: str = Field(alias="deviceCode")


def _camel(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "deviceCode": data.get("device_code"),
        "expiresIn": data.get("expires_in"),
        "interval": data.get("interval"),
        "userCode": data.get("user_code"),
        "verificationUri": data.get("verification_uri") or data.get("verification_url"),
    }


async def _provider(session: AsyncSession, user_id: str, provider_id: str) -> AiProvider | None:
    return (
        await session.execute(
            select(AiProvider).where(and_(AiProvider.user_id == user_id, AiProvider.id == provider_id))
        )
    ).scalar_one_or_none()


async def _get_or_create_provider(session: AsyncSession, user_id: str, provider_id: str) -> AiProvider:
    provider = await _provider(session, user_id, provider_id)
    if provider is not None:
        return provider
    provider = AiProvider(id=provider_id, user_id=user_id, name=provider_id, source="builtin", enabled=True)
    session.add(provider)
    await session.flush()
    return provider


def _flow_config(provider: AiProvider | None, provider_id: str) -> dict[str, Any] | None:
    if provider_id == "githubcopilot":
        return GITHUB_COPILOT_CONFIG
    configured = (provider.settings or {}).get("oauthDeviceFlow") if provider else None
    return configured if isinstance(configured, dict) else None


def _decode_key_vaults(provider: AiProvider | None) -> dict[str, Any]:
    if not provider or not provider.key_vaults:
        return {}
    if settings.key_vaults_secret:
        return KeyVaultService.from_env().decrypt_json(provider.key_vaults)
    try:
        return json.loads(provider.key_vaults)
    except json.JSONDecodeError:
        return {}


def _encode_key_vaults(values: dict[str, Any]) -> str:
    if settings.key_vaults_secret:
        return KeyVaultService.from_env().encrypt_json(values)
    return json.dumps(values)


@router.get("/auth-status")
async def get_auth_status(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = await _provider(session, user_id, provider_id)
    vaults = _decode_key_vaults(provider)
    expires_at = (
        vaults.get("oauthAccessTokenExpiresAt")
        or vaults.get("oauthTokenExpiresAt")
        or vaults.get("bearerTokenExpiresAt")
    )
    return {
        "avatarUrl": (
            vaults.get("githubUserInfo", {}).get("avatarUrl")
            or vaults.get("githubAvatarUrl")
            or vaults.get("avatarUrl")
        ),
        "expiresAt": expires_at,
        "isAuthenticated": bool(vaults.get("oauthAccessToken") or vaults.get("bearerToken")),
        "username": (
            vaults.get("githubUserInfo", {}).get("username")
            or vaults.get("githubUsername")
            or vaults.get("username")
        ),
    }


@router.post("/initiate-device-code")
async def initiate_device_code(
    body: ProviderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = await _get_or_create_provider(session, user_id, body.provider_id)
    config = _flow_config(provider, body.provider_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider does not support OAuth device flow")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            str(config["deviceCodeEndpoint"]),
            data={"client_id": config["clientId"], "scope": " ".join(config.get("scopes") or [])},
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text)
    data = response.json()
    data.setdefault("interval", config.get("defaultPollingInterval", 5))
    return _camel(data)


@router.post("/poll-auth-status")
async def poll_auth_status(
    body: PollBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = await _get_or_create_provider(session, user_id, body.provider_id)
    config = _flow_config(provider, body.provider_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider does not support OAuth device flow")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            str(config["tokenEndpoint"]),
            data={
                "client_id": config["clientId"],
                "device_code": body.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        )
        token_data = response.json()
        if token_data.get("error"):
            return {"status": _oauth_error_status(str(token_data["error"]))}
        if not token_data.get("access_token"):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Unexpected OAuth token response")

        oauth_token = str(token_data["access_token"])
        vaults = _decode_key_vaults(provider)
        expires_at = _expires_at(token_data.get("expires_in"))
        vaults.update(
            {
                "oauthAccessToken": oauth_token,
                "oauthAccessTokenExpiresAt": expires_at,
                "oauthScope": token_data.get("scope"),
                "oauthTokenType": token_data.get("token_type") or "bearer",
            }
        )

        if body.provider_id == "githubcopilot":
            user_info, copilot = await _complete_github_copilot(client, config, oauth_token)
            vaults.update(
                {
                    "bearerToken": copilot["token"],
                    "bearerTokenExpiresAt": copilot["expiresAt"],
                    "githubUserInfo": user_info,
                }
            )

    provider.key_vaults = _encode_key_vaults(vaults)
    provider.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(provider)
    await session.flush()
    return {"status": "success"}


@router.post("/revoke-auth")
async def revoke_auth(
    body: ProviderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = await _provider(session, user_id, body.provider_id)
    if provider is None:
        return {"success": True}
    vaults = _decode_key_vaults(provider)
    for key in [
        "apiKey",
        "bearerToken",
        "bearerTokenExpiresAt",
        "githubAvatarUrl",
        "githubUserInfo",
        "githubUsername",
        "oauthAccessToken",
        "oauthAccessTokenExpiresAt",
        "oauthScope",
        "oauthTokenType",
        "oauthTokenExpiresAt",
    ]:
        vaults.pop(key, None)
    provider.key_vaults = _encode_key_vaults(vaults)
    provider.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(provider)
    await session.flush()
    return {"success": True}


def _oauth_error_status(error: str) -> str:
    return {
        "access_denied": "denied",
        "authorization_pending": "pending",
        "expired_token": "expired",
        "slow_down": "slow_down",
    }.get(error, "pending")


def _expires_at(expires_in: Any) -> int | None:
    if expires_in is None:
        return None
    return int((datetime.now(UTC) + timedelta(seconds=int(expires_in))).timestamp() * 1000)


async def _complete_github_copilot(
    client: httpx.AsyncClient,
    config: dict[str, Any],
    oauth_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    headers = {"Accept": "application/json", "Authorization": f"token {oauth_token}", "User-Agent": "Ethos/1.0"}
    user_response = await client.get("https://api.github.com/user", headers=headers)
    user_response.raise_for_status()
    user_json = user_response.json()
    token_response = await client.get(str(config["tokenExchangeEndpoint"]), headers=headers)
    token_response.raise_for_status()
    token_json = token_response.json()
    return (
        {"avatarUrl": user_json.get("avatar_url") or "", "username": user_json.get("login") or ""},
        {"expiresAt": int(token_json["expires_at"]) * 1000, "token": token_json["token"]},
    )
