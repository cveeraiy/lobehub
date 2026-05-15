"""Topic CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.topic import Topic

router = APIRouter(prefix="/api/topics", tags=["Topics"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateTopicBody(BaseModel):
    title: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    favorite: bool = False


class UpdateTopicBody(BaseModel):
    title: Optional[str] = None
    favorite: Optional[bool] = None
    status: Optional[str] = None
    history_summary: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_topics(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Topic).where(Topic.user_id == user_id)
    if session_id:
        stmt = stmt.where(Topic.session_id == session_id)
    if agent_id:
        stmt = stmt.where(Topic.agent_id == agent_id)
    stmt = stmt.order_by(desc(Topic.favorite), desc(Topic.updated_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_topic_dict(r) for r in rows]


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    row = await _find_topic(session, user_id, topic_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    return _topic_dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_topic(
    body: CreateTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    t = Topic(user_id=user_id, **body.model_dump(exclude_none=True))
    session.add(t)
    await session.flush()
    return {"id": t.id}


@router.put("/{topic_id}")
async def update_topic(
    topic_id: str,
    body: UpdateTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(Topic)
        .where(and_(Topic.id == topic_id, Topic.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{topic_id}")
async def delete_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(Topic).where(and_(Topic.id == topic_id, Topic.user_id == user_id))
    )
    return {"ok": True}


@router.delete("")
async def batch_delete_topics(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all topics matching filters."""
    stmt = delete(Topic).where(Topic.user_id == user_id)
    if session_id:
        stmt = stmt.where(Topic.session_id == session_id)
    if agent_id:
        stmt = stmt.where(Topic.agent_id == agent_id)
    await session.execute(stmt)
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_topic(db: AsyncSession, user_id: str, topic_id: str) -> Topic | None:
    stmt = select(Topic).where(and_(Topic.id == topic_id, Topic.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _topic_dict(t: Topic) -> dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "session_id": t.session_id,
        "agent_id": t.agent_id,
        "favorite": t.favorite,
        "status": t.status,
        "history_summary": t.history_summary,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
