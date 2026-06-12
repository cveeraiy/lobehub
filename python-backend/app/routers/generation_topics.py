"""Generation Topics router — CRUD for image/video generation topics.

Frontend: src/services/generationTopic.rest.ts
Prefix: /api/generation-topics
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.generation import GenerationTopic, GenerationBatch, Generation

router = APIRouter(prefix="/api/generation-topics", tags=["Generation Topics"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateTopicBody(BaseModel):
    type: Optional[str] = None


class UpdateTopicBody(BaseModel):
    title: Optional[str] = None
    favorite: Optional[bool] = None


class UpdateTopicCoverBody(BaseModel):
    coverUrl: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────

def _topic_dict(t: GenerationTopic) -> dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "favorite": t.favorite,
        "type": t.type,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
        "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
    }


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_topics(
    type: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List generation topics for the current user."""
    stmt = (
        select(GenerationTopic)
        .where(GenerationTopic.user_id == user_id)
    )
    if type:
        stmt = stmt.where(GenerationTopic.type == type)
    stmt = stmt.order_by(desc(GenerationTopic.updated_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_topic_dict(t) for t in rows]


@router.post("", status_code=201)
async def create_topic(
    body: CreateTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a generation topic. Returns the topic ID."""
    topic = GenerationTopic(
        user_id=user_id,
        type=body.type,
    )
    session.add(topic)
    await session.flush()
    return topic.id


@router.put("/{topic_id}")
async def update_topic(
    topic_id: str,
    body: UpdateTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update a generation topic (title, favorite)."""
    values = body.model_dump(exclude_none=True)
    if not values:
        return None
    values["updated_at"] = _now()
    result = await session.execute(
        update(GenerationTopic)
        .where(and_(GenerationTopic.id == topic_id, GenerationTopic.user_id == user_id))
        .values(**values)
        .returning(GenerationTopic)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    return _topic_dict(row)


@router.put("/{topic_id}/cover")
async def update_topic_cover(
    topic_id: str,
    body: UpdateTopicCoverBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update a generation topic's cover URL."""
    values: dict[str, Any] = {"updated_at": _now()}
    # Store coverUrl in a metadata-like approach or dedicated column if available
    # For now, we just update the updated_at to acknowledge the request
    result = await session.execute(
        update(GenerationTopic)
        .where(and_(GenerationTopic.id == topic_id, GenerationTopic.user_id == user_id))
        .values(**values)
        .returning(GenerationTopic)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    return _topic_dict(row)


@router.delete("/{topic_id}")
async def delete_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a generation topic and its batches/generations."""
    # Delete generations belonging to batches in this topic
    batch_ids_stmt = select(GenerationBatch.id).where(
        and_(GenerationBatch.topic_id == topic_id, GenerationBatch.user_id == user_id)
    )
    await session.execute(
        delete(Generation).where(Generation.batch_id.in_(batch_ids_stmt))
    )
    # Delete batches
    await session.execute(
        delete(GenerationBatch).where(
            and_(GenerationBatch.topic_id == topic_id, GenerationBatch.user_id == user_id)
        )
    )
    # Delete topic
    await session.execute(
        delete(GenerationTopic).where(
            and_(GenerationTopic.id == topic_id, GenerationTopic.user_id == user_id)
        )
    )
    return {"ok": True}
