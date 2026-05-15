"""Chunk router — chunk-level CRUD and search within a document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.rag import Chunk, Embedding

router = APIRouter(prefix="/api/chunks", tags=["Chunks"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class UpdateChunkBody(BaseModel):
    text: Optional[str] = None
    abstract: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class SearchChunksBody(BaseModel):
    query: str
    knowledge_base_id: Optional[str] = None
    document_id: Optional[str] = None
    limit: int = 10


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/{chunk_id}")
async def get_chunk(
    chunk_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    chunk = await _find_chunk(session, user_id, chunk_id)
    if not chunk:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chunk not found")
    return _chunk_dict(chunk)


@router.put("/{chunk_id}")
async def update_chunk(
    chunk_id: str,
    body: UpdateChunkBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update chunk text/abstract (e.g. after manual correction)."""
    values: dict[str, Any] = {}
    if body.text is not None:
        values["text"] = body.text
    if body.abstract is not None:
        values["abstract"] = body.abstract
    if body.metadata is not None:
        values["metadata_"] = body.metadata
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    stmt = (
        update(Chunk)
        .where(and_(Chunk.id == chunk_id, Chunk.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{chunk_id}")
async def delete_chunk(
    chunk_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a chunk and its embedding."""
    await session.execute(delete(Embedding).where(Embedding.chunk_id == chunk_id))
    await session.execute(
        delete(Chunk).where(and_(Chunk.id == chunk_id, Chunk.user_id == user_id))
    )
    return {"ok": True}


@router.post("/search")
async def search_chunks(
    body: SearchChunksBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Vector search across chunks (requires embedding the query first)."""
    from app.services import knowledge_service, llm_service

    try:
        vectors = await llm_service.embed([body.query])
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Embedding failed: {exc}")

    results = await knowledge_service.vector_search(
        session,
        user_id,
        vectors[0],
        kb_id=body.knowledge_base_id,
        limit=body.limit,
    )
    return results


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_chunk(db: AsyncSession, user_id: str, chunk_id: str) -> Chunk | None:
    stmt = select(Chunk).where(and_(Chunk.id == chunk_id, Chunk.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _chunk_dict(c: Chunk) -> dict[str, Any]:
    return {
        "id": c.id,
        "text": c.text,
        "abstract": c.abstract,
        "index": c.index,
        "type": c.type,
        "metadata": c.metadata_,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
