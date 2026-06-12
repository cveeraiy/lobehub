"""Memory service — 5-layer user memory CRUD + vector search.

Manages the ``user_memories`` table (base layer) which stores all five
memory layers (event, semantic, episodic, procedural, persona) in one
table, differentiated by ``memory_layer``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import UserMemory
from app.services import llm_service

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Memory layers ────────────────────────────────────────────────────
MEMORY_LAYERS = ("event", "semantic", "episodic", "procedural", "persona")


# ─────────────────────────────────────────────────────────────────────
#  CRUD
# ─────────────────────────────────────────────────────────────────────

async def create_memory(
    session: AsyncSession,
    user_id: str,
    *,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    details: Optional[str] = None,
    memory_layer: str = "semantic",
    memory_type: Optional[str] = None,
    memory_category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    embed_model: str = "openai/text-embedding-3-small",
    api_key: Optional[str] = None,
) -> UserMemory:
    """Create a memory record, optionally embedding summary + details."""
    mem = UserMemory(
        user_id=user_id,
        title=title,
        summary=summary,
        details=details,
        memory_layer=memory_layer,
        memory_type=memory_type,
        memory_category=memory_category,
        tags=tags,
        metadata_=metadata,
    )

    # Embed summary and details vectors
    texts_to_embed: list[tuple[str, str]] = []  # (field_name, text)
    if summary:
        texts_to_embed.append(("summary_vector_1024", summary))
    if details:
        texts_to_embed.append(("details_vector_1024", details))

    if texts_to_embed:
        try:
            raw_texts = [t for _, t in texts_to_embed]
            vectors = await llm_service.embed(raw_texts, model=embed_model, api_key=api_key)
            for (field_name, _), vec in zip(texts_to_embed, vectors):
                setattr(mem, field_name, vec)
        except Exception:
            logger.warning("Failed to embed memory text; storing without vectors", exc_info=True)

    session.add(mem)
    await session.flush()
    return mem


async def get_memory(
    session: AsyncSession,
    user_id: str,
    memory_id: str,
) -> UserMemory | None:
    stmt = select(UserMemory).where(
        and_(UserMemory.id == memory_id, UserMemory.user_id == user_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_memories(
    session: AsyncSession,
    user_id: str,
    *,
    layer: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[UserMemory]:
    stmt = (
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.last_accessed_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if layer:
        stmt = stmt.where(UserMemory.memory_layer == layer)
    if category:
        stmt = stmt.where(UserMemory.memory_category == category)
    return list((await session.execute(stmt)).scalars().all())


async def update_memory(
    session: AsyncSession,
    user_id: str,
    memory_id: str,
    **values: Any,
) -> None:
    values["updated_at"] = _now()
    stmt = (
        update(UserMemory)
        .where(and_(UserMemory.id == memory_id, UserMemory.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)


async def delete_memory(
    session: AsyncSession,
    user_id: str,
    memory_id: str,
) -> None:
    await session.execute(
        delete(UserMemory).where(
            and_(UserMemory.id == memory_id, UserMemory.user_id == user_id)
        )
    )


# ─────────────────────────────────────────────────────────────────────
#  Vector search
# ─────────────────────────────────────────────────────────────────────

async def search_memories(
    session: AsyncSession,
    user_id: str,
    query_vector: list[float],
    *,
    layer: Optional[str] = None,
    limit: int = 10,
    vector_field: str = "summary",
) -> list[dict[str, Any]]:
    """Search memories by cosine similarity on summary or details vector.

    ``vector_field`` can be ``"summary"`` or ``"details"``.
    """
    from sqlalchemy import literal_column

    col = (
        UserMemory.summary_vector_1024
        if vector_field == "summary"
        else UserMemory.details_vector_1024
    )
    # Use proper vector literal instead of str() to avoid SQL text bloat
    vec_literal = literal_column(f"'{query_vector}'::vector")
    distance = col.op("<=>")(vec_literal)

    stmt = (
        select(
            UserMemory.id,
            UserMemory.title,
            UserMemory.summary,
            UserMemory.memory_layer,
            UserMemory.memory_category,
            UserMemory.tags,
            distance.label("distance"),
        )
        .where(and_(UserMemory.user_id == user_id, col.isnot(None)))
        .order_by(distance)
        .limit(limit)
    )
    if layer:
        stmt = stmt.where(UserMemory.memory_layer == layer)

    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "summary": r.summary,
            "memory_layer": r.memory_layer,
            "memory_category": r.memory_category,
            "tags": r.tags,
            "distance": float(r.distance),
        }
        for r in rows
    ]


async def search_memories_by_text(
    session: AsyncSession,
    user_id: str,
    query: str,
    *,
    model: str = "openai/text-embedding-3-small",
    api_key: Optional[str] = None,
    layer: Optional[str] = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Convenience: embed query text then search."""
    vectors = await llm_service.embed([query], model=model, api_key=api_key)
    return await search_memories(
        session, user_id, vectors[0], layer=layer, limit=limit
    )
