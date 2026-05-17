"""Agent Bot Provider router — CRUD for bot platform integrations.

Mirrors TS: src/server/routers/lambda/agentBotProvider.ts
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent_ops import AgentBotProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-bot-providers", tags=["Agent Bot Providers"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize(row: AgentBotProvider) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "user_id": row.user_id,
        "platform": row.platform,
        "credentials": row.credentials,
        "settings": row.settings,
        "webhook_url": row.webhook_url,
        "webhook_secret": row.webhook_secret,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ── Schemas ──────────────────────────────────────────────────────────

class CreateBotProviderBody(BaseModel):
    agent_id: str
    application_id: Optional[str] = None
    platform: str
    credentials: Optional[dict[str, str]] = None
    settings: Optional[dict[str, Any]] = None
    enabled: bool = True


class UpdateBotProviderBody(BaseModel):
    application_id: Optional[str] = None
    platform: Optional[str] = None
    credentials: Optional[dict[str, str]] = None
    settings: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/platforms/list")
async def list_platforms(
    user_id: str = Depends(get_current_user_id),
):
    """List available bot platforms.

    Note: Returns a static list. The TS backend uses a platform registry
    with detailed schemas; this is a simplified version.
    """
    return {
        "platforms": [
            "discord",
            "feishu",
            "line",
            "qq",
            "slack",
            "telegram",
            "wechat",
        ]
    }


@router.get("")
async def list_bot_providers(
    agent_id: Optional[str] = None,
    platform: Optional[str] = None,
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
    now = _now()
    provider = AgentBotProvider(
        agent_id=body.agent_id,
        user_id=user_id,
        platform=body.platform,
        credentials=body.credentials,
        settings=body.settings,
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
                f"A bot provider for agent '{body.agent_id}' on platform '{body.platform}' already exists.",
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
    """Start/connect a bot provider.

    Note: In the Python backend, gateway lifecycle management is a placeholder.
    The TS backend handles actual WebSocket/polling gateway connections.
    """
    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.id == provider_id,
            AgentBotProvider.user_id == user_id,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot provider not found")

    return {"status": "queued"}


@router.post("/{provider_id}/test")
async def test_connection(
    provider_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Test a bot provider's credentials.

    Note: Full platform-specific validation requires the TS gateway infrastructure.
    This endpoint validates that the provider record exists and has credentials.
    """
    stmt = select(AgentBotProvider).where(
        and_(
            AgentBotProvider.id == provider_id,
            AgentBotProvider.user_id == user_id,
        )
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot provider not found")

    if not row.credentials:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No credentials configured")

    return {"valid": True}


