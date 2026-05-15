"""Message CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message, MessageFile

router = APIRouter(prefix="/api/messages", tags=["Messages"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateMessageBody(BaseModel):
    role: str  # user | assistant | system | tool
    content: Optional[str] = None
    session_id: Optional[str] = None
    topic_id: Optional[str] = None
    agent_id: Optional[str] = None
    parent_id: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tools: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    reasoning_content: Optional[str] = None


class UpdateMessageBody(BaseModel):
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tools: Optional[list[dict[str, Any]]] = None
    error: Optional[dict[str, Any]] = None
    token_count: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_price: Optional[float] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_messages(
    session_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Message).where(Message.user_id == user_id)
    if session_id:
        stmt = stmt.where(Message.session_id == session_id)
    if topic_id:
        stmt = stmt.where(Message.topic_id == topic_id)
    if agent_id:
        stmt = stmt.where(Message.agent_id == agent_id)
    stmt = stmt.order_by(Message.created_at).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_msg_dict(r) for r in rows]


@router.get("/{message_id}")
async def get_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    msg = await _find_msg(session, user_id, message_id)
    if not msg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return _msg_dict(msg)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_message(
    body: CreateMessageBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    msg = Message(user_id=user_id, **body.model_dump(exclude_none=True))
    session.add(msg)
    await session.flush()
    return {"id": msg.id}


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def create_messages_batch(
    messages: list[CreateMessageBody],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    objs: list[Message] = []
    for body in messages:
        msg = Message(user_id=user_id, **body.model_dump(exclude_none=True))
        session.add(msg)
        objs.append(msg)
    await session.flush()  # single round-trip instead of N
    return {"ids": [m.id for m in objs]}


@router.put("/{message_id}")
async def update_message(
    message_id: str,
    body: UpdateMessageBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(Message)
        .where(and_(Message.id == message_id, Message.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Remove file links
    await session.execute(
        delete(MessageFile).where(
            and_(MessageFile.message_id == message_id, MessageFile.user_id == user_id)
        )
    )
    await session.execute(
        delete(Message).where(and_(Message.id == message_id, Message.user_id == user_id))
    )
    return {"ok": True}


@router.delete("")
async def batch_delete_messages(
    session_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = delete(Message).where(Message.user_id == user_id)
    if session_id:
        stmt = stmt.where(Message.session_id == session_id)
    if topic_id:
        stmt = stmt.where(Message.topic_id == topic_id)
    await session.execute(stmt)
    return {"ok": True}


# ── File links ───────────────────────────────────────────────────────

@router.post("/{message_id}/files/{file_id}", status_code=status.HTTP_201_CREATED)
async def link_file(
    message_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    link = MessageFile(message_id=message_id, file_id=file_id, user_id=user_id)
    session.add(link)
    await session.flush()
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_msg(db: AsyncSession, user_id: str, message_id: str) -> Message | None:
    stmt = select(Message).where(and_(Message.id == message_id, Message.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _msg_dict(m: Message) -> dict[str, Any]:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "reasoning_content": m.reasoning_content,
        "model": m.model,
        "provider": m.provider,
        "session_id": m.session_id,
        "topic_id": m.topic_id,
        "agent_id": m.agent_id,
        "parent_id": m.parent_id,
        "tool_call_id": m.tool_call_id,
        "tools": m.tools,
        "error": m.error,
        "token_count": m.token_count,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "total_price": m.total_price,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
