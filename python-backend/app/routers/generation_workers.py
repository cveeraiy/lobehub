"""Generation worker control endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.generation_worker import execute_generation_task, execute_pending_generation_tasks

router = APIRouter(prefix="/api/generation-workers", tags=["Generation Workers"])


@router.post("/tasks/{task_id}/run")
async def run_generation_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await execute_generation_task(session, task_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/run-pending")
async def run_pending_generation_tasks(
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await execute_pending_generation_tasks(session, limit=limit, user_id=user_id)
