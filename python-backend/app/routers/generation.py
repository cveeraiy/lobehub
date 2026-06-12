"""Generation router — text and image generation endpoints, plus generation topics CRUD."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models._helpers import create_nanoid
from app.services import llm_service

router = APIRouter(prefix="/api/generation", tags=["Generation"])


class TextGenerationBody(BaseModel):
    prompt: str
    model: Optional[str] = "openai/gpt-4o"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None


class ImageGenerationBody(BaseModel):
    prompt: str
    model: Optional[str] = "openai/dall-e-3"
    size: Optional[str] = "1024x1024"
    quality: Optional[str] = "standard"
    n: int = 1


@router.post("/text")
async def generate_text(
    body: TextGenerationBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Generate text completion (non-streaming)."""
    messages: list[dict[str, Any]] = []
    if body.system_prompt:
        messages.append({"role": "system", "content": body.system_prompt})
    messages.append({"role": "user", "content": body.prompt})

    response = await llm_service.chat(
        messages,
        model=body.model or "openai/gpt-4o",
        stream=False,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    choice = response.choices[0]  # type: ignore[attr-defined]
    return {
        "content": choice.message.content,
        "model": response.model,  # type: ignore[attr-defined]
        "usage": getattr(response, "usage", None),
    }


@router.post("/image")
async def generate_image(
    body: ImageGenerationBody,
    user_id: str = Depends(get_current_user_id),
):
    """Generate image via LiteLLM image_generation."""
    try:
        import litellm
        response = await litellm.aimage_generation(
            model=body.model or "openai/dall-e-3",
            prompt=body.prompt,
            size=body.size,
            quality=body.quality,
            n=body.n,
        )
        return {
            "images": [
                {"url": img.url, "revised_prompt": getattr(img, "revised_prompt", None)}
                for img in response.data  # type: ignore[attr-defined]
            ]
        }
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Image generation failed: {exc}")


# ── Generation Topics CRUD ─────────────────────────────────────────


class CreateTopicBody(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None  # text2image | image2image | image2video | text2video


@router.post("/topics", status_code=201)
async def create_topic(
    body: CreateTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a generation topic."""
    from app.models._helpers import id_generator
    topic_id = id_generator("generationTopics")
    await session.execute(
        text(
            "INSERT INTO generation_topics (id, user_id, title, type, favorite) "
            "VALUES (:id, :uid, :title, :type, false)"
        ),
        {"id": topic_id, "uid": user_id, "title": body.title, "type": body.type},
    )
    return {"id": topic_id, "title": body.title, "type": body.type}


@router.get("/topics")
async def list_topics(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List generation topics for the current user."""
    result = await session.execute(
        text(
            "SELECT id, title, type, favorite, created_at FROM generation_topics "
            "WHERE user_id = :uid ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    )
    return [dict(r._mapping) for r in result.fetchall()]


@router.delete("/topics/{topic_id}")
async def delete_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a generation topic."""
    await session.execute(
        text("DELETE FROM generation_topics WHERE id = :id AND user_id = :uid"),
        {"id": topic_id, "uid": user_id},
    )
    return {"ok": True}
