"""Knowledge base retrieval builtin tool — search KB from within a chat."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)


# ── Context-aware implementation ──────────────────────────────────────


async def knowledge_base_search_with_context(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Vector-based knowledge base search with embedding."""
    from app.services import knowledge_service, llm_service

    query = arguments.get("query", "")
    if not query:
        return json.dumps({"error": "query is required"})

    kb_id = arguments.get("knowledge_base_id")
    limit = min(arguments.get("limit", 5), 20)

    try:
        vectors = await llm_service.embed([query])
        results = await knowledge_service.vector_search(
            session, user_id, vectors[0], kb_id=kb_id, limit=limit,
        )
        return json.dumps([
            {"text": r.get("text", ""), "score": r.get("score")}
            for r in results
        ])
    except Exception as exc:
        logger.error("KB search failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Knowledge base search failed: {exc}"})


# ── Registered tool ──────────────────────────────────────────────────


@register(
    "knowledge_base_search",
    description="Search the user's knowledge bases for relevant documents and chunks. "
    "Use this when the user asks about content from their uploaded files or knowledge bases.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query to search knowledge bases",
            },
            "knowledge_base_id": {
                "type": "string",
                "description": "Optional KB ID to scope the search to a specific knowledge base",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)
async def knowledge_base_search(arguments: dict[str, Any]) -> str:
    """Stub — real implementation via context handler."""
    return json.dumps({"error": "knowledge_base_search requires DB context"})


register_context_handler("knowledge_base_search", knowledge_base_search_with_context)
