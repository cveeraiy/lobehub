"""Memory builtin tool — search and store user memories from within a chat.

Supports 5-layer memory model: event, semantic, episodic, procedural, persona.
Context-aware handlers use embedding-based vector search and auto-embedding storage.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)


# ── Context-aware implementations ────────────────────────────────────


async def memory_search_with_context(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Vector-based memory search with layer/category filters."""
    from app.services import llm_service, memory_service

    query = arguments.get("query", "")
    if not query:
        return json.dumps({"error": "query is required"})

    layer = arguments.get("layer")
    category = arguments.get("category")
    limit = min(arguments.get("limit", 10), 20)

    try:
        vectors = await llm_service.embed([query])
        query_embedding = vectors[0] if vectors else None
    except Exception as exc:
        logger.warning("Embedding failed, falling back to text search: %s", exc)
        query_embedding = None

    try:
        if query_embedding:
            results = await memory_service.search_memories_by_vector(
                session, user_id, query_embedding,
                layer=layer, category=category, limit=limit,
            )
        else:
            results = await memory_service.search_memories(
                session, user_id, query,
                layer=layer, category=category, limit=limit,
            )
    except Exception as exc:
        logger.error("Memory search failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Memory search failed: {exc}"})

    return json.dumps({
        "query": query,
        "total": len(results),
        "memories": [
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "summary": r.get("summary") or r.get("content", ""),
                "layer": r.get("layer"),
                "category": r.get("category"),
                "score": r.get("score"),
                "created_at": r.get("created_at"),
            }
            for r in results
        ],
    })


async def memory_store_with_context(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Store a memory with auto-embedding, supporting all 5 layers."""
    from app.services import llm_service, memory_service

    summary = arguments.get("summary", "")
    if not summary:
        return json.dumps({"error": "summary is required"})

    title = arguments.get("title")
    details = arguments.get("details")
    layer = arguments.get("layer", "semantic")
    memory_type = arguments.get("memory_type")
    category = arguments.get("category")
    tags = arguments.get("tags")

    # Generate embedding
    embed_text = f"{title or ''} {summary} {details or ''}".strip()
    try:
        vectors = await llm_service.embed([embed_text])
        embedding = vectors[0] if vectors else None
    except Exception as exc:
        logger.warning("Embedding generation failed: %s", exc)
        embedding = None

    try:
        memory = await memory_service.create_memory(
            session,
            user_id=user_id,
            content=summary,
            title=title,
            layer=layer,
            memory_type=memory_type,
            category=category,
            tags=tags,
            embedding=embedding,
            metadata={"details": details} if details else None,
        )
        return json.dumps({
            "status": "stored",
            "memory_id": memory.get("id") if isinstance(memory, dict) else str(memory.id),
            "layer": layer,
            "summary": summary[:100],
        })
    except Exception as exc:
        logger.error("Memory store failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Memory store failed: {exc}"})


# ── Registered tools (context-backed) ────────────────────────────────


@register(
    "memory_search",
    description="Search user memories by semantic similarity. Supports 5 layers: "
    "event, semantic, episodic, procedural, persona.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "layer": {
                "type": "string",
                "enum": ["event", "semantic", "episodic", "procedural", "persona"],
                "description": "Filter by memory layer",
            },
            "category": {
                "type": "string",
                "description": "Filter by category",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10, max 20)",
                "default": 10,
            },
        },
        "required": ["query"],
    },
)
async def memory_search(arguments: dict[str, Any]) -> str:
    """Context-required fallback; real implementation uses memory_search_with_context."""
    return json.dumps({"error": "memory_search requires DB context"})


@register(
    "memory_store",
    description="Store a new user memory with automatic embedding. Supports 5 layers: "
    "event, semantic, episodic, procedural, persona.",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Brief summary of the memory"},
            "title": {"type": "string", "description": "Optional title"},
            "details": {"type": "string", "description": "Detailed content of the memory"},
            "layer": {
                "type": "string",
                "description": "Memory layer",
                "enum": ["event", "semantic", "episodic", "procedural", "persona"],
                "default": "semantic",
            },
            "memory_type": {"type": "string", "description": "Sub-type within the layer"},
            "category": {"type": "string", "description": "Category tag"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for organization",
            },
        },
        "required": ["summary"],
    },
)
async def memory_store(arguments: dict[str, Any]) -> str:
    """Context-required fallback; real implementation uses memory_store_with_context."""
    return json.dumps({"error": "memory_store requires DB context"})


register_context_handler("memory_search", memory_search_with_context)
register_context_handler("memory_store", memory_store_with_context)
