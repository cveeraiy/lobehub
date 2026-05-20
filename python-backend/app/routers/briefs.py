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
    artifacts: Optional[dict[str, Any]] = None
    actions: Optional[Any] = None
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
    actions: Optional[Any] = None
    artifacts: Optional[dict[str, Any]] = None
    agents: list[dict[str, Any]] = Field(default_factory=list)
    task_status: Optional[str] = None
    resolved_action: Optional[str] = None
    resolved_comment: Optional[str] = None
    read_at: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


def _brief_to_response(brief: Any) -> dict[str, Any]:
    if isinstance(brief, dict):
        get = brief.get
    else:
        get = lambda key, default=None: getattr(brief, key, default)

    read_at = get("read_at")
    resolved_at = get("resolved_at")
    created_at = get("created_at")

    return {
        "id": get("id"),
        "user_id": get("user_id"),
        "userId": get("user_id"),
        "task_id": get("task_id"),
        "taskId": get("task_id"),
        "cron_job_id": get("cron_job_id"),
        "cronJobId": get("cron_job_id"),
        "topic_id": get("topic_id"),
        "topicId": get("topic_id"),
        "agent_id": get("agent_id"),
        "agentId": get("agent_id"),
        "type": get("type"),
        "priority": get("priority"),
        "title": get("title"),
        "summary": get("summary"),
        "artifacts": get("artifacts"),
        "actions": get("actions"),
        "agents": get("agents") or [],
        "task_status": get("task_status"),
        "taskStatus": get("task_status"),
        "resolved_action": get("resolved_action"),
        "resolvedAction": get("resolved_action"),
        "resolved_comment": get("resolved_comment"),
        "resolvedComment": get("resolved_comment"),
        "read_at": read_at.isoformat() if hasattr(read_at, "isoformat") else read_at,
        "readAt": read_at.isoformat() if hasattr(read_at, "isoformat") else read_at,
        "resolved_at": resolved_at.isoformat() if hasattr(resolved_at, "isoformat") else resolved_at,
        "resolvedAt": resolved_at.isoformat() if hasattr(resolved_at, "isoformat") else resolved_at,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
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
    briefs = await svc.enrich_briefs_with_agents(result["briefs"])
    return {
        "success": True,
        "data": [_brief_to_response(b) for b in briefs],
        "total": result["total"],
    }


@router.get("/unresolved")
async def list_unresolved(
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    """List all unresolved briefs."""
    svc = BriefService(session, user_id)
    briefs = await svc.enrich_briefs_with_agents(await svc.list_unresolved())
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
        artifacts=body.artifacts,
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
    briefs = await svc.enrich_briefs_with_agents(await svc.find_by_task_id(task_id))
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
    enriched = await svc.enrich_briefs_with_agents([brief])
    return {"success": True, "data": _brief_to_response(enriched[0])}


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
    enriched = await svc.enrich_briefs_with_agents([brief])
    return {"success": True, "data": _brief_to_response(enriched[0])}


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
