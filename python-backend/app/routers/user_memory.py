"""User Memory router — structured memory CRUD across all memory layers.

Covers: base memories, contexts, preferences, activities, identities, experiences.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pydantic import Field as PField
from sqlalchemy import and_, asc, delete, desc, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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
from app.models.message import Message
from app.models.persona import UserPersonaDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user-memory", tags=["User Memory"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _summarize_memory_text(messages: list[Message]) -> tuple[str, str]:
    lines = [
        f"{message.role}: {(message.content or '').strip()}"
        for message in messages
        if (message.content or "").strip()
    ]
    details = "\n".join(lines)
    if not details:
        return "No memory content found", ""
    first_user = next((m.content for m in messages if m.role == "user" and m.content), None)
    title = (first_user or details.splitlines()[0])[:120]
    summary = details[:1000]
    return title, summary


async def _extract_memory_from_messages(
    session: AsyncSession,
    user_id: str,
    messages: list[Message],
    *,
    source: dict[str, Any],
) -> UserMemory | None:
    title, summary = _summarize_memory_text(messages)
    if not summary:
        return None
    memory = UserMemory(
        user_id=user_id,
        title=title,
        summary=summary,
        details="\n".join(m.content or "" for m in messages if m.content),
        memory_category="chat",
        memory_layer="context",
        memory_type="conversation_summary",
        tags=["extracted"],
        metadata_=source,
        status="active",
    )
    session.add(memory)
    await session.flush()
    return memory


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
    description: Optional[str] = None
    role: Optional[str] = None
    relationship: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CreatePreferenceBody(BaseModel):
    type: Optional[str] = None
    conclusion_directives: Optional[str] = None
    suggestions: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class UpdateIdentityBody(BaseModel):
    type: Optional[str] = None
    description: Optional[str] = None
    role: Optional[str] = None
    relationship: Optional[str] = None
    episodic_date: Optional[str] = None
    extracted_labels: Optional[list[str]] = None


class UpdatePreferenceBody(BaseModel):
    conclusion_directives: Optional[str] = None
    suggestions: Optional[str] = None


class UpdateActivityBody(BaseModel):
    narrative: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class UpdateContextBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    current_status: Optional[str] = None


class UpdateExperienceBody(BaseModel):
    situation: Optional[str] = None
    action: Optional[str] = None
    key_learning: Optional[str] = None


# ── Base Memory CRUD ─────────────────────────────────────────────────
# NOTE: Fixed-path routes (/stats, /identities, /preferences) are registered
# before the /{memory_id} wildcard to avoid path conflicts.

@router.get("")
async def list_memories(
    layer: Optional[str] = None,
    category: Optional[str] = None,
    categories: Optional[str] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    tags: Optional[str] = None,
    types: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=200),
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List user memories with optional layer/category/q/tag/type/status filters."""
    stmt = select(UserMemory).where(UserMemory.user_id == user_id)
    count_stmt = select(func.count()).select_from(UserMemory).where(UserMemory.user_id == user_id)

    if layer:
        stmt = stmt.where(UserMemory.memory_layer == layer)
        count_stmt = count_stmt.where(UserMemory.memory_layer == layer)
    if category:
        stmt = stmt.where(UserMemory.memory_category == category)
        count_stmt = count_stmt.where(UserMemory.memory_category == category)
    if categories:
        cat_list = [c.strip() for c in categories.split(",")]
        stmt = stmt.where(UserMemory.memory_category.in_(cat_list))
        count_stmt = count_stmt.where(UserMemory.memory_category.in_(cat_list))
    if q:
        like = f"%{q}%"
        filter_ = or_(UserMemory.title.ilike(like), UserMemory.summary.ilike(like))
        stmt = stmt.where(filter_)
        count_stmt = count_stmt.where(filter_)
    if status_filter:
        vals = [s.strip() for s in status_filter.split(",")]
        stmt = stmt.where(UserMemory.status.in_(vals))
        count_stmt = count_stmt.where(UserMemory.status.in_(vals))
    if tags:
        for tag in tags.split(","):
            stmt = stmt.where(UserMemory.tags.any(tag.strip()))
            count_stmt = count_stmt.where(UserMemory.tags.any(tag.strip()))
    if types:
        vals = [t.strip() for t in types.split(",")]
        stmt = stmt.where(UserMemory.memory_type.in_(vals))
        count_stmt = count_stmt.where(UserMemory.memory_type.in_(vals))

    sort_col = UserMemory.updated_at
    if sort == "capturedAt":
        sort_col = UserMemory.captured_at
    elif sort == "scoreConfidence":
        sort_col = UserMemory.score_confidence
    elif sort == "scoreImpact":
        sort_col = UserMemory.score_impact
    elif sort == "scorePriority":
        sort_col = UserMemory.score_priority
    elif sort == "scoreUrgency":
        sort_col = UserMemory.score_urgency
    stmt = stmt.order_by(asc(sort_col) if order == "asc" else desc(sort_col))

    total = (await session.execute(count_stmt)).scalar_one()

    if limit is not None:
        stmt = stmt.offset(offset or 0).limit(limit)
    else:
        stmt = stmt.offset((page - 1) * pageSize).limit(pageSize)

    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_memory_dict(m) for m in rows], "page": page, "pageSize": pageSize, "total": total}


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
    return [{"id": i.id, "type": i.type, "description": i.description, "role": i.role, "relationship": i.relationship} for i in rows]


