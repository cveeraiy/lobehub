"""Agent Bot Provider router — CRUD for bot platform integrations.

Mirrors TS: src/server/routers/lambda/agentBotProvider.ts
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent_ops import AgentBotProvider
from app.services.bot.platforms import platform_registry
from app.services.key_vault.service import KeyVaultService

router = APIRouter(prefix="/api/agent-bot-providers", tags=["Agent Bot Providers"])


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _decode_credentials(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        value = KeyVaultService.from_env().decrypt_json(raw)
        if isinstance(value, dict) and value:
            return {str(key): str(val) for key, val in value.items()}
    except (RuntimeError, ValueError):
        pass
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items()}


def _encode_credentials(credentials: dict[str, str] | None) -> str | None:
    if credentials is None:
        return None
    try:
        return KeyVaultService.from_env().encrypt_json(credentials)
    except (RuntimeError, ValueError):
        pass
    return json.dumps(credentials)


def _serialize(row: AgentBotProvider) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "user_id": row.user_id,
        "platform": row.platform,
        "application_id": row.application_id,
        "credentials": _decode_credentials(row.credentials),
        "settings": row.settings,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ── Schemas ──────────────────────────────────────────────────────────

class CreateBotProviderBody(BaseModel):
    agent_id: str
    application_id: str
    platform: str
    credentials: dict[str, str] | None = None
    settings: dict[str, Any] | None = None
    enabled: bool = True


class UpdateBotProviderBody(BaseModel):
    application_id: str | None = None
    platform: str | None = None
    credentials: dict[str, str] | None = None
    settings: dict[str, Any] | None = None
    enabled: bool | None = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/platforms/list")
async def list_platforms(
    user_id: str = Depends(get_current_user_id),
):
    """List Python-migrated bot platforms with frontend form schemas."""
    return platform_registry.list_serialized()


@router.get("")
async def list_bot_providers(
    agent_id: str | None = None,
    platform: str | None = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List bot providers, optionally filtered by agent_id or platform."""
    stmt = select(AgentBotProvider).where(AgentBotProvider.user_id == user_id)
    if agent_id:
        stmt = stmt.where(AgentBotProvider.agent_id == agent_id)
    if platform:
        stmt = stmt.where(AgentBotProvider.platform == platform)
    stmt = stmt.order_by(AgentBotProvider.created_at.desc())

    rows = (await session.execute(stmt)).scalars().all()
    return [_serialize(r) for r in rows]


@router.get("/by-agent/{agent_id}")
async def get_by_agent_id(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get all bot providers for a specific agent."""
    stmt = (
        select(AgentBotProvider)
        .where(
            and_(
                AgentBotProvider.user_id == user_id,
                AgentBotProvider.agent_id == agent_id,
            )
        )
        .order_by(AgentBotProvider.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_serialize(r) for r in rows]


@router.get("/{provider_id}")
async def get_bot_provider(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get a single bot provider by ID."""
    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.id == provider_id,
            AgentBotProvider.user_id == user_id,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot provider not found")
    return _serialize(row)


@router.post("", status_code=201)
async def create_bot_provider(
    body: CreateBotProviderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a new bot provider."""
    try:
        platform = platform_registry.require(body.platform)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    now = _now()
    provider = AgentBotProvider(
        agent_id=body.agent_id,
        user_id=user_id,
        platform=body.platform,
        application_id=body.application_id,
        credentials=_encode_credentials(body.credentials),
        settings=platform.merge_settings(body.settings),
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
        accessed_at=now,
    )
    session.add(provider)
    try:
        await session.commit()
        await session.refresh(provider)
    except Exception as exc:
        await session.rollback()
        # Unique constraint violation
        if "23505" in str(exc) or "UniqueViolation" in str(exc) or "duplicate key" in str(exc):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                (
                    f"A bot provider for platform '{body.platform}' and application "
                    f"'{body.application_id}' already exists."
                ),
            )
        raise
    return _serialize(provider)


@router.patch("/{provider_id}")
async def update_bot_provider(
    provider_id: str,
    body: UpdateBotProviderBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update a bot provider."""
    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.id == provider_id,
            AgentBotProvider.user_id == user_id,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot provider not found")

    updates = body.model_dump(exclude_unset=True)
    platform_id = updates.get("platform") or row.platform
    try:
        platform = platform_registry.require(platform_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if "settings" in updates:
        updates["settings"] = platform.merge_settings(updates["settings"])
    if "credentials" in updates:
        updates["credentials"] = _encode_credentials(updates["credentials"])
    for key, value in updates.items():
        setattr(row, key, value)
    row.updated_at = _now()

    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _serialize(row)


@router.delete("/{provider_id}")
async def delete_bot_provider(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a bot provider."""
    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.id == provider_id,
            AgentBotProvider.user_id == user_id,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot provider not found")

    await session.delete(row)
    await session.commit()
    return {"success": True}


@router.post("/{provider_id}/connect")
async def connect_bot(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Start/connect a bot provider."""
    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.id == provider_id,
            AgentBotProvider.user_id == user_id,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot provider not found")

    definition = platform_registry.get(row.platform)
    if definition is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported bot platform: {row.platform}")
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        f"Python runtime for {definition.name} {definition.connection_mode} connections is not implemented yet.",
    )


@router.post("/{provider_id}/test")
async def test_connection(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Test a bot provider's credentials through the Python platform registry."""
    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.id == provider_id,
            AgentBotProvider.user_id == user_id,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot provider not found")

    definition = platform_registry.get(row.platform)
    if definition is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported bot platform: {row.platform}")

    result = await definition.validate_credentials(
        _decode_credentials(row.credentials),
        row.settings,
        row.application_id,
    )
    if not result.valid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, result.to_dict())

    return result.to_dict()


@router.get("/runtime-status/get")
async def get_runtime_status(
    application_id: str,
    platform: str,
    user_id: str = Depends(get_current_user_id),
):
    """Return Python runtime status for a bot provider.

    Discord is registered for provider management first; its Python gateway is
    not implemented in this migration slice, so it reports disconnected.
    """
    if platform_registry.get(platform) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported bot platform: {platform}")
    return {
        "application_id": application_id,
        "platform": platform,
        "status": "disconnected",
        "updated_at": int(datetime.now(UTC).timestamp() * 1000),
    }


@router.post("/runtime-status/refresh")
async def refresh_runtime_status(
    body: dict[str, str],
    user_id: str = Depends(get_current_user_id),
):
    application_id = body.get("application_id")
    platform = body.get("platform")
    if not application_id or not platform:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "application_id and platform are required")
    return await get_runtime_status(application_id=application_id, platform=platform, user_id=user_id)


@router.post("/runtime-status/refresh-by-agent/{agent_id}")
async def refresh_runtime_statuses_by_agent(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
):
    return {"success": True}
