"""Brief Router — REST endpoints for brief CRUD and lifecycle.

Endpoints:
- GET    /api/briefs              — List briefs (paginated)
- GET    /api/briefs/unresolved   — List unresolved briefs
- POST   /api/briefs              — Create a brief
- GET    /api/briefs/{id}         — Get brief by ID
- POST   /api/briefs/{id}/resolve — Resolve a brief
- POST   /api/briefs/{id}/read    — Mark brief as read
- DELETE /api/briefs/{id}         — Delete a brief
- GET    /api/briefs/task/{task_id} — List briefs for a task
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.brief import BriefService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefs", tags=["briefs"])

from app.dependencies import get_current_user_id


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateBriefRequest(BaseModel):
    type: str
    title: str
    summary: str
    task_id: Optional[str] = None
    cron_job_id: Optional[str] = None
    topic_id: Optional[str] = None
    agent_id: Optional[str] = None
    priority: str = "info"
    actions: Optional[dict[str, Any]] = None
    trigger: Optional[str] = None


class ResolveBriefRequest(BaseModel):
    action: Optional[str] = None  # "approve" | "feedback" | "retry" | "acknowledge"
    comment: Optional[str] = None


class BriefResponse(BaseModel):
    id: str
    user_id: str
    task_id: Optional[str] = None
    cron_job_id: Optional[str] = None
    topic_id: Optional[str] = None
    agent_id: Optional[str] = None
    type: str
    priority: Optional[str] = None
    title: str
    summary: str
    actions: Optional[dict[str, Any]] = None
    resolved_action: Optional[str] = None
    resolved_comment: Optional[str] = None
    read_at: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


def _brief_to_response(brief: Any) -> dict[str, Any]:
    return {
        "id": brief.id,
        "user_id": brief.user_id,
        "task_id": brief.task_id,
        "cron_job_id": brief.cron_job_id,
        "topic_id": brief.topic_id,
        "agent_id": brief.agent_id,
        "type": brief.type,
        "priority": brief.priority,
        "title": brief.title,
        "summary": brief.summary,
        "actions": brief.actions,
        "agents": getattr(brief, "agents", None) or [],
        "resolved_action": brief.resolved_action,
        "resolved_comment": brief.resolved_comment,
        "read_at": brief.read_at.isoformat() if brief.read_at else None,
        "resolved_at": brief.resolved_at.isoformat() if brief.resolved_at else None,
        "created_at": brief.created_at.isoformat() if brief.created_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_briefs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    type: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """List briefs with pagination."""
    svc = BriefService(session, user_id)
    result = await svc.list_briefs(limit=limit, offset=offset, brief_type=type)
    return {
        "success": True,
        "data": [_brief_to_response(b) for b in result["briefs"]],
        "total": result["total"],
    }


@router.get("/unresolved")
async def list_unresolved(
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """List all unresolved briefs."""
    svc = BriefService(session, user_id)
    briefs = await svc.list_unresolved()
    return {
        "success": True,
        "data": [_brief_to_response(b) for b in briefs],
    }


@router.post("", status_code=201)
async def create_brief(
    body: CreateBriefRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """Create a new brief."""
    svc = BriefService(session, user_id)
    brief = await svc.create(
        brief_type=body.type,
        title=body.title,
        summary=body.summary,
        task_id=body.task_id,
        cron_job_id=body.cron_job_id,
        topic_id=body.topic_id,
        agent_id=body.agent_id,
        priority=body.priority,
        actions=body.actions,
        trigger=body.trigger,
    )
    await session.commit()
    return {"success": True, "data": _brief_to_response(brief)}


@router.get("/task/{task_id}")
async def list_briefs_by_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """List all briefs for a task."""
    svc = BriefService(session, user_id)
    briefs = await svc.find_by_task_id(task_id)
    return {
        "success": True,
        "data": [_brief_to_response(b) for b in briefs],
    }


@router.get("/{brief_id}")
async def get_brief(
    brief_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """Get a brief by ID."""
    svc = BriefService(session, user_id)
    brief = await svc.find_by_id(brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    return {"success": True, "data": _brief_to_response(brief)}


@router.post("/{brief_id}/resolve")
async def resolve_brief(
    brief_id: str,
    body: ResolveBriefRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """Resolve a brief (approve, feedback, retry, acknowledge)."""
    svc = BriefService(session, user_id)
    brief = await svc.resolve(brief_id, action=body.action, comment=body.comment)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    await session.commit()
    return {"success": True, "data": _brief_to_response(brief)}


@router.post("/{brief_id}/read")
@router.put("/{brief_id}/read")
async def mark_brief_read(
    brief_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """Mark a brief as read."""
    svc = BriefService(session, user_id)
    ok = await svc.mark_read(brief_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Brief not found")
    await session.commit()
    return {"success": True}


@router.delete("/{brief_id}")
async def delete_brief(
    brief_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a brief."""
    svc = BriefService(session, user_id)
    ok = await svc.delete(brief_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Brief not found")
    await session.commit()
    return {"success": True}
