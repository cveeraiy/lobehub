"""Notifications router — list, mark read, archive."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.misc import Notification

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class MarkReadBody(BaseModel):
    ids: list[str]


@router.get("/count")
async def count_notifications(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    total = (await session.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    )).scalar_one()
    unread = (await session.execute(
        select(func.count()).select_from(Notification).where(
            and_(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
    )).scalar_one()
    return {"total": total, "unread": unread}


@router.get("/unread-count")
async def unread_count(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return (await session.execute(
        select(func.count()).select_from(Notification).where(
            and_(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
    )).scalar_one()


@router.get("")
async def list_notifications(
    category: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    offset: int = 0,
    unreadOnly: bool | None = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    conditions = [Notification.user_id == user_id]
    if category:
        conditions.append(Notification.category == category)
    if unreadOnly:
        conditions.append(Notification.read_at.is_(None))

    if cursor:
        cursor_row = (await session.execute(
            select(Notification.created_at, Notification.id).where(
                and_(Notification.id == cursor, Notification.user_id == user_id)
            )
        )).first()
        if cursor_row:
            cursor_time, cursor_id = cursor_row
            conditions.append(
                or_(
                    Notification.created_at < cursor_time,
                    and_(Notification.created_at == cursor_time, Notification.id < cursor_id),
                )
            )

    stmt = (
        select(Notification)
        .where(and_(*conditions))
        .order_by(desc(Notification.created_at), desc(Notification.id))
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
        .values(read_at=_utcnow(), updated_at=_utcnow())
    )
    return {"ok": True}


@router.put("/read")
async def mark_read_many(
    body: MarkReadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if body.ids:
        await session.execute(
            update(Notification)
            .where(and_(Notification.user_id == user_id, Notification.id.in_(body.ids)))
            .values(read_at=_utcnow(), updated_at=_utcnow())
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
        .values(read_at=_utcnow(), updated_at=_utcnow())
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


@router.delete("")
async def remove_all_notifications(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(Notification).where(Notification.user_id == user_id)
    )
    return {"ok": True}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _notif_dict(n: Notification) -> dict[str, Any]:
    created_at = n.created_at.isoformat() if n.created_at else None
    updated_at = n.updated_at.isoformat() if n.updated_at else None
    metadata = n.metadata_ or {}
    return {
        "actionUrl": metadata.get("actionUrl") or metadata.get("action_url"),
        "category": n.category,
        "content": n.body or "",
        "createdAt": created_at,
        "id": n.id,
        "isArchived": False,
        "isRead": n.read_at is not None,
        "title": n.title,
        "type": metadata.get("type") or n.category or "system",
        "updatedAt": updated_at,
        # Backward-compatible snake_case aliases for existing Python callers.
        "body": n.body,
        "created_at": created_at,
        "metadata": metadata,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "updated_at": updated_at,
    }
