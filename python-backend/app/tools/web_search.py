"""Web search builtin tool — delegates to the unified SearchService.

Supports 12 providers: tavily, brave, google, exa, searxng, jina,
firecrawl, kagi, bocha, search1api, anspire, serper.

Configure via ``SEARCH_PROVIDERS`` env (comma-separated chain) or
individual ``*_API_KEY`` env vars for auto-detection.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.search.service import search_service
from app.services.search.types import SearchParams
from app.tools.registry import register

logger = logging.getLogger(__name__)


@register(
    "web_search",
    description="Search the web for current information. Returns titles, snippets, and URLs.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {
                "type": "integer",
                "description": "Max results (default 15)",
                "default": 15,
            },
            "time_range": {
                "type": "string",
                "description": "Time filter: day, week, month, year, or anytime",
                "enum": ["day", "week", "month", "year", "anytime"],
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Search categories, e.g. ['news', 'general']",
            },
        },
        "required": ["query"],
    },
)
async def web_search(arguments: dict[str, Any]) -> str:
    query = arguments.get("query", "")
    max_results = arguments.get("max_results", 15)

    if not query:
        return json.dumps({"error": "query is required"})

    try:
        resp = await search_service.web_search(
            query,
            search_categories=arguments.get("categories"),
            search_time_range=arguments.get("time_range"),
        )
    except Exception as exc:
        logger.error("Web search failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Search failed: {exc}"})

    # Trim to requested max
    results = resp.results[:max_results]

    return json.dumps({
        "query": query,
        "results": [
            {
                "title": r.title,
                "snippet": r.content,
                "url": r.url,
                "score": r.score,
            }
            for r in results
        ],
        "provider": results[0].engines[0] if results and results[0].engines else "none",
        "cost_time_ms": resp.cost_time_ms,
    })
