"""Memory CRUD + search router."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services import memory_service as svc

router = APIRouter(prefix="/api/memories", tags=["Memories"])


# ── Schemas ──────────────────────────────────────────────────────────

class CreateMemoryBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memory_layer: str = "semantic"
    memory_type: Optional[str] = None
    memory_category: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class UpdateMemoryBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memory_category: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


class SearchMemoryBody(BaseModel):
    query: str
    layer: Optional[str] = None
    limit: int = 10
    model: str = "openai/text-embedding-3-small"


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_memories(
    layer: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mems = await svc.list_memories(
        session, user_id, layer=layer, category=category, limit=limit, offset=offset
    )
    return [_mem_dict(m) for m in mems]


@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mem = await svc.get_memory(session, user_id, memory_id)
    if not mem:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    return _mem_dict(mem)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: CreateMemoryBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mem = await svc.create_memory(
        session, user_id,
        title=body.title,
        summary=body.summary,
        details=body.details,
        memory_layer=body.memory_layer,
        memory_type=body.memory_type,
        memory_category=body.memory_category,
        tags=body.tags,
        metadata=body.metadata,
    )
    return {"id": mem.id}


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    body: UpdateMemoryBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    await svc.update_memory(session, user_id, memory_id, **values)
    return {"ok": True}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await svc.delete_memory(session, user_id, memory_id)
    return {"ok": True}


# ── Search ───────────────────────────────────────────────────────────

@router.post("/search")
async def search_memories(
    body: SearchMemoryBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await svc.search_memories_by_text(
        session, user_id, body.query,
        model=body.model,
        layer=body.layer,
        limit=body.limit,
    )


# ── Helpers ──────────────────────────────────────────────────────────

def _mem_dict(m) -> dict[str, Any]:
    return {
        "id": m.id,
        "title": m.title,
        "summary": m.summary,
        "details": m.details,
        "memory_layer": m.memory_layer,
        "memory_type": m.memory_type,
        "memory_category": m.memory_category,
        "tags": m.tags,
        "status": m.status,
        "accessed_count": m.accessed_count,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
