"""SearchService — orchestrator with fallback chain and retry.

Mirrors the TS ``SearchService`` class:
- Reads ``SEARCH_PROVIDERS`` env (comma-separated) to build a provider list.
- ``query()``  — hit the first provider.
- ``web_search()`` — walk the chain with progressive relaxation of filters.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.services.search.providers.base import SearchProvider
from app.services.search.providers.registry import create_provider
from app.services.search.types import SearchParams, SearchResponse

logger = logging.getLogger(__name__)


def _parse_providers_env(env_val: str | None) -> list[str]:
    """Parse comma-separated (full-width comma tolerated) provider list."""
    if not env_val:
        return []
    cleaned = env_val.replace("\uff0c", ",").strip()
    return [p.strip() for p in cleaned.split(",") if p.strip()]


class SearchService:
    """Unified search service with configurable provider fallback chain."""

    def __init__(self, providers: list[SearchProvider] | None = None) -> None:
        if providers is not None:
            self._providers = providers
        else:
            names = _parse_providers_env(settings.search_providers)
            if names:
                self._providers = [create_provider(n) for n in names]
            else:
                # Fallback: auto-detect from available API keys
                self._providers = self._auto_detect()

        if not self._providers:
            logger.warning("SearchService: no providers configured")

    # ── Public API ───────────────────────────────────────────────────

    async def query(
        self, query: str, params: SearchParams | None = None
    ) -> SearchResponse:
        """Query the first configured provider."""
        if not self._providers:
            return SearchResponse(
                query=query, results=[], error_detail="No search providers configured"
            )
        return await self._query_with_provider(self._providers[0], query, params)

    async def web_search(
        self,
        query: str,
        *,
        search_categories: list[str] | None = None,
        search_engines: list[str] | None = None,
        search_time_range: str | None = None,
    ) -> SearchResponse:
        """Walk the provider chain with progressive filter relaxation.

        1. Try each provider with all filters.
        2. If no results and ``search_engines`` was set, retry without it.
        3. If still no results, retry with no filters at all.
        """
        params = SearchParams(
            search_categories=search_categories,
            search_engines=search_engines,
            search_time_range=search_time_range,
        )

        for provider in self._providers:
            # Attempt 1: full params
            resp = await self._query_with_provider(provider, query, params)
            if resp.results:
                return resp

            # Attempt 2: drop engine restriction
            if search_engines:
                relaxed = SearchParams(
                    search_categories=search_categories,
                    search_time_range=search_time_range,
                )
                resp = await self._query_with_provider(provider, query, relaxed)
                if resp.results:
                    return resp

            # Attempt 3: no filters
            resp = await self._query_with_provider(provider, query)
            if resp.results:
                return resp

        # All providers exhausted
        return SearchResponse(query=query, results=[], result_count=0, cost_time_ms=0)

    # ── Internals ────────────────────────────────────────────────────

    async def _query_with_provider(
        self,
        provider: SearchProvider,
        query: str,
        params: SearchParams | None = None,
    ) -> SearchResponse:
        try:
            return await provider.query(query, params)
        except Exception as exc:
            logger.error(
                "SearchService: provider %s failed: %s", provider.name, exc, exc_info=True,
            )
            return SearchResponse(
                query=query,
                results=[],
                result_count=0,
                error_detail=str(exc),
            )

    @staticmethod
    def _auto_detect() -> list[SearchProvider]:
        """Build provider list from available env-var API keys."""
        detected: list[SearchProvider] = []

        # Order: most common first
        if settings.tavily_api_key:
            from app.services.search.providers.tavily import TavilyProvider
            detected.append(TavilyProvider())
        if settings.searxng_url:
            from app.services.search.providers.searxng import SearXNGProvider
            detected.append(SearXNGProvider())
        if settings.serper_api_key:
            from app.services.search.providers.serper import SerperProvider
            detected.append(SerperProvider())
        if settings.brave_api_key:
            from app.services.search.providers.brave import BraveProvider
            detected.append(BraveProvider())
        if settings.google_pse_api_key and settings.google_pse_engine_id:
            from app.services.search.providers.google import GoogleProvider
            detected.append(GoogleProvider())
        if settings.exa_api_key:
            from app.services.search.providers.exa import ExaProvider
            detected.append(ExaProvider())
        if settings.jina_api_key:
            from app.services.search.providers.jina import JinaProvider
            detected.append(JinaProvider())
        if settings.firecrawl_api_key:
            from app.services.search.providers.firecrawl import FirecrawlProvider
            detected.append(FirecrawlProvider())
        if settings.kagi_api_key:
            from app.services.search.providers.kagi import KagiProvider
            detected.append(KagiProvider())
        if settings.bocha_api_key:
            from app.services.search.providers.bocha import BochaProvider
            detected.append(BochaProvider())
        if settings.search1api_api_key:
            from app.services.search.providers.search1api import Search1APIProvider
            detected.append(Search1APIProvider())
        if settings.anspire_api_key:
            from app.services.search.providers.anspire import AnspireProvider
            detected.append(AnspireProvider())

        return detected


# ── Module-level singleton ────────────────────────────────────────────
search_service = SearchService()
