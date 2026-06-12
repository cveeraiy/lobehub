"""Unified search service with pluggable provider backends.

Architecture mirrors the TS ``src/server/services/search/`` module:

- ``SearchProvider`` — abstract interface every backend implements
- ``SearchService``  — orchestrator with fallback chain, retry logic
- ``search_service`` — pre-built singleton

Supported backends: tavily, brave, google, exa, searxng, jina, firecrawl,
kagi, bocha, search1api, anspire, serper.
"""

from app.services.search.service import SearchService, search_service
from app.services.search.types import (
    SearchParams,
    SearchResult,
    SearchResponse,
)
from app.services.search.providers.base import SearchProvider

__all__ = [
    "SearchService",
    "search_service",
    "SearchParams",
    "SearchResult",
    "SearchResponse",
    "SearchProvider",
]