@router.post("/identities", status_code=status.HTTP_201_CREATED)
async def create_identity(
    body: CreateIdentityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    ident = UserMemoryIdentity(
        user_id=user_id,
        type=body.type,
        description=body.description,
        role=body.role,
        relationship=body.relationship,
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
    return [{"id": p.id, "type": p.type, "conclusion_directives": p.conclusion_directives, "suggestions": p.suggestions} for p in rows]


@router.post("/preferences", status_code=status.HTTP_201_CREATED)
async def create_preference(
    body: CreatePreferenceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    pref = UserMemoryPreference(
        user_id=user_id,
        type=body.type,
        conclusion_directives=body.conclusion_directives,
        suggestions=body.suggestions,
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


# ── Activities ──────────────────────────────────────────────────────

@router.get("/activities")
async def list_activities(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryActivity).where(UserMemoryActivity.user_id == user_id).order_by(desc(UserMemoryActivity.created_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_activity_dict(a) for a in rows]


@router.put("/activities/{activity_id}")
async def update_activity(
    activity_id: str,
    body: UpdateActivityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(UserMemoryActivity)
        .where(and_(UserMemoryActivity.id == activity_id, UserMemoryActivity.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/activities/{activity_id}")
async def delete_activity(
    activity_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(UserMemoryActivity).where(and_(UserMemoryActivity.id == activity_id, UserMemoryActivity.user_id == user_id))
    )
    return {"ok": True}


# ── Contexts ────────────────────────────────────────────────────────

@router.get("/contexts")
async def list_contexts(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryContext).where(UserMemoryContext.user_id == user_id).order_by(desc(UserMemoryContext.created_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_context_dict(c) for c in rows]


@router.put("/contexts/{context_id}")
async def update_context(
    context_id: str,
    body: UpdateContextBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(UserMemoryContext)
        .where(and_(UserMemoryContext.id == context_id, UserMemoryContext.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/contexts/{context_id}")
async def delete_context(
    context_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(UserMemoryContext).where(and_(UserMemoryContext.id == context_id, UserMemoryContext.user_id == user_id))
    )
    return {"ok": True}


# ── Experiences ─────────────────────────────────────────────────────

@router.get("/experiences")
async def list_experiences(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryExperience).where(UserMemoryExperience.user_id == user_id).order_by(desc(UserMemoryExperience.created_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_experience_dict(e) for e in rows]


@router.put("/experiences/{experience_id}")
async def update_experience(
    experience_id: str,
    body: UpdateExperienceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(UserMemoryExperience)
        .where(and_(UserMemoryExperience.id == experience_id, UserMemoryExperience.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/experiences/{experience_id}")
async def delete_experience(
    experience_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(UserMemoryExperience).where(and_(UserMemoryExperience.id == experience_id, UserMemoryExperience.user_id == user_id))
    )
    return {"ok": True}


# ── Persona ─────────────────────────────────────────────────────────

@router.get("/persona")
async def get_persona(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserPersonaDocument)
        .where(UserPersonaDocument.user_id == user_id)
        .order_by(desc(UserPersonaDocument.updated_at))
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return None
    return {
        "content": row.persona or "",
        "summary": row.tagline or "",
    }


# ── Update identity / preference (with {id} param) ─────────────────

@router.put("/identities/{identity_id}")
async def update_identity(
    identity_id: str,
    body: UpdateIdentityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values: dict[str, Any] = {"updated_at": _now()}
    if body.type is not None:
        values["type"] = body.type
    if body.description is not None:
        values["description"] = body.description
    if body.role is not None:
        values["role"] = body.role
    if body.relationship is not None:
        values["relationship"] = body.relationship
    if body.extracted_labels is not None:
        values["tags"] = body.extracted_labels
    await session.execute(
        update(UserMemoryIdentity)
        .where(and_(UserMemoryIdentity.id == identity_id, UserMemoryIdentity.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.put("/preferences/{pref_id}")
async def update_preference(
    pref_id: str,
    body: UpdatePreferenceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(UserMemoryPreference)
        .where(and_(UserMemoryPreference.id == pref_id, UserMemoryPreference.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


# ── Delete All ──────────────────────────────────────────────────────

@router.delete("")
async def delete_all_memories(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all user memory data across all layers."""
    await session.execute(delete(UserMemoryActivity).where(UserMemoryActivity.user_id == user_id))
    await session.execute(delete(UserMemoryContext).where(UserMemoryContext.user_id == user_id))
    await session.execute(delete(UserMemoryExperience).where(UserMemoryExperience.user_id == user_id))
    await session.execute(delete(UserMemoryIdentity).where(UserMemoryIdentity.user_id == user_id))
    await session.execute(delete(UserMemoryPreference).where(UserMemoryPreference.user_id == user_id))
    await session.execute(delete(UserMemory).where(UserMemory.user_id == user_id))
    return {"ok": True}


# ── Retrieve for topic (must be before /{memory_id} wildcard) ────────

@router.get("/retrieve-for-topic")
async def retrieve_memory_for_topic(
    topicId: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve relevant memories for a topic by embedding the topic's user messages."""
    stmt = (
        select(Message.content)
        .where(and_(Message.topic_id == topicId, Message.user_id == user_id, Message.role == "user"))
        .order_by(asc(Message.created_at))
        .limit(50)
    )
    rows = (await session.execute(stmt)).scalars().all()
    user_text = " ".join([c for c in rows if c])[:7000]
    if not user_text.strip():
        return _empty_search_result()

    try:
        embeddings = await _embed([user_text])
    except Exception as e:
        logger.warning("Failed to embed topic messages: %s", e)
        return _empty_search_result()

    query_vec = embeddings[0] if embeddings else None
    if not query_vec:
        return _empty_search_result()

    identities = await _vector_search(session, user_id, query_vec, UserMemoryIdentity, UserMemoryIdentity.description_vector, 2, _identity_search_dict)
    preferences = await _vector_search(session, user_id, query_vec, UserMemoryPreference, UserMemoryPreference.conclusion_directives_vector, 5, _preference_search_dict)
    activities = await _vector_search(session, user_id, query_vec, UserMemoryActivity, UserMemoryActivity.narrative_vector, 5, _activity_search_dict)
    experiences = await _vector_search(session, user_id, query_vec, UserMemoryExperience, UserMemoryExperience.situation_vector, 5, _experience_search_dict)
    contexts = await _vector_search(session, user_id, query_vec, UserMemoryContext, UserMemoryContext.description_vector, 5, _context_search_dict)

    return {
        "identities": identities,
        "preferences": preferences,
        "activities": activities,
        "experiences": experiences,
        "contexts": contexts,
        "meta": {
            "appliedFilters": {},
            "appliedQueries": [user_text[:200]],
            "layers": {
                "identities": {"hasMore": False, "returned": len(identities), "total": len(identities)},
                "preferences": {"hasMore": False, "returned": len(preferences), "total": len(preferences)},
                "activities": {"hasMore": False, "returned": len(activities), "total": len(activities)},
                "experiences": {"hasMore": False, "returned": len(experiences), "total": len(experiences)},
                "contexts": {"hasMore": False, "returned": len(contexts), "total": len(contexts)},
            },
        },
    }


# ── Single Memory CRUD (/{memory_id} routes AFTER fixed paths) ──────

@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    layer: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mem = await _find_memory(session, user_id, memory_id)
    if not mem:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    result = _memory_dict(mem)
    effective_layer = layer or mem.memory_layer
    if effective_layer:
        result = await _enrich_with_layer(session, user_id, memory_id, effective_layer, result)
    return result


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


# ══════════════════════════════════════════════════════════════════════
#  Advanced Query / Search / Tool-add endpoints
#  (REST replacement for the retired TS user memory TRPC router)
# ══════════════════════════════════════════════════════════════════════


def _embedding_model() -> str:
    model = settings.memory_user_memory_embedding_model
    provider = settings.memory_user_memory_embedding_provider
    if provider and "/" not in model:
        return f"{provider}/{model}"
    return model


def _embedding_dimensions() -> int:
    return settings.memory_user_memory_embedding_dimensions


def _has_embedding_credentials() -> bool:
    model = _embedding_model()
    if model.startswith("openai/"):
        return bool(settings.openai_api_key)
    if model.startswith("bedrock/"):
        return bool(settings.aws_access_key_id and settings.aws_secret_access_key and settings.aws_region)
    return True

# ── Query schemas ─────────────────────────────────────────────────────


class QueryActivitiesParams(BaseModel):
    order: Optional[str] = None
    page: int = 1
    pageSize: int = 20
    q: Optional[str] = None
    sort: Optional[str] = None
    status: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    types: Optional[list[str]] = None


class QueryExperiencesParams(BaseModel):
    order: Optional[str] = None
    page: int = 1
    pageSize: int = 20
    q: Optional[str] = None
    sort: Optional[str] = None
    tags: Optional[list[str]] = None
    types: Optional[list[str]] = None


class QueryIdentitiesParams(BaseModel):
    order: Optional[str] = None
    page: int = 1
    pageSize: int = 20
    q: Optional[str] = None
    relationships: Optional[list[str]] = None
    sort: Optional[str] = None
    tags: Optional[list[str]] = None
    types: Optional[list[str]] = None


class SearchMemoryBody(BaseModel):
    queries: Optional[list[str]] = None
    effort: Optional[str] = None
    topK: Optional[dict[str, int]] = None
    where: Optional[dict[str, Any]] = None


class ToolAddActivityBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memoryCategory: Optional[str] = None
    memoryType: Optional[str] = None
    tags: Optional[list[str]] = None
    withActivity: dict[str, Any] = PField(default_factory=dict)


class ToolAddContextBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memoryCategory: Optional[str] = None
    memoryType: Optional[str] = None
    tags: Optional[list[str]] = None
    withContext: dict[str, Any] = PField(default_factory=dict)


class ToolAddExperienceBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memoryCategory: Optional[str] = None
    memoryType: Optional[str] = None
    tags: Optional[list[str]] = None
    withExperience: dict[str, Any] = PField(default_factory=dict)


class ToolAddIdentityBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memoryCategory: Optional[str] = None
    memoryType: Optional[str] = None
    tags: Optional[list[str]] = None
    withIdentity: dict[str, Any] = PField(default_factory=dict)


class ToolAddPreferenceBody(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    details: Optional[str] = None
    memoryCategory: Optional[str] = None
    memoryType: Optional[str] = None
    tags: Optional[list[str]] = None
    withPreference: dict[str, Any] = PField(default_factory=dict)


class ToolRemoveIdentityBody(BaseModel):
    id: str
    reason: Optional[str] = None


class ToolUpdateIdentityBody(BaseModel):
    id: str
    mergeStrategy: Optional[str] = None
    set: dict[str, Any] = PField(default_factory=dict)


class ReEmbedBody(BaseModel):
    concurrency: int = 10
    endDate: Optional[str] = None
    limit: Optional[int] = None
    only: Optional[list[str]] = None
    startDate: Optional[str] = None


# ── Embedding helper ─────────────────────────────────────────────────


async def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the default model."""
    from app.services import llm_service
    if not texts:
        return []
    if not _has_embedding_credentials():
        logger.debug("Skipping memory embedding because credentials are not configured")
        return []
    return await llm_service.embed(
        texts,
        model=_embedding_model(),
        dimensions=_embedding_dimensions(),
    )


async def _embed_single(text: str | None) -> list[float] | None:
    if not text or not text.strip():
        return None
    vecs = await _embed([text.strip()])
    return vecs[0] if vecs else None


# ── Paginated query endpoints ────────────────────────────────────────


@router.get("/query/activities")
async def query_activities(
    order: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    q: Optional[str] = None,
    sort: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    tags: Optional[str] = None,
    types: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryActivity).where(UserMemoryActivity.user_id == user_id)
    count_stmt = select(func.count()).select_from(UserMemoryActivity).where(UserMemoryActivity.user_id == user_id)

    if q:
        like = f"%{q}%"
        filter_ = or_(
            UserMemoryActivity.narrative.ilike(like),
            UserMemoryActivity.notes.ilike(like),
            UserMemoryActivity.feedback.ilike(like),
        )
        stmt = stmt.where(filter_)
        count_stmt = count_stmt.where(filter_)
    if status_filter:
        vals = [s.strip() for s in status_filter.split(",")]
        stmt = stmt.where(UserMemoryActivity.status.in_(vals))
        count_stmt = count_stmt.where(UserMemoryActivity.status.in_(vals))
    if tags:
        for tag in tags.split(","):
            stmt = stmt.where(UserMemoryActivity.tags.any(tag.strip()))
            count_stmt = count_stmt.where(UserMemoryActivity.tags.any(tag.strip()))
    if types:
        vals = [t.strip() for t in types.split(",")]
        stmt = stmt.where(UserMemoryActivity.type.in_(vals))
        count_stmt = count_stmt.where(UserMemoryActivity.type.in_(vals))

    if sort == "startsAt":
        col = UserMemoryActivity.starts_at
    else:
        col = UserMemoryActivity.captured_at
    stmt = stmt.order_by(asc(col) if order == "asc" else desc(col))

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.offset((page - 1) * pageSize).limit(pageSize)
    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_activity_dict(a) for a in rows], "page": page, "pageSize": pageSize, "total": total}


@router.get("/query/experiences")
async def query_experiences(
    order: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    q: Optional[str] = None,
    sort: Optional[str] = None,
    tags: Optional[str] = None,
    types: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryExperience).where(UserMemoryExperience.user_id == user_id)
    count_stmt = select(func.count()).select_from(UserMemoryExperience).where(UserMemoryExperience.user_id == user_id)

    if q:
        like = f"%{q}%"
        filter_ = or_(
            UserMemoryExperience.situation.ilike(like),
            UserMemoryExperience.action.ilike(like),
            UserMemoryExperience.key_learning.ilike(like),
        )
        stmt = stmt.where(filter_)
        count_stmt = count_stmt.where(filter_)
    if tags:
        for tag in tags.split(","):
            stmt = stmt.where(UserMemoryExperience.tags.any(tag.strip()))
            count_stmt = count_stmt.where(UserMemoryExperience.tags.any(tag.strip()))
    if types:
        vals = [t.strip() for t in types.split(",")]
        stmt = stmt.where(UserMemoryExperience.type.in_(vals))
        count_stmt = count_stmt.where(UserMemoryExperience.type.in_(vals))

    if sort == "scoreConfidence":
        col = UserMemoryExperience.score_confidence
    else:
        col = UserMemoryExperience.captured_at
    stmt = stmt.order_by(asc(col) if order == "asc" else desc(col))

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.offset((page - 1) * pageSize).limit(pageSize)
    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_experience_dict(e) for e in rows], "page": page, "pageSize": pageSize, "total": total}


@router.get("/query/identities")
async def query_identities(
    order: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    q: Optional[str] = None,
    relationships: Optional[str] = None,
    sort: Optional[str] = None,
    tags: Optional[str] = None,
    types: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(UserMemoryIdentity).where(UserMemoryIdentity.user_id == user_id)
    count_stmt = select(func.count()).select_from(UserMemoryIdentity).where(UserMemoryIdentity.user_id == user_id)

    if q:
        like = f"%{q}%"
        filter_ = or_(
            UserMemoryIdentity.description.ilike(like),
            UserMemoryIdentity.role.ilike(like),
        )
        stmt = stmt.where(filter_)
        count_stmt = count_stmt.where(filter_)
    if relationships:
        vals = [r.strip() for r in relationships.split(",")]
        stmt = stmt.where(UserMemoryIdentity.relationship.in_(vals))
        count_stmt = count_stmt.where(UserMemoryIdentity.relationship.in_(vals))
    if tags:
        for tag in tags.split(","):
            stmt = stmt.where(UserMemoryIdentity.tags.any(tag.strip()))
            count_stmt = count_stmt.where(UserMemoryIdentity.tags.any(tag.strip()))
    if types:
        vals = [t.strip() for t in types.split(",")]
        stmt = stmt.where(UserMemoryIdentity.type.in_(vals))
        count_stmt = count_stmt.where(UserMemoryIdentity.type.in_(vals))

    if sort == "type":
        col = UserMemoryIdentity.type
    else:
        col = UserMemoryIdentity.captured_at
    stmt = stmt.order_by(asc(col) if order == "asc" else desc(col))

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.offset((page - 1) * pageSize).limit(pageSize)
    rows = (await session.execute(stmt)).scalars().all()
    items = [
        {
            "id": i.id,
            "type": i.type,
            "description": i.description,
            "role": i.role,
            "relationship": i.relationship,
            "episodicDate": i.episodic_date.isoformat() if i.episodic_date else None,
            "tags": i.tags,
            "createdAt": i.created_at.isoformat() if i.created_at else None,
            "updatedAt": i.updated_at.isoformat() if i.updated_at else None,
        }
        for i in rows
    ]
    return {"items": items, "page": page, "pageSize": pageSize, "total": total}


@router.get("/identities-for-injection")
async def query_identities_for_injection(
    limit: int = Query(default=50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserMemoryIdentity)
        .where(UserMemoryIdentity.user_id == user_id)
        .order_by(desc(UserMemoryIdentity.created_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": i.id,
            "type": i.type,
            "description": i.description,
            "role": i.role,
            "relationship": i.relationship,
            "tags": i.tags,
        }
        for i in rows
    ]


@router.get("/identity-roles")
async def query_identity_roles(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    roles_stmt = (
        select(UserMemoryIdentity.role)
        .where(and_(UserMemoryIdentity.user_id == user_id, UserMemoryIdentity.role.isnot(None)))
        .distinct()
        .offset((page - 1) * size)
        .limit(size)
    )
    roles = [r for (r,) in (await session.execute(roles_stmt)).all() if r]
    tags_stmt = (
        select(func.unnest(UserMemoryIdentity.tags))
        .where(and_(UserMemoryIdentity.user_id == user_id, UserMemoryIdentity.tags.isnot(None)))
        .distinct()
        .limit(size)
    )
    try:
        tags = [t for (t,) in (await session.execute(tags_stmt)).all() if t]
    except Exception:
        tags = []
    return {"roles": roles, "tags": tags}


@router.get("/tags")
async def query_tags(
    layers: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(func.unnest(UserMemory.tags).label("tag"))
        .where(and_(UserMemory.user_id == user_id, UserMemory.tags.isnot(None)))
    )
    if layers:
        layer_list = [l.strip() for l in layers.split(",")]
        stmt = stmt.where(UserMemory.memory_layer.in_(layer_list))
    stmt = stmt.distinct().offset((page - 1) * size).limit(size)
    try:
        tags = [t for (t,) in (await session.execute(stmt)).all() if t]
    except Exception:
        tags = []
    return tags


@router.get("/taxonomy-options")
async def query_taxonomy_options(
    layer: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    base_where = [UserMemory.user_id == user_id]
    if layer:
        base_where.append(UserMemory.memory_layer == layer)

    async def _distinct_col(col, where_clauses, limit=50):
        stmt = select(col).where(and_(*where_clauses)).where(col.isnot(None)).distinct().limit(limit)
        try:
            return [v for (v,) in (await session.execute(stmt)).all() if v]
        except Exception:
            return []

    categories = await _distinct_col(UserMemory.memory_category, base_where)
    types = await _distinct_col(UserMemory.memory_type, base_where)
    statuses = await _distinct_col(UserMemory.status, base_where)

    tag_stmt = (
        select(func.unnest(UserMemory.tags).label("tag"))
        .where(and_(*base_where, UserMemory.tags.isnot(None)))
        .distinct()
        .limit(50)
    )
    try:
        tags = [t for (t,) in (await session.execute(tag_stmt)).all() if t]
    except Exception:
        tags = []

    ident_where = [UserMemoryIdentity.user_id == user_id]
    roles = await _distinct_col(UserMemoryIdentity.role, ident_where)
    relationships = await _distinct_col(UserMemoryIdentity.relationship, ident_where)
    labels: list[str] = []

    return {
        "categories": categories,
        "hasMore": {},
        "labels": labels,
        "relationships": relationships,
        "roles": roles,
        "statuses": statuses,
        "tags": tags,
        "types": types,
    }


# ── Search / Retrieve ────────────────────────────────────────────────


@router.post("/search")
async def search_memory(
    body: SearchMemoryBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    queries = [q.strip() for q in (body.queries or []) if q and q.strip()]
    top_k = body.topK or {}
    ident_limit = top_k.get("identities", 2)
    pref_limit = top_k.get("preferences", 5)
    act_limit = top_k.get("activities", 5)
    exp_limit = top_k.get("experiences", 5)
    ctx_limit = top_k.get("contexts", 5)

    identities: list[dict] = []
    preferences: list[dict] = []
    activities: list[dict] = []
    experiences: list[dict] = []
    contexts: list[dict] = []

    if not queries:
        return _empty_search_result()

    try:
        embeddings = await _embed(queries)
    except Exception as e:
        logger.warning("Failed to generate embeddings for memory search: %s", e)
        return _empty_search_result()

    query_vec = embeddings[0] if embeddings else None
    if not query_vec:
        return _empty_search_result()

    identities = await _vector_search(
        session, user_id, query_vec, UserMemoryIdentity,
        UserMemoryIdentity.description_vector, ident_limit,
        _identity_search_dict,
    )
    preferences = await _vector_search(
        session, user_id, query_vec, UserMemoryPreference,
        UserMemoryPreference.conclusion_directives_vector, pref_limit,
        _preference_search_dict,
    )
    activities = await _vector_search(
        session, user_id, query_vec, UserMemoryActivity,
        UserMemoryActivity.narrative_vector, act_limit,
        _activity_search_dict,
    )
    experiences = await _vector_search(
        session, user_id, query_vec, UserMemoryExperience,
        UserMemoryExperience.situation_vector, exp_limit,
        _experience_search_dict,
    )
    contexts = await _vector_search(
        session, user_id, query_vec, UserMemoryContext,
        UserMemoryContext.description_vector, ctx_limit,
        _context_search_dict,
    )

    return {
        "identities": identities,
        "preferences": preferences,
        "activities": activities,
        "experiences": experiences,
        "contexts": contexts,
        "meta": {
            "appliedFilters": {},
            "appliedQueries": queries,
            "layers": {
                "identities": {"hasMore": False, "returned": len(identities), "total": len(identities)},
                "preferences": {"hasMore": False, "returned": len(preferences), "total": len(preferences)},
                "activities": {"hasMore": False, "returned": len(activities), "total": len(activities)},
                "experiences": {"hasMore": False, "returned": len(experiences), "total": len(experiences)},
                "contexts": {"hasMore": False, "returned": len(contexts), "total": len(contexts)},
            },
        },
    }


# ── Tool-based add memory endpoints (with auto-embedding) ───────────


@router.post("/add-activity")
async def tool_add_activity_memory(
    body: ToolAddActivityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        summary_vec = await _embed_single(body.summary)
        details_vec = await _embed_single(body.details)
        wa = body.withActivity
        narrative_vec = await _embed_single(wa.get("narrative"))
        feedback_vec = await _embed_single(wa.get("feedback"))

        mem = UserMemory(
            user_id=user_id,
            title=body.title,
            summary=body.summary,
            summary_vector_1024=summary_vec,
            details=body.details or "",
            details_vector_1024=details_vec,
            memory_category=body.memoryCategory,
            memory_layer="activity",
            memory_type=body.memoryType,
            tags=body.tags,
        )
        session.add(mem)
        await session.flush()

        act = UserMemoryActivity(
            user_id=user_id,
            user_memory_id=mem.id,
            type=wa.get("type", "other"),
            status=wa.get("status", "pending"),
            timezone=wa.get("timezone"),
            starts_at=_parse_date(wa.get("startsAt")),
            ends_at=_parse_date(wa.get("endsAt")),
            associated_objects=wa.get("associatedObjects"),
            associated_subjects=wa.get("associatedSubjects"),
            associated_locations=wa.get("associatedLocations"),
            notes=wa.get("notes"),
            narrative=wa.get("narrative"),
            narrative_vector=narrative_vec,
            feedback=wa.get("feedback"),
            feedback_vector=feedback_vec,
            tags=wa.get("tags") or body.tags or [],
            metadata_=wa.get("metadata"),
        )
        session.add(act)
        await session.flush()

        return {"activityId": act.id, "memoryId": mem.id, "message": "Memory saved successfully", "success": True}
    except Exception as e:
        logger.error("Failed to save activity memory: %s", e)
        return {"message": f"Failed to save memory: {e}", "success": False}


@router.post("/add-context")
async def tool_add_context_memory(
    body: ToolAddContextBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        summary_vec = await _embed_single(body.summary)
        details_vec = await _embed_single(body.details)
        wc = body.withContext
        desc_vec = await _embed_single(wc.get("description"))

        mem = UserMemory(
            user_id=user_id,
            title=body.title,
            summary=body.summary,
            summary_vector_1024=summary_vec,
            details=body.details or "",
            details_vector_1024=details_vec,
            memory_category=body.memoryCategory,
            memory_layer="context",
            memory_type=body.memoryType,
            tags=body.tags,
        )
        session.add(mem)
        await session.flush()

        ctx = UserMemoryContext(
            user_id=user_id,
            user_memory_ids=[mem.id],
            title=wc.get("title"),
            description=wc.get("description"),
            description_vector=desc_vec,
            type=wc.get("type"),
            current_status=wc.get("currentStatus"),
            associated_objects=wc.get("associatedObjects"),
            associated_subjects=wc.get("associatedSubjects"),
            score_impact=wc.get("scoreImpact"),
            score_urgency=wc.get("scoreUrgency"),
            tags=body.tags or [],
            metadata_=wc.get("metadata", {}),
        )
        session.add(ctx)
        await session.flush()

        return {"contextId": ctx.id, "memoryId": mem.id, "message": "Memory saved successfully", "success": True}
    except Exception as e:
        logger.error("Failed to save context memory: %s", e)
        return {"message": f"Failed to save memory: {e}", "success": False}


@router.post("/add-experience")
async def tool_add_experience_memory(
    body: ToolAddExperienceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        summary_vec = await _embed_single(body.summary)
        details_vec = await _embed_single(body.details)
        we = body.withExperience
        situation_vec = await _embed_single(we.get("situation"))
        action_vec = await _embed_single(we.get("action"))
        key_learning_vec = await _embed_single(we.get("keyLearning"))

        mem = UserMemory(
            user_id=user_id,
            title=body.title,
            summary=body.summary,
            summary_vector_1024=summary_vec,
            details=body.details or "",
            details_vector_1024=details_vec,
            memory_category=body.memoryCategory,
            memory_layer="experience",
            memory_type=body.memoryType,
            tags=body.tags,
        )
        session.add(mem)
        await session.flush()

        exp = UserMemoryExperience(
            user_id=user_id,
            user_memory_id=mem.id,
            type=body.memoryType,
            situation=we.get("situation"),
            situation_vector=situation_vec,
            action=we.get("action"),
            action_vector=action_vec,
            key_learning=we.get("keyLearning"),
            key_learning_vector=key_learning_vec,
            reasoning=we.get("reasoning"),
            possible_outcome=we.get("possibleOutcome"),
            score_confidence=we.get("scoreConfidence"),
            tags=body.tags or [],
            metadata_=we.get("metadata", {}),
        )
        session.add(exp)
        await session.flush()

        return {"experienceId": exp.id, "memoryId": mem.id, "message": "Memory saved successfully", "success": True}
    except Exception as e:
        logger.error("Failed to save experience memory: %s", e)
        return {"message": f"Failed to save memory: {e}", "success": False}


@router.post("/add-identity")
async def tool_add_identity_memory(
    body: ToolAddIdentityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        summary_vec = await _embed_single(body.summary)
        details_vec = await _embed_single(body.details)
        wi = body.withIdentity
        desc_vec = await _embed_single(wi.get("description"))

        mem = UserMemory(
            user_id=user_id,
            title=body.title,
            summary=body.summary,
            summary_vector_1024=summary_vec,
            details=body.details,
            details_vector_1024=details_vec,
            memory_category=body.memoryCategory,
            memory_layer="identity",
            memory_type=body.memoryType,
            tags=body.tags,
        )
        session.add(mem)
        await session.flush()

        ident = UserMemoryIdentity(
            user_id=user_id,
            user_memory_id=mem.id,
            type=wi.get("type"),
            description=wi.get("description"),
            description_vector=desc_vec,
            episodic_date=_parse_date(wi.get("episodicDate")),
            relationship=wi.get("relationship"),
            role=wi.get("role"),
            tags=body.tags or [],
        )
        session.add(ident)
        await session.flush()

        return {"identityId": ident.id, "memoryId": mem.id, "message": "Identity memory saved successfully", "success": True}
    except Exception as e:
        logger.error("Failed to save identity memory: %s", e)
        return {"message": f"Failed to save identity memory: {e}", "success": False}


@router.post("/add-preference")
async def tool_add_preference_memory(
    body: ToolAddPreferenceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        summary_vec = await _embed_single(body.summary)
        details_vec = await _embed_single(body.details)
        wp = body.withPreference
        conclusion_vec = await _embed_single(wp.get("conclusionDirectives"))

        suggestions_text = None
        if wp.get("suggestions") and len(wp["suggestions"]) > 0:
            suggestions_text = "\n".join(wp["suggestions"])

        mem = UserMemory(
            user_id=user_id,
            title=body.title,
            summary=body.summary,
            summary_vector_1024=summary_vec,
            details=body.details or "",
            details_vector_1024=details_vec,
            memory_category=body.memoryCategory,
            memory_layer="preference",
            memory_type=body.memoryType,
            tags=body.tags,
        )
        session.add(mem)
        await session.flush()

        pref = UserMemoryPreference(
            user_id=user_id,
            user_memory_id=mem.id,
            type=body.memoryType,
            conclusion_directives=wp.get("conclusionDirectives", ""),
            conclusion_directives_vector=conclusion_vec,
            score_priority=wp.get("scorePriority"),
            suggestions=suggestions_text,
            tags=body.tags or [],
            metadata_={
                "appContext": wp.get("appContext"),
                "extractedScopes": wp.get("extractedScopes"),
                "originContext": wp.get("originContext"),
            },
        )
        session.add(pref)
        await session.flush()

        return {"memoryId": mem.id, "preferenceId": pref.id, "message": "Memory saved successfully", "success": True}
    except Exception as e:
        logger.error("Failed to save preference memory: %s", e)
        return {"message": f"Failed to save memory: {e}", "success": False}


@router.post("/remove-identity")
async def tool_remove_identity_memory(
    body: ToolRemoveIdentityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        ident = (await session.execute(
            select(UserMemoryIdentity).where(
                and_(UserMemoryIdentity.id == body.id, UserMemoryIdentity.user_id == user_id)
            )
        )).scalar_one_or_none()

        if not ident:
            return {"message": "Identity memory not found", "success": False}

        mem_id = ident.user_memory_id
        await session.execute(
            delete(UserMemoryIdentity).where(
                and_(UserMemoryIdentity.id == body.id, UserMemoryIdentity.user_id == user_id)
            )
        )
        if mem_id:
            await session.execute(
                delete(UserMemory).where(and_(UserMemory.id == mem_id, UserMemory.user_id == user_id))
            )
        return {"identityId": body.id, "message": "Identity memory removed successfully", "reason": body.reason, "success": True}
    except Exception as e:
        logger.error("Failed to remove identity memory: %s", e)
        return {"message": f"Failed to remove identity memory: {e}", "success": False}


@router.post("/update-identity")
async def tool_update_identity_memory(
    body: ToolUpdateIdentityBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        ident = (await session.execute(
            select(UserMemoryIdentity).where(
                and_(UserMemoryIdentity.id == body.id, UserMemoryIdentity.user_id == user_id)
            )
        )).scalar_one_or_none()

        if not ident:
            return {"message": "Identity memory not found", "success": False}

        set_data = body.set
        wi = set_data.get("withIdentity", {})

        ident_values: dict[str, Any] = {"updated_at": _now()}
        if "description" in wi and wi["description"] is not None:
            ident_values["description"] = wi["description"]
            ident_values["description_vector"] = await _embed_single(wi["description"])
        if "episodicDate" in wi:
            ident_values["episodic_date"] = _parse_date(wi["episodicDate"])
        if "relationship" in wi:
            ident_values["relationship"] = wi["relationship"]
        if "role" in wi:
            ident_values["role"] = wi["role"]
        if "type" in wi:
            ident_values["type"] = wi["type"]
        if "tags" in set_data:
            ident_values["tags"] = set_data["tags"]

        if len(ident_values) > 1:
            await session.execute(
                update(UserMemoryIdentity)
                .where(and_(UserMemoryIdentity.id == body.id, UserMemoryIdentity.user_id == user_id))
                .values(**ident_values)
            )

        base_values: dict[str, Any] = {"updated_at": _now()}
        if "summary" in set_data and set_data["summary"] is not None:
            base_values["summary"] = set_data["summary"]
            base_values["summary_vector_1024"] = await _embed_single(set_data["summary"])
        if "details" in set_data and set_data["details"] is not None:
            base_values["details"] = set_data["details"]
            base_values["details_vector_1024"] = await _embed_single(set_data["details"])
        if "title" in set_data:
            base_values["title"] = set_data["title"]
        if "tags" in set_data:
            base_values["tags"] = set_data["tags"]
        if "memoryCategory" in set_data:
            base_values["memory_category"] = set_data["memoryCategory"]
        if "memoryType" in set_data:
            base_values["memory_type"] = set_data["memoryType"]

        if len(base_values) > 1 and ident.user_memory_id:
            await session.execute(
                update(UserMemory)
                .where(and_(UserMemory.id == ident.user_memory_id, UserMemory.user_id == user_id))
                .values(**base_values)
            )

        return {"identityId": body.id, "message": "Identity memory updated successfully", "success": True}
    except Exception as e:
        logger.error("Failed to update identity memory: %s", e)
        return {"message": f"Failed to update identity memory: {e}", "success": False}


# ── Re-embed ─────────────────────────────────────────────────────────


@router.post("/re-embed")
async def re_embed_memories(
    body: Optional[ReEmbedBody] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    options = body or ReEmbedBody()
    tables = options.only or ["userMemories", "contexts", "preferences", "identities", "experiences", "activities"]
    results: dict[str, dict] = {}

    async def _reembed_rows(key, model_cls, text_fields, vector_fields, order_col):
        if key not in tables:
            return
        where_clauses = [model_cls.user_id == user_id]
        if options.startDate:
            where_clauses.append(model_cls.created_at >= _parse_date(options.startDate))
        if options.endDate:
            where_clauses.append(model_cls.created_at <= _parse_date(options.endDate))

        cols_to_select = [model_cls.id] + [getattr(model_cls, tf) for tf in text_fields]
        stmt = select(*cols_to_select).where(and_(*where_clauses)).order_by(asc(order_col))
        if options.limit:
            stmt = stmt.limit(options.limit)
        rows = (await session.execute(stmt)).all()

        succeeded = 0
        failed = 0
        skipped = 0

        for row in rows:
            row_id = row[0]
            texts_to_embed = []
            text_values = []
            for i, tf in enumerate(text_fields):
                val = row[i + 1]
                text_values.append(val)
                if val and val.strip():
                    texts_to_embed.append(val.strip())

            if not texts_to_embed:
                update_vals = {vf: None for vf in vector_fields}
                update_vals["updated_at"] = _now()
                await session.execute(
                    update(model_cls).where(model_cls.id == row_id).values(**update_vals)
                )
                skipped += 1
                continue

            try:
                vecs = await _embed(texts_to_embed)
                update_vals: dict[str, Any] = {"updated_at": _now()}
                vec_idx = 0
                for i, tf in enumerate(text_fields):
                    vf = vector_fields[i]
                    if text_values[i] and text_values[i].strip():
                        update_vals[vf] = vecs[vec_idx] if vec_idx < len(vecs) else None
                        vec_idx += 1
                    else:
                        update_vals[vf] = None
                await session.execute(
                    update(model_cls).where(model_cls.id == row_id).values(**update_vals)
                )
                succeeded += 1
            except Exception as e:
                logger.error("Failed to re-embed %s %s: %s", key, row_id, e)
                failed += 1

        results[key] = {"total": len(rows), "succeeded": succeeded, "failed": failed, "skipped": skipped}

    await _reembed_rows(
        "userMemories", UserMemory,
        ["summary", "details"],
        ["summary_vector_1024", "details_vector_1024"],
        UserMemory.created_at,
    )
    await _reembed_rows(
        "contexts", UserMemoryContext,
        ["description"],
        ["description_vector"],
        UserMemoryContext.created_at,
    )
    await _reembed_rows(
        "preferences", UserMemoryPreference,
        ["conclusion_directives"],
        ["conclusion_directives_vector"],
        UserMemoryPreference.created_at,
    )
    await _reembed_rows(
        "identities", UserMemoryIdentity,
        ["description"],
        ["description_vector"],
        UserMemoryIdentity.created_at,
    )
    await _reembed_rows(
        "activities", UserMemoryActivity,
        ["narrative", "feedback"],
        ["narrative_vector", "feedback_vector"],
        UserMemoryActivity.created_at,
    )
    await _reembed_rows(
        "experiences", UserMemoryExperience,
        ["situation", "action", "key_learning"],
        ["situation_vector", "action_vector", "key_learning_vector"],
        UserMemoryExperience.created_at,
    )

    if not results:
        return {"message": "No memory records matched re-embed criteria", "results": results, "success": True}

    aggregate = {"total": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    for stats in results.values():
        for k in aggregate:
            aggregate[k] += stats.get(k, 0)

    message = (
        "No memory records required re-embedding" if aggregate["total"] == 0
        else f"Re-embedded {aggregate['succeeded']} of {aggregate['total']} records"
    )
    return {"aggregate": aggregate, "message": message, "results": results, "success": True}


# ── Memory detail by layer ───────────────────────────────────────────


@router.get("/memory-detail/{memory_id}")
async def get_memory_detail(
    memory_id: str,
    layer: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mem = await _find_memory(session, user_id, memory_id)
    if not mem:
        return None

    result = _memory_dict(mem)
    effective_layer = layer or mem.memory_layer

    if effective_layer == "identity":
        stmt = select(UserMemoryIdentity).where(
            and_(UserMemoryIdentity.user_memory_id == memory_id, UserMemoryIdentity.user_id == user_id)
        )
        ident = (await session.execute(stmt)).scalar_one_or_none()
        if ident:
            result["identity"] = {
                "id": ident.id, "type": ident.type, "description": ident.description,
                "role": ident.role, "relationship": ident.relationship,
                "episodicDate": ident.episodic_date.isoformat() if ident.episodic_date else None,
                "tags": ident.tags,
            }
    elif effective_layer == "context":
        stmt = select(UserMemoryContext).where(
            and_(UserMemoryContext.user_memory_ids.contains([memory_id]), UserMemoryContext.user_id == user_id)
        )
        ctx = (await session.execute(stmt)).scalar_one_or_none()
        if ctx:
            result["context"] = _context_dict(ctx)
    elif effective_layer == "preference":
        stmt = select(UserMemoryPreference).where(
            and_(UserMemoryPreference.user_memory_id == memory_id, UserMemoryPreference.user_id == user_id)
        )
        pref = (await session.execute(stmt)).scalar_one_or_none()
        if pref:
            result["preference"] = {
                "id": pref.id, "type": pref.type,
                "conclusionDirectives": pref.conclusion_directives,
                "suggestions": pref.suggestions,
                "scorePriority": pref.score_priority,
            }
    elif effective_layer == "activity":
        stmt = select(UserMemoryActivity).where(
            and_(UserMemoryActivity.user_memory_id == memory_id, UserMemoryActivity.user_id == user_id)
        )
        act = (await session.execute(stmt)).scalar_one_or_none()
        if act:
            result["activity"] = _activity_dict(act)
    elif effective_layer == "experience":
        stmt = select(UserMemoryExperience).where(
            and_(UserMemoryExperience.user_memory_id == memory_id, UserMemoryExperience.user_id == user_id)
        )
        exp = (await session.execute(stmt)).scalar_one_or_none()
        if exp:
            result["experience"] = _experience_dict(exp)

    return result


# ── Extraction endpoints ─────────────────────────────────────────────


class ExtractionFromChatTopicsBody(BaseModel):
    fromDate: Optional[str] = None
    toDate: Optional[str] = None


@router.post("/extraction/from-chat-topics")
async def extraction_from_chat_topics(
    body: ExtractionFromChatTopicsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from app.models.misc import AsyncTask
    from_date = _parse_date(body.fromDate)
    to_date = _parse_date(body.toDate)
    task = AsyncTask(
        user_id=user_id,
        type="memory_extraction",
        status="processing",
    )
    session.add(task)
    await session.flush()

    stmt = select(Message).where(and_(Message.user_id == user_id, Message.content.isnot(None)))
    if from_date:
        stmt = stmt.where(Message.created_at >= from_date)
    if to_date:
        stmt = stmt.where(Message.created_at <= to_date)
    stmt = stmt.order_by(desc(Message.created_at)).limit(100)
    messages = list(reversed((await session.execute(stmt)).scalars().all()))
    memory = await _extract_memory_from_messages(
        session,
        user_id,
        messages,
        source={"source": "chat_topics", "fromDate": body.fromDate, "toDate": body.toDate},
    )
    task.status = "success"
    task.error = None
    return {
        "id": task.id,
        "status": task.status,
        "metadata": {"memoryId": memory.id if memory else None, "messageCount": len(messages)},
        "deduped": False,
    }


@router.get("/extraction/task")
async def get_extraction_task(
    taskId: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from app.models.misc import AsyncTask
    if taskId:
        task = (await session.execute(
            select(AsyncTask).where(
                and_(AsyncTask.id == taskId, AsyncTask.user_id == user_id)
            )
        )).scalar_one_or_none()
    else:
        task = (await session.execute(
            select(AsyncTask)
            .where(and_(AsyncTask.user_id == user_id, AsyncTask.type == "memory_extraction"))
            .order_by(desc(AsyncTask.created_at))
            .limit(1)
        )).scalar_one_or_none()

    if not task:
        return None
    return {
        "id": task.id,
        "status": task.status,
        "metadata": {},
        "error": task.error,
    }


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_date(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _empty_search_result() -> dict:
    layer_empty = {"hasMore": False, "returned": 0, "total": 0}
    return {
        "identities": [],
        "preferences": [],
        "activities": [],
        "experiences": [],
        "contexts": [],
        "meta": {
            "appliedFilters": {},
            "appliedQueries": [],
            "layers": {
                "identities": layer_empty,
                "preferences": layer_empty,
                "activities": layer_empty,
                "experiences": layer_empty,
                "contexts": layer_empty,
            },
        },
    }


async def _vector_search(
    session: AsyncSession,
    user_id: str,
    query_vec: list[float],
    model_cls,
    vector_col,
    limit: int,
    dict_fn,
) -> list[dict]:
    try:
        vec_literal = literal_column(f"'{query_vec}'::vector")
        distance = vector_col.op("<=>")(vec_literal)
        stmt = (
            select(model_cls, distance.label("distance"))
            .where(and_(model_cls.user_id == user_id, vector_col.isnot(None)))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return [dict_fn(row[0], float(row[1])) for row in rows]
    except Exception as e:
        logger.warning("Vector search failed for %s: %s", model_cls.__tablename__, e)
        return []


def _identity_search_dict(i: UserMemoryIdentity, distance: float) -> dict:
    return {
        "id": i.id, "type": i.type, "description": i.description,
        "role": i.role, "relationship": i.relationship,
        "episodicDate": i.episodic_date.isoformat() if i.episodic_date else None,
        "createdAt": i.created_at.isoformat() if i.created_at else None,
        "updatedAt": i.updated_at.isoformat() if i.updated_at else None,
        "tags": i.tags, "distance": distance,
    }


def _preference_search_dict(p: UserMemoryPreference, distance: float) -> dict:
    return {
        "id": p.id, "type": p.type,
        "conclusionDirectives": p.conclusion_directives,
        "suggestions": p.suggestions,
        "scorePriority": p.score_priority,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
        "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
        "tags": p.tags, "distance": distance,
    }


def _activity_search_dict(a: UserMemoryActivity, distance: float) -> dict:
    d = _activity_dict(a)
    d["distance"] = distance
    return d


def _experience_search_dict(e: UserMemoryExperience, distance: float) -> dict:
    d = _experience_dict(e)
    d["distance"] = distance
    return d


def _context_search_dict(c: UserMemoryContext, distance: float) -> dict:
    d = _context_dict(c)
    d["distance"] = distance
    return d


async def _enrich_with_layer(
    session: AsyncSession, user_id: str, memory_id: str, layer: str, result: dict,
) -> dict:
    if layer == "identity":
        stmt = select(UserMemoryIdentity).where(
            and_(UserMemoryIdentity.user_memory_id == memory_id, UserMemoryIdentity.user_id == user_id)
        )
        ident = (await session.execute(stmt)).scalar_one_or_none()
        if ident:
            result["identity"] = {
                "id": ident.id, "type": ident.type, "description": ident.description,
                "role": ident.role, "relationship": ident.relationship,
                "episodicDate": ident.episodic_date.isoformat() if ident.episodic_date else None,
                "tags": ident.tags,
            }
    elif layer == "context":
        stmt = select(UserMemoryContext).where(
            and_(UserMemoryContext.user_memory_ids.contains([memory_id]), UserMemoryContext.user_id == user_id)
        )
        ctx = (await session.execute(stmt)).scalar_one_or_none()
        if ctx:
            result["context"] = _context_dict(ctx)
    elif layer == "preference":
        stmt = select(UserMemoryPreference).where(
            and_(UserMemoryPreference.user_memory_id == memory_id, UserMemoryPreference.user_id == user_id)
        )
        pref = (await session.execute(stmt)).scalar_one_or_none()
        if pref:
            result["preference"] = {
                "id": pref.id, "type": pref.type,
                "conclusionDirectives": pref.conclusion_directives,
                "suggestions": pref.suggestions,
                "scorePriority": pref.score_priority,
            }
    elif layer == "activity":
        stmt = select(UserMemoryActivity).where(
            and_(UserMemoryActivity.user_memory_id == memory_id, UserMemoryActivity.user_id == user_id)
        )
        act = (await session.execute(stmt)).scalar_one_or_none()
        if act:
            result["activity"] = _activity_dict(act)
    elif layer == "experience":
        stmt = select(UserMemoryExperience).where(
            and_(UserMemoryExperience.user_memory_id == memory_id, UserMemoryExperience.user_id == user_id)
        )
        exp = (await session.execute(stmt)).scalar_one_or_none()
        if exp:
            result["experience"] = _experience_dict(exp)
    return result


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


def _activity_dict(a: UserMemoryActivity) -> dict[str, Any]:
    return {
        "id": a.id,
        "type": a.type,
        "status": a.status,
        "narrative": a.narrative,
        "notes": a.notes,
        "feedback": a.feedback,
        "tags": a.tags,
        "starts_at": a.starts_at.isoformat() if a.starts_at else None,
        "ends_at": a.ends_at.isoformat() if a.ends_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "associatedObjects": a.associated_objects,
        "associatedSubjects": a.associated_subjects,
        "associatedLocations": a.associated_locations,
        "startsAt": a.starts_at.isoformat() if a.starts_at else None,
        "endsAt": a.ends_at.isoformat() if a.ends_at else None,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
        "updatedAt": a.updated_at.isoformat() if a.updated_at else None,
    }


def _context_dict(c: UserMemoryContext) -> dict[str, Any]:
    return {
        "id": c.id,
        "type": c.type,
        "title": c.title,
        "description": c.description,
        "current_status": c.current_status,
        "tags": c.tags,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "associatedObjects": c.associated_objects,
        "associatedSubjects": c.associated_subjects,
        "currentStatus": c.current_status,
        "scoreImpact": c.score_impact,
        "scoreUrgency": c.score_urgency,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
        "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
    }


def _experience_dict(e: UserMemoryExperience) -> dict[str, Any]:
    return {
        "id": e.id,
        "type": e.type,
        "situation": e.situation,
        "action": e.action,
        "key_learning": e.key_learning,
        "reasoning": e.reasoning,
        "possible_outcome": e.possible_outcome,
        "tags": e.tags,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        "keyLearning": e.key_learning,
        "possibleOutcome": e.possible_outcome,
        "scoreConfidence": e.score_confidence,
        "createdAt": e.created_at.isoformat() if e.created_at else None,
        "updatedAt": e.updated_at.isoformat() if e.updated_at else None,
    }


# ── Memory extraction task endpoints ─────────────────────────────────

@router.get("/extraction-task/{task_id}")
async def get_memory_extraction_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get the status of a memory extraction async task."""
    from app.models.misc import AsyncTask
    task = (await session.execute(
        select(AsyncTask).where(
            and_(AsyncTask.id == task_id, AsyncTask.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return {
        "id": task.id,
        "status": task.status,
        "type": task.type,
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


class RequestMemoryFromTopicBody(BaseModel):
    topic_id: str


@router.post("/request-from-topic")
async def request_memory_from_chat_topic(
    body: RequestMemoryFromTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Extract a base memory from a chat topic."""
    from app.models.misc import AsyncTask
    task = AsyncTask(
        user_id=user_id,
        type="memory_extraction",
        status="processing",
    )
    session.add(task)
    await session.flush()

    messages = (
        await session.execute(
            select(Message)
            .where(and_(Message.topic_id == body.topic_id, Message.user_id == user_id, Message.content.isnot(None)))
            .order_by(Message.created_at)
            .limit(100)
        )
    ).scalars().all()
    memory = await _extract_memory_from_messages(
        session,
        user_id,
        list(messages),
        source={"source": "topic", "topicId": body.topic_id},
    )
    task.status = "success"
    task.error = None
    return {
        "task_id": task.id,
        "status": task.status,
        "memory_id": memory.id if memory else None,
        "message_count": len(messages),
    }
