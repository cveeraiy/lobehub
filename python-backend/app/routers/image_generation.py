"""Image Generation router — create image generation batches.

Mirrors TS: src/server/routers/lambda/image/index.ts
Simplified: no chargeBeforeGenerate, no async task trigger, no S3 URL normalization.
The Python backend handles DB record creation; actual generation is delegated
to the model runtime (litellm or provider SDK) via a background task.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.generation import GenerationBatch, Generation
from app.models.misc import AsyncTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image", tags=["Image Generation"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_seeds(count: int) -> list[int]:
    """Generate unique random seeds."""
    seeds = set()
    while len(seeds) < count:
        seeds.add(random.randint(0, 2**31 - 1))
    return list(seeds)


# ── Schemas ──────────────────────────────────────────────────────────

class ImageParams(BaseModel):
    prompt: str
    width: Optional[int] = None
    height: Optional[int] = None
    cfg: Optional[float] = None
    steps: Optional[int] = None
    seed: Optional[int] = None
    image_urls: Optional[list[str]] = Field(None, alias="imageUrls")
    image_url: Optional[str] = Field(None, alias="imageUrl")

    model_config = {"populate_by_name": True}


class CreateImageBody(BaseModel):
    generation_topic_id: str = Field(..., alias="generationTopicId")
    image_num: int = Field(1, alias="imageNum")
    model: str
    provider: str
    params: ImageParams

    model_config = {"populate_by_name": True}


# ── Helpers ──────────────────────────────────────────────────────────

def _serialize_batch(batch: GenerationBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "model": batch.model,
        "provider": batch.provider,
        "prompt": batch.prompt,
        "params": batch.params,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
    }


def _serialize_generation(gen: Generation) -> dict[str, Any]:
    return {
        "id": gen.id,
        "batch_id": gen.batch_id,
        "seed": gen.seed,
        "status": gen.status,
        "file_id": gen.file_id,
        "async_task_id": getattr(gen, "_async_task_id", None),
        "created_at": gen.created_at.isoformat() if gen.created_at else None,
    }


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/create")
async def create_image(
    body: CreateImageBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create image generation batch with generations and async tasks.

    Creates the DB records (batch + N generations + N async tasks) atomically.
    The actual image generation is handled by a background worker that polls
    for pending async tasks.
    """
    now = _now()
    params_dict = body.params.model_dump(by_alias=True, exclude_none=True)

    # 1. Create batch
    batch = GenerationBatch(
        user_id=user_id,
        topic_id=body.generation_topic_id,
        model=body.model,
        provider=body.provider,
        prompt=body.params.prompt,
        params=params_dict,
        created_at=now,
        updated_at=now,
        accessed_at=now,
    )
    session.add(batch)
    await session.flush()  # get batch.id

    # 2. Create generations + async tasks
    use_seeds = body.params.seed is not None
    seeds = _generate_seeds(body.image_num) if use_seeds else [None] * body.image_num

    created_generations = []
    for i in range(body.image_num):
        # Create async task
        task = AsyncTask(
            user_id=user_id,
            status="pending",
            type="image_generation",
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        await session.flush()

        # Create generation linked to task
        gen = Generation(
            user_id=user_id,
            batch_id=batch.id,
            topic_id=body.generation_topic_id,
            type="text2image" if not body.params.image_url else "image2image",
            model=body.model,
            provider=body.provider,
            prompt=body.params.prompt,
            seed=seeds[i],
            status="pending",
            created_at=now,
            updated_at=now,
            accessed_at=now,
        )
        session.add(gen)
        await session.flush()

        gen._async_task_id = task.id  # type: ignore[attr-defined]
        created_generations.append(gen)

    await session.commit()

    return {
        "success": True,
        "data": {
            "batch": _serialize_batch(batch),
            "generations": [_serialize_generation(g) for g in created_generations],
        },
    }
