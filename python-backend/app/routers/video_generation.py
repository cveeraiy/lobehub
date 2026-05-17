"""Video Generation router — create video generation batches.

Mirrors TS: src/server/routers/lambda/video/index.ts
Simplified: no chargeBeforeGenerate/chargeAfterGenerate, no webhook token,
no background polling. The Python backend handles DB record creation;
actual generation is delegated to the model runtime via a background task.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.generation import GenerationBatch, Generation
from app.models.misc import AsyncTask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["Video Generation"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class VideoParams(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = Field(None, alias="aspectRatio")
    camera_fixed: Optional[bool] = Field(None, alias="cameraFixed")
    duration: Optional[int] = None
    end_image_url: Optional[str] = Field(None, alias="endImageUrl")
    generate_audio: Optional[bool] = Field(None, alias="generateAudio")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    resolution: Optional[str] = None
    seed: Optional[int] = None

    model_config = {"populate_by_name": True}


class CreateVideoBody(BaseModel):
    generation_topic_id: str = Field(..., alias="generationTopicId")
    model: str
    provider: str
    params: VideoParams

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


def _serialize_generation(gen: Generation, async_task_id: str) -> dict[str, Any]:
    return {
        "id": gen.id,
        "batch_id": gen.batch_id,
        "seed": gen.seed,
        "status": gen.status,
        "file_id": gen.file_id,
        "async_task_id": async_task_id,
        "created_at": gen.created_at.isoformat() if gen.created_at else None,
    }


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/create")
async def create_video(
    body: CreateVideoBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create video generation batch with one generation and async task.

    Creates the DB records atomically. Video always generates a single output.
    The actual video generation is handled by a background worker.
    """
    now = _now()
    params_dict = body.params.model_dump(by_alias=True, exclude_none=True)

    gen_type = "text2video"
    if body.params.image_url:
        gen_type = "image2video"

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
    await session.flush()

    # 2. Create async task
    task = AsyncTask(
        user_id=user_id,
        status="pending",
        type="video_generation",
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    await session.flush()

    # 3. Create single generation
    gen = Generation(
        user_id=user_id,
        batch_id=batch.id,
        topic_id=body.generation_topic_id,
        type=gen_type,
        model=body.model,
        provider=body.provider,
        prompt=body.params.prompt,
        seed=body.params.seed,
        status="pending",
        created_at=now,
        updated_at=now,
        accessed_at=now,
    )
    session.add(gen)
    await session.commit()

    return {
        "success": True,
        "data": {
            "batch": _serialize_batch(batch),
            "generations": [_serialize_generation(gen, task.id)],
        },
    }
