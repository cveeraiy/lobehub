"""Generation Batches router — list/delete generation batches.

Frontend: src/services/generationBatch.rest.ts
Prefix: /api/generation-batches
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.generation import GenerationBatch, Generation
from app.models.misc import AsyncTask

router = APIRouter(prefix="/api/generation-batches", tags=["Generation Batches"])


# ── Helpers ──────────────────────────────────────────────────────────

def _batch_dict(b: GenerationBatch) -> dict[str, Any]:
    return {
        "id": b.id,
        "topicId": b.topic_id,
        "model": b.model,
        "provider": b.provider,
        "prompt": b.prompt,
        "params": b.params,
        "createdAt": b.created_at.isoformat() if b.created_at else None,
        "updatedAt": b.updated_at.isoformat() if b.updated_at else None,
    }


def _generation_dict(g: Generation, async_task_id: Optional[str] = None) -> dict[str, Any]:
    return {
        "id": g.id,
        "batchId": g.batch_id,
        "topicId": g.topic_id,
        "type": g.type,
        "model": g.model,
        "provider": g.provider,
        "prompt": g.prompt,
        "fileId": g.file_id,
        "seed": g.seed,
        "status": g.status,
        "error": g.error,
        "asyncTaskId": async_task_id,
        "createdAt": g.created_at.isoformat() if g.created_at else None,
        "updatedAt": g.updated_at.isoformat() if g.updated_at else None,
    }


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_generation_batches(
    topicId: Optional[str] = None,
    type: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List generation batches for a topic, with their generations."""
    stmt = (
        select(GenerationBatch)
        .where(GenerationBatch.user_id == user_id)
    )
    if topicId:
        stmt = stmt.where(GenerationBatch.topic_id == topicId)
    stmt = stmt.order_by(desc(GenerationBatch.created_at))
    batches = (await session.execute(stmt)).scalars().all()

    results = []
    for batch in batches:
        gen_stmt = (
            select(Generation)
            .where(and_(Generation.batch_id == batch.id, Generation.user_id == user_id))
            .order_by(Generation.created_at)
        )
        generations = (await session.execute(gen_stmt)).scalars().all()

        # Filter by type if provided
        if type:
            generations = [g for g in generations if g.type and type in g.type]

        # Get async task IDs for each generation
        gen_dicts = []
        for g in generations:
            # Look up async_task_id from batch or generation
            task_id = batch.async_task_id
            gen_dicts.append(_generation_dict(g, async_task_id=task_id))

        batch_data = _batch_dict(batch)
        batch_data["generations"] = gen_dicts
        results.append(batch_data)

    return results


@router.delete("/{batch_id}")
async def delete_generation_batch(
    batch_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a generation batch and its generations."""
    # Get batch first
    batch = (await session.execute(
        select(GenerationBatch).where(
            and_(GenerationBatch.id == batch_id, GenerationBatch.user_id == user_id)
        )
    )).scalar_one_or_none()

    if not batch:
        return None

    # Delete generations
    await session.execute(
        delete(Generation).where(
            and_(Generation.batch_id == batch_id, Generation.user_id == user_id)
        )
    )

    # Delete async task if exists
    if batch.async_task_id:
        await session.execute(
            delete(AsyncTask).where(AsyncTask.id == batch.async_task_id)
        )

    # Delete batch
    await session.execute(
        delete(GenerationBatch).where(
            and_(GenerationBatch.id == batch_id, GenerationBatch.user_id == user_id)
        )
    )

    return _batch_dict(batch)
