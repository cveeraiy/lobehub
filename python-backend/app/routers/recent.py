"""Recent items router — last N accessed topics/documents/tasks for quick-switch UI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.file import Document
from app.models.topic import Topic

router = APIRouter(prefix="/api/recent", tags=["Recent"])


@router.get("")
async def get_recent(
    limit: int = Query(default=10, le=50),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get recently accessed topics and documents.

    Returns items with type, title, route path, and timestamp for the quick-switch sidebar.
    """
    results: list[dict[str, Any]] = []

    # Recent topics
    topic_stmt = (
        select(Topic)
        .where(Topic.user_id == user_id)
        .order_by(desc(Topic.updated_at))
        .limit(limit)
    )
    topics = (await session.execute(topic_stmt)).scalars().all()

    for t in topics:
        agent_id = None
        route_path = "/"

        # Build route path based on session
        if t.session_id:
            route_path = f"/chat/{t.session_id}?topic={t.id}"

        results.append({
            "id": t.id,
            "type": "topic",
            "title": t.title or "Untitled",
            "icon": "topic",
            "routePath": route_path,
            "agentId": agent_id,
            "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
        })

    # Recent documents
    doc_stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .where(Document.source_type == "api")
        .order_by(desc(Document.accessed_at))
        .limit(limit)
    )
    docs = (await session.execute(doc_stmt)).scalars().all()

    for d in docs:
        results.append({
            "id": d.id,
            "type": "document",
            "title": d.title or d.filename or "Untitled",
            "icon": "document",
            "routePath": f"/page/{d.id}",
            "agentId": None,
            "updatedAt": d.accessed_at.isoformat() if d.accessed_at else None,
        })

    # Sort all results by timestamp descending, limit to requested count
    results.sort(key=lambda x: x.get("updatedAt") or "", reverse=True)
    return results[:limit]
