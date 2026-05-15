"""Notifications router — list, mark read, dismiss."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.misc import Notification

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
async def list_notifications(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_notif_dict(n) for n in rows]


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Notification)
        .where(and_(Notification.id == notification_id, Notification.user_id == user_id))
        .values(read_at=datetime.now(timezone.utc))
    )
    return {"ok": True}


@router.put("/read-all")
async def mark_all_read(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Notification)
        .where(and_(Notification.user_id == user_id, Notification.read_at.is_(None)))
        .values(read_at=datetime.now(timezone.utc))
    )
    return {"ok": True}


@router.delete("/{notification_id}")
async def dismiss_notification(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(Notification)
        .where(and_(Notification.id == notification_id, Notification.user_id == user_id))
    )
    return {"ok": True}


def _notif_dict(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "category": n.category,
        "metadata": n.metadata_,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
