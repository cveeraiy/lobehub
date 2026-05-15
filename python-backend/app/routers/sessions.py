"""Session CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.session import Session, SessionGroup

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateSessionBody(BaseModel):
    agent_id: Optional[str] = None
    group_id: Optional[str] = None
    type: str = "agent"


class UpdateSessionBody(BaseModel):
    pinned: Optional[bool] = None
    group_id: Optional[str] = None
    slug: Optional[str] = None


class CreateGroupBody(BaseModel):
    name: str
    sort: Optional[int] = None


class UpdateGroupBody(BaseModel):
    name: Optional[str] = None
    sort: Optional[int] = None


# ── Session endpoints ────────────────────────────────────────────────

@router.get("")
async def list_sessions(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(desc(Session.pinned), desc(Session.updated_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_session_dict(r) for r in rows]


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    row = await _find_session(session, user_id, session_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return _session_dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    s = Session(user_id=user_id, **body.model_dump(exclude_none=True))
    session.add(s)
    await session.flush()
    return {"id": s.id}


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    body: UpdateSessionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(Session)
        .where(and_(Session.id == session_id, Session.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(Session).where(and_(Session.id == session_id, Session.user_id == user_id))
    )
    return {"ok": True}


# ── Session Group endpoints ──────────────────────────────────────────

@router.get("/groups/all")
async def list_groups(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SessionGroup)
        .where(SessionGroup.user_id == user_id)
        .order_by(SessionGroup.sort, SessionGroup.created_at)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [{"id": r.id, "name": r.name, "sort": r.sort} for r in rows]


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    body: CreateGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    g = SessionGroup(user_id=user_id, name=body.name, sort=body.sort)
    session.add(g)
    await session.flush()
    return {"id": g.id}


@router.put("/groups/{group_id}")
async def update_group(
    group_id: str,
    body: UpdateGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(SessionGroup)
        .where(and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Unlink sessions from this group
    await session.execute(
        update(Session)
        .where(and_(Session.group_id == group_id, Session.user_id == user_id))
        .values(group_id=None)
    )
    await session.execute(
        delete(SessionGroup).where(
            and_(SessionGroup.id == group_id, SessionGroup.user_id == user_id)
        )
    )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_session(db: AsyncSession, user_id: str, session_id: str) -> Session | None:
    stmt = select(Session).where(and_(Session.id == session_id, Session.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _session_dict(s: Session) -> dict[str, Any]:
    return {
        "id": s.id,
        "agent_id": s.agent_id,
        "group_id": s.group_id,
        "type": s.type,
        "pinned": s.pinned,
        "slug": s.slug,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
