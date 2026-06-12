"""Share router — create and manage shareable conversation links."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message
from app.models.topic import Topic
from app.models.topic_ext import TopicShare

router = APIRouter(prefix="/api/share", tags=["Share"])


class CreateShareBody(BaseModel):
    topic_id: str
    is_public: bool = True


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_share(
    body: CreateShareBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create or return existing share link for a topic."""
    existing = (
        await session.execute(
            select(TopicShare).where(
                and_(TopicShare.topic_id == body.topic_id, TopicShare.user_id == user_id)
            )
        )
    ).scalar_one_or_none()

    if existing:
        return {"id": existing.id, "is_public": existing.is_public}

    share = TopicShare(
        topic_id=body.topic_id,
        user_id=user_id,
        is_public=body.is_public,
    )
    session.add(share)
    await session.flush()
    return {"id": share.id, "is_public": share.is_public}


@router.get("/{share_id}")
async def get_shared_conversation(
    share_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Public endpoint — get shared conversation by share ID."""
    share = (
        await session.execute(select(TopicShare).where(TopicShare.id == share_id))
    ).scalar_one_or_none()

    if not share or not share.is_public:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")

    topic = (
        await session.execute(select(Topic).where(Topic.id == share.topic_id))
    ).scalar_one_or_none()

    messages = (
        await session.execute(
            select(Message)
            .where(and_(Message.topic_id == share.topic_id, Message.user_id == share.user_id))
            .order_by(Message.created_at)
        )
    ).scalars().all()

    return {
        "topic": {"id": topic.id, "title": topic.title} if topic else None,
        "messages": [
            {"role": m.role, "content": m.content, "model": m.model, "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in messages
        ],
    }


@router.delete("/{share_id}")
async def delete_share(
    share_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete
    await session.execute(
        delete(TopicShare).where(and_(TopicShare.id == share_id, TopicShare.user_id == user_id))
    )
    return {"ok": True}
