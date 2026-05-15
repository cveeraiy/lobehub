"""User Memory router — structured memory CRUD across all memory layers.

Covers: base memories, contexts, preferences, activities, identities, experiences.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.memory import (
    UserMemory,
    UserMemoryActivity,
    UserMemoryContext,
    UserMemoryExperience,
    UserMemoryIdentity,
    UserMemoryPreference,
)

router = APIRouter(prefix="/api/user-memory", tags=["User Memory"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateMemoryBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memory_category: Optional[str] = None
    memory_layer: Optional[str] = None
    memory_type: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class UpdateMemoryBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class CreateIdentityBody(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CreatePreferenceBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


# ── Base Memory CRUD ─────────────────────────────────────────────────
# NOTE: Fixed-path routes (/stats, /identities, /preferences) are registered
# before the /{memory_id} wildcard to avoid path conflicts.

@router.get("")
async def list_memories(
    layer: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List user memories with optional layer/category filter."""
    stmt = select(UserMemory).where(UserMemory.user_id == user_id)
    if layer:
        stmt = stmt.where(UserMemory.memory_layer == layer)
    if category:
        stmt = stmt.where(UserMemory.memory_category == category)
    stmt = stmt.order_by(desc(UserMemory.updated_at)).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_memory_dict(m) for m in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: CreateMemoryBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mem = UserMemory(
        user_id=user_id,
        title=body.title,
        summary=body.summary,
        details=body.details,
        memory_category=body.memory_category,
        memory_layer=body.memory_layer,
        memory_type=body.memory_type,
        tags=body.tags,
        metadata_=body.metadata,
    )
    session.add(mem)
    await session.flush()
    return {"id": mem.id}


# ── Stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def memory_stats(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get counts per memory layer."""
    total = (await session.execute(
        select(func.count()).select_from(UserMemory).where(UserMemory.user_id == user_id)
    )).scalar_one()
    identities = (await session.execute(
        select(func.count()).select_from(UserMemoryIdentity).where(UserMemoryIdentity.user_id == user_id)
    )).scalar_one()
    preferences = (await session.execute(
        select(func.count()).select_from(UserMemoryPreference).where(UserMemoryPreference.user_id == user_id)
    )).scalar_one()
    activities = (await session.execute(
        select(func.count()).select_from(UserMemoryActivity).where(UserMemoryActivity.user_id == user_id)
    )).scalar_one()
    experiences = (await session.execute(
        select(func.count()).select_from(UserMemoryExperience).where(UserMemoryExperience.user_id == user_id)
    )).scalar_one()
    contexts = (await session.execute(
        select(func.count()).select_from(UserMemoryContext).where(UserMemoryContext.user_id == user_id)
    )).scalar_one()
    return {
        "total": total,
        "identities": identities,
        "preferences": preferences,
        "activities": activities,
        "experiences": experiences,
        "contexts": contexts,
    }


# ── Identities ───────────────────────────────────────────────────────

@router.get("/identities")
async def list_identities(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryIdentity).where(UserMemoryIdentity.user_id == user_id).order_by(desc(UserMemoryIdentity.created_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [{"id": i.id, "type": i.type, "title": i.title, "description": i.description} for i in rows]


@router.post("/identities", status_code=status.HTTP_201_CREATED)
async def create_identity(
    body: CreateIdentityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    ident = UserMemoryIdentity(
        user_id=user_id,
        type=body.type,
        title=body.title,
        description=body.description,
        metadata_=body.metadata,
    )
    session.add(ident)
    await session.flush()
    return {"id": ident.id}


@router.delete("/identities/{identity_id}")
async def delete_identity(
    identity_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(UserMemoryIdentity).where(and_(UserMemoryIdentity.id == identity_id, UserMemoryIdentity.user_id == user_id))
    )
    return {"ok": True}


# ── Preferences ──────────────────────────────────────────────────────

@router.get("/preferences")
async def list_preferences(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryPreference).where(UserMemoryPreference.user_id == user_id).order_by(desc(UserMemoryPreference.created_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [{"id": p.id, "title": p.title, "description": p.description} for p in rows]


@router.post("/preferences", status_code=status.HTTP_201_CREATED)
async def create_preference(
    body: CreatePreferenceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    pref = UserMemoryPreference(
        user_id=user_id,
        title=body.title,
        description=body.description,
        tags=body.tags,
        metadata_=body.metadata,
    )
    session.add(pref)
    await session.flush()
    return {"id": pref.id}


@router.delete("/preferences/{pref_id}")
async def delete_preference(
    pref_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(UserMemoryPreference).where(and_(UserMemoryPreference.id == pref_id, UserMemoryPreference.user_id == user_id))
    )
    return {"ok": True}


# ── Single Memory CRUD (/{memory_id} routes AFTER fixed paths) ──────

@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mem = await _find_memory(session, user_id, memory_id)
    if not mem:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    return _memory_dict(mem)


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    body: UpdateMemoryBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values: dict[str, Any] = {}
    if body.title is not None:
        values["title"] = body.title
    if body.summary is not None:
        values["summary"] = body.summary
    if body.details is not None:
        values["details"] = body.details
    if body.status is not None:
        values["status"] = body.status
    if body.tags is not None:
        values["tags"] = body.tags
    if body.metadata is not None:
        values["metadata_"] = body.metadata
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(UserMemory)
        .where(and_(UserMemory.id == memory_id, UserMemory.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(UserMemory).where(and_(UserMemory.id == memory_id, UserMemory.user_id == user_id))
    )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_memory(db: AsyncSession, user_id: str, memory_id: str) -> UserMemory | None:
    stmt = select(UserMemory).where(and_(UserMemory.id == memory_id, UserMemory.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _memory_dict(m: UserMemory) -> dict[str, Any]:
    return {
        "id": m.id,
        "title": m.title,
        "summary": m.summary,
        "details": m.details,
        "memory_category": m.memory_category,
        "memory_layer": m.memory_layer,
        "memory_type": m.memory_type,
        "tags": m.tags,
        "metadata": m.metadata_,
        "status": m.status,
        "accessed_count": m.accessed_count,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
