"""Search router — unified full-text search across messages, topics, agents."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent import Agent
from app.models.message import Message
from app.models.topic import Topic

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Search across messages, topics, and agents using ILIKE."""
    pattern = f"%{q}%"

    # Messages
    msg_stmt = (
        select(Message)
        .where(Message.user_id == user_id)
        .where(Message.content.ilike(pattern))
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    messages = (await session.execute(msg_stmt)).scalars().all()

    # Topics
    topic_stmt = (
        select(Topic)
        .where(Topic.user_id == user_id)
        .where(Topic.title.ilike(pattern))
        .order_by(desc(Topic.created_at))
        .limit(limit)
    )
    topics = (await session.execute(topic_stmt)).scalars().all()

    # Agents
    agent_stmt = (
        select(Agent)
        .where(Agent.user_id == user_id)
        .where(
            or_(
                Agent.title.ilike(pattern),
                Agent.description.ilike(pattern),
            )
        )
        .order_by(desc(Agent.updated_at))
        .limit(limit)
    )
    agents = (await session.execute(agent_stmt)).scalars().all()

    return {
        "messages": [
            {"id": m.id, "content": m.content[:200] if m.content else "", "session_id": m.session_id, "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in messages
        ],
        "topics": [
            {"id": t.id, "title": t.title, "session_id": t.session_id, "created_at": t.created_at.isoformat() if t.created_at else None}
            for t in topics
        ],
        "agents": [
            {"id": a.id, "title": a.title, "slug": a.slug, "description": a.description}
            for a in agents
        ],
    }
