"""Agent Cron Job Router — CRUD for scheduled agent jobs.

Ports TS ``routers/lambda/agentCronJob.ts`` (371 lines):
- create / update / delete
- list (paginated, filtered by agent/enabled)
- findById / findByAgent
- batchUpdateStatus
- resetExecutions
- getStats / getNearDepletion
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete as sa_delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.agent_ops import AgentCronJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-cron-jobs", tags=["agent-cron-jobs"])

_TEMP_USER_ID = "user_default"


def _get_user_id() -> str:
    return _TEMP_USER_ID


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateCronJobRequest(BaseModel):
    agent_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    schedule: str  # cron expression
    timezone: str = "UTC"
    config: Optional[dict[str, Any]] = None
    condition: Optional[dict[str, Any]] = None
    enabled: bool = True
    template_id: Optional[str] = None  # for analytics, not persisted


class UpdateCronJobRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[str] = None
    timezone: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    condition: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


class BatchUpdateStatusRequest(BaseModel):
    ids: list[str]
    enabled: bool


class ResetExecutionsRequest(BaseModel):
    id: str
    new_max_executions: Optional[int] = None


def _job_to_dict(job: AgentCronJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "agent_id": job.agent_id,
        "user_id": job.user_id,
        "name": job.name,
        "description": job.description,
        "schedule": job.schedule,
        "timezone": job.timezone,
        "config": job.config,
        "condition": job.condition,
        "enabled": job.enabled,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "total_runs": job.total_runs,
        "total_failures": job.total_failures,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_cron_jobs(
    agent_id: Optional[str] = Query(default=None),
    enabled: Optional[bool] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """List cron jobs with filtering and pagination."""
    base = select(AgentCronJob).where(AgentCronJob.user_id == user_id)
    if agent_id:
        base = base.where(AgentCronJob.agent_id == agent_id)
    if enabled is not None:
        base = base.where(AgentCronJob.enabled == enabled)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = base.order_by(AgentCronJob.created_at.desc()).offset(offset).limit(limit)
    jobs = (await session.execute(stmt)).scalars().all()

    return {
        "success": True,
        "data": [_job_to_dict(j) for j in jobs],
        "pagination": {
            "total": total,
            "offset": offset,
            "limit": limit,
            "hasMore": offset + limit < total,
        },
    }


@router.post("", status_code=201)
async def create_cron_job(
    body: CreateCronJobRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Create a new cron job."""
    job = AgentCronJob(
        agent_id=body.agent_id,
        user_id=user_id,
        name=body.name,
        description=body.description,
        schedule=body.schedule,
        timezone=body.timezone,
        config=body.config,
        condition=body.condition,
        enabled=body.enabled,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    await session.commit()
    return {"success": True, "data": _job_to_dict(job), "message": "Cron job created successfully"}


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Get execution statistics for user's cron jobs."""
    stmt = select(
        func.count(AgentCronJob.id).label("total_jobs"),
        func.sum(AgentCronJob.total_runs).label("total_runs"),
        func.sum(AgentCronJob.total_failures).label("total_failures"),
        func.count(AgentCronJob.id).filter(AgentCronJob.enabled == True).label("enabled_count"),  # noqa: E712
    ).where(AgentCronJob.user_id == user_id)

    row = (await session.execute(stmt)).one()
    return {
        "success": True,
        "data": {
            "totalJobs": row.total_jobs or 0,
            "totalRuns": row.total_runs or 0,
            "totalFailures": row.total_failures or 0,
            "enabledCount": row.enabled_count or 0,
        },
    }


@router.get("/near-depletion")
async def get_near_depletion(
    threshold: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Get jobs near depletion (total_runs close to some limit)."""
    # For now return all enabled jobs sorted by total_runs desc
    stmt = (
        select(AgentCronJob)
        .where(AgentCronJob.user_id == user_id, AgentCronJob.enabled == True)  # noqa: E712
        .order_by(AgentCronJob.total_runs.desc())
        .limit(threshold)
    )
    jobs = (await session.execute(stmt)).scalars().all()
    return {"success": True, "data": [_job_to_dict(j) for j in jobs]}


@router.get("/agent/{agent_id}")
async def find_by_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """List cron jobs for a specific agent."""
    stmt = (
        select(AgentCronJob)
        .where(AgentCronJob.user_id == user_id, AgentCronJob.agent_id == agent_id)
        .order_by(AgentCronJob.created_at.desc())
    )
    jobs = (await session.execute(stmt)).scalars().all()
    return {"success": True, "data": [_job_to_dict(j) for j in jobs]}


@router.get("/{job_id}")
async def find_by_id(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Get a single cron job by ID."""
    stmt = select(AgentCronJob).where(
        AgentCronJob.id == job_id, AgentCronJob.user_id == user_id
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    return {"success": True, "data": _job_to_dict(job)}


@router.put("/{job_id}")
async def update_cron_job(
    job_id: str,
    body: UpdateCronJobRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Update a cron job."""
    stmt = select(AgentCronJob).where(
        AgentCronJob.id == job_id, AgentCronJob.user_id == user_id
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found or access denied")

    update_data: dict[str, Any] = {}
    for field_name in ("name", "description", "schedule", "timezone", "config", "condition", "enabled"):
        val = getattr(body, field_name)
        if val is not None:
            update_data[field_name] = val

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await session.execute(
            update(AgentCronJob)
            .where(AgentCronJob.id == job_id)
            .values(**update_data)
        )
        await session.refresh(job)

    await session.commit()
    return {"success": True, "data": _job_to_dict(job), "message": "Cron job updated successfully"}


@router.delete("/{job_id}")
async def delete_cron_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Delete a cron job."""
    result = await session.execute(
        sa_delete(AgentCronJob).where(
            AgentCronJob.id == job_id, AgentCronJob.user_id == user_id
        )
    )
    if result.rowcount == 0:  # type: ignore[union-attr]
        raise HTTPException(status_code=404, detail="Cron job not found or access denied")
    await session.commit()
    return {"success": True, "message": "Cron job deleted successfully"}


@router.post("/batch-update-status")
async def batch_update_status(
    body: BatchUpdateStatusRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Batch enable/disable multiple cron jobs."""
    if not body.ids:
        return {"success": True, "data": {"updatedCount": 0}}

    result = await session.execute(
        update(AgentCronJob)
        .where(
            AgentCronJob.id.in_(body.ids),
            AgentCronJob.user_id == user_id,
        )
        .values(enabled=body.enabled, updated_at=datetime.now(timezone.utc))
    )
    count = result.rowcount  # type: ignore[union-attr]
    await session.commit()

    action = "enabled" if body.enabled else "disabled"
    return {
        "success": True,
        "data": {"updatedCount": count},
        "message": f"{count} cron jobs {action} successfully",
    }


@router.post("/reset-executions")
async def reset_executions(
    body: ResetExecutionsRequest,
    session: AsyncSession = Depends(get_session),
    user_id: str = Depends(_get_user_id),
):
    """Reset execution counts for a cron job."""
    stmt = select(AgentCronJob).where(
        AgentCronJob.id == body.id, AgentCronJob.user_id == user_id
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found or access denied")

    update_values: dict[str, Any] = {
        "total_runs": 0,
        "total_failures": 0,
        "updated_at": datetime.now(timezone.utc),
    }

    await session.execute(
        update(AgentCronJob).where(AgentCronJob.id == body.id).values(**update_values)
    )
    await session.refresh(job)
    await session.commit()

    return {"success": True, "data": _job_to_dict(job), "message": "Execution counts reset successfully"}
