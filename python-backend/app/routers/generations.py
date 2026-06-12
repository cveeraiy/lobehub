"""Generations router — status and delete for individual generations.

Frontend: src/services/generation.rest.ts
Prefix: /api/generations
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.generation import Generation
from app.models.misc import AsyncTask

router = APIRouter(prefix="/api/generations", tags=["Generations"])


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/{generation_id}/status")
async def get_generation_status(
    generation_id: str,
    asyncTaskId: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get the status of a generation, optionally checking its async task."""
    gen = (await session.execute(
        select(Generation).where(
            and_(Generation.id == generation_id, Generation.user_id == user_id)
        )
    )).scalar_one_or_none()

    if not gen:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Generation not found")

    result: dict[str, Any] = {
        "id": gen.id,
        "status": gen.status,
        "fileId": gen.file_id,
        "error": gen.error,
    }

    # If an async task ID is provided, check its status too
    if asyncTaskId:
        task = (await session.execute(
            select(AsyncTask).where(AsyncTask.id == asyncTaskId)
        )).scalar_one_or_none()
        if task:
            result["asyncTaskStatus"] = task.status
            result["asyncTaskError"] = getattr(task, "error", None)

    return result


@router.delete("/{generation_id}")
async def delete_generation(
    generation_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a single generation."""
    await session.execute(
        delete(Generation).where(
            and_(Generation.id == generation_id, Generation.user_id == user_id)
        )
    )
    return {"ok": True}
