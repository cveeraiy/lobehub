"""Thread router — conversation branching under topics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message
from app.models.topic_ext import Thread

router = APIRouter(prefix="/api/threads", tags=["Threads"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateThreadBody(BaseModel):
    topic_id: str
    title: Optional[str] = None
    source_message_id: Optional[str] = None
    type: Optional[str] = "standalone"
    parent_thread_id: Optional[str] = None


class UpdateThreadBody(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class CreateThreadWithMessageBody(BaseModel):
    topic_id: str
    title: Optional[str] = None
    source_message_id: Optional[str] = None
    type: Optional[str] = "standalone"
    parent_thread_id: Optional[str] = None
    id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    message: Optional[dict[str, Any]] = None


class BatchDeleteThreadsBody(BaseModel):
    ids: list[str]


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/with-message", status_code=status.HTTP_201_CREATED)
async def create_thread_with_message(
    body: CreateThreadWithMessageBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a thread and an initial message in one call."""
    thread = Thread(
        topic_id=body.topic_id,
        user_id=user_id,
        title=body.message.get("content", "")[:20] if body.message and body.message.get("content") else body.title,
        source_message_id=body.source_message_id,
        type=body.type,
        parent_thread_id=body.parent_thread_id,
    )
    if body.id:
        thread.id = body.id
    session.add(thread)
    await session.flush()

    message_id = None
    if body.message:
        msg = Message(
            user_id=user_id,
            role=body.message.get("role", "user"),
            content=body.message.get("content"),
            model=body.message.get("model"),
            provider=body.message.get("provider"),
            topic_id=body.topic_id,
            thread_id=thread.id,
            agent_id=body.message.get("agent_id"),
            session_id=body.message.get("session_id"),
        )
        session.add(msg)
        await session.flush()
        message_id = msg.id

    return {"thread_id": thread.id, "message_id": message_id}


@router.post("/remove-all")
async def remove_all_threads(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(delete(Thread).where(Thread.user_id == user_id))
    return {"ok": True}


@router.get("")
async def list_threads(
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List threads, optionally filtered by topic."""
    stmt = select(Thread).where(Thread.user_id == user_id)
    if topic_id:
        stmt = stmt.where(Thread.topic_id == topic_id)
    stmt = stmt.order_by(desc(Thread.updated_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_thread_dict(t) for t in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_thread(
    body: CreateThreadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    thread = Thread(
        topic_id=body.topic_id,
        user_id=user_id,
        title=body.title,
        source_message_id=body.source_message_id,
        type=body.type,
        parent_thread_id=body.parent_thread_id,
    )
    session.add(thread)
    await session.flush()
    return {"id": thread.id}


@router.get("/{thread_id}")
async def get_thread(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    thread = await _find_thread(session, user_id, thread_id)
    if not thread:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    return _thread_dict(thread)


@router.put("/{thread_id}")
async def update_thread(
    thread_id: str,
    body: UpdateThreadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    values["updated_at"] = _now()
    stmt = (
        update(Thread)
        .where(and_(Thread.id == thread_id, Thread.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(Thread).where(and_(Thread.id == thread_id, Thread.user_id == user_id))
    )
    return {"ok": True}


@router.get("/{thread_id}/messages")
async def get_thread_messages(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get all messages in a thread."""
    stmt = (
        select(Message)
        .where(and_(Message.thread_id == thread_id, Message.user_id == user_id))
        .order_by(Message.created_at)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "model": m.model,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


@router.post("/remove-by-topic")
async def remove_threads_by_topic(
    topic_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(Thread).where(and_(Thread.topic_id == topic_id, Thread.user_id == user_id))
    )
    return {"ok": True}


@router.post("/batch-delete")
async def batch_delete_threads(
    body: BatchDeleteThreadsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if body.ids:
        await session.execute(
            delete(Thread).where(and_(Thread.id.in_(body.ids), Thread.user_id == user_id))
        )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_thread(db: AsyncSession, user_id: str, thread_id: str) -> Thread | None:
    stmt = select(Thread).where(and_(Thread.id == thread_id, Thread.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _thread_dict(t: Thread) -> dict[str, Any]:
    return {
        "id": t.id,
        "topic_id": t.topic_id,
        "title": t.title,
        "type": t.type,
        "status": t.status,
        "source_message_id": t.source_message_id,
        "parent_thread_id": t.parent_thread_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
