"""Session Groups router — manages conversation/session grouping.

This is separate from agent groups — it manages session_groups directly
for organizing sessions (conversations) into folders.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.session import Session, SessionGroup

router = APIRouter(prefix="/api/session-groups", tags=["Session Groups"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CreateSessionGroupBody(BaseModel):
    name: str
    sort: Optional[int] = None


class UpdateSessionGroupBody(BaseModel):
    name: Optional[str] = None
    sort: Optional[int] = None


@router.get("")
async def list_session_groups(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SessionGroup)
        .where(SessionGroup.user_id == user_id)
        .order_by(SessionGroup.sort)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_group_dict(g) for g in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session_group(
    body: CreateSessionGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    group = SessionGroup(
        user_id=user_id,
        name=body.name,
        sort=body.sort,
    )
    session.add(group)
    await session.flush()
    return {"id": group.id}


@router.put("/{group_id}")
async def update_session_group(
    group_id: str,
    body: UpdateSessionGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(SessionGroup)
        .where(and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/{group_id}")
async def delete_session_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Unset group on any sessions in this group
    await session.execute(
        update(Session)
        .where(and_(Session.group_id == group_id, Session.user_id == user_id))
        .values(group_id=None)
    )
    await session.execute(
        delete(SessionGroup).where(and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id))
    )
    return {"ok": True}


@router.put("/{group_id}/sessions/{session_id}")
async def assign_session_to_group(
    group_id: str,
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Session)
        .where(and_(Session.id == session_id, Session.user_id == user_id))
        .values(group_id=group_id)
    )
    return {"ok": True}


@router.delete("/{group_id}/sessions/{session_id}")
async def remove_session_from_group(
    group_id: str,
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Session)
        .where(and_(Session.id == session_id, Session.user_id == user_id, Session.group_id == group_id))
        .values(group_id=None)
    )
    return {"ok": True}


def _group_dict(g: SessionGroup) -> dict[str, Any]:
    return {
        "id": g.id,
        "name": g.name,
        "sort": g.sort,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
