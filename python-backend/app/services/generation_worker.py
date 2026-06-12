"""Generation task execution helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.generation import Generation, GenerationBatch
from app.models.misc import AsyncTask


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def execute_generation_task(session: AsyncSession, task_id: str, *, user_id: str | None = None) -> dict[str, Any]:
    stmt = select(AsyncTask).where(AsyncTask.id == task_id)
    if user_id:
        stmt = stmt.where(AsyncTask.user_id == user_id)
    task = (await session.execute(stmt)).scalar_one_or_none()
    if task is None:
        raise ValueError("Async task not found")
    if task.type not in {"image_generation", "video_generation"}:
        raise ValueError(f"Unsupported generation task type: {task.type}")

    batches = (
        await session.execute(select(GenerationBatch).where(GenerationBatch.async_task_id == task.id))
    ).scalars().all()
    if not batches:
        task.status = "error"
        task.error = {"message": "No generation batch is linked to this task"}
        task.updated_at = _now()
        await session.flush()
        return {"processed": 0, "status": task.status}

    task.status = "processing"
    task.updated_at = _now()
    processed = 0
    failures: list[dict[str, Any]] = []

    for batch in batches:
        generations = (
            await session.execute(
                select(Generation).where(
                    and_(
                        Generation.batch_id == batch.id,
                        Generation.status.in_(["pending", "processing"]),
                    )
                )
            )
        ).scalars().all()
        for generation in generations:
            generation.status = "processing"
            generation.updated_at = _now()
            try:
                if task.type == "image_generation":
                    file_id = await _execute_image_generation(session, batch, generation)
                    generation.file_id = file_id
                    generation.status = "success"
                else:
                    raise RuntimeError(
                        "Video generation execution requires a provider-specific worker or webhook callback"
                    )
            except Exception as exc:
                generation.status = "failed"
                generation.error = {"message": str(exc)}
                failures.append({"generationId": generation.id, "message": str(exc)})
            finally:
                generation.updated_at = _now()
                processed += 1

    task.status = "error" if failures else "success"
    task.error = {"failures": failures} if failures else None
    task.updated_at = _now()
    await session.flush()
    return {"failures": failures, "processed": processed, "status": task.status}


async def execute_pending_generation_tasks(
    session: AsyncSession,
    *,
    limit: int = 10,
    user_id: str | None = None,
) -> dict[str, Any]:
    stmt = (
        select(AsyncTask)
        .where(and_(AsyncTask.type.in_(["image_generation", "video_generation"]), AsyncTask.status == "pending"))
        .order_by(AsyncTask.created_at)
        .limit(limit)
    )
    if user_id:
        stmt = stmt.where(AsyncTask.user_id == user_id)
    tasks = (await session.execute(stmt)).scalars().all()
    results = [await execute_generation_task(session, task.id, user_id=user_id) for task in tasks]
    return {"processed": len(results), "results": results}


async def _execute_image_generation(
    session: AsyncSession,
    batch: GenerationBatch,
    generation: Generation,
) -> str:
    image_urls = await _call_litellm_image_generation(batch, generation)
    image_url = image_urls[0] if image_urls else None
    if not image_url:
        raise RuntimeError("Image provider returned no image URL")

    file = File(
        user_id=generation.user_id,
        file_type="image/png",
        name=f"{generation.id}.png",
        size=0,
        url=image_url,
        source="generation",
        metadata_={
            "batchId": batch.id,
            "generationId": generation.id,
            "model": generation.model,
            "provider": generation.provider,
        },
        created_at=_now(),
        updated_at=_now(),
        accessed_at=_now(),
    )
    session.add(file)
    await session.flush()
    return file.id


async def _call_litellm_image_generation(batch: GenerationBatch, generation: Generation) -> list[str]:
    from litellm import aimage_generation

    params = dict(batch.params or generation.params or {})
    prompt = generation.prompt or batch.prompt
    if not prompt:
        raise RuntimeError("Image prompt is required")

    response = await aimage_generation(
        model=batch.model or generation.model,
        prompt=prompt,
        **{key: value for key, value in params.items() if key != "prompt"},
    )
    return _extract_image_urls(response)


def _extract_image_urls(response: Any) -> list[str]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    urls: list[str] = []
    for item in data or []:
        if isinstance(item, dict):
            url = item.get("url") or item.get("b64_json")
        else:
            url = getattr(item, "url", None) or getattr(item, "b64_json", None)
        if url:
            urls.append(str(url))
    return urls
