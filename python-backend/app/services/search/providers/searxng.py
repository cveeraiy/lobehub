"""SearXNG search provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class SearXNGProvider(SearchProvider):
    name = "searxng"

    @property
    def _base_url(self) -> str | None:
        return settings.searxng_url

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        base = self._base_url
        if not base:
            return self._empty_response(query, error="SEARXNG_URL not configured")

        base = base.rstrip("/")
        client = get_client()
        start = time.monotonic()

        qs: dict[str, Any] = {"q": query, "format": "json"}
        if params.search_categories:
            qs["categories"] = ",".join(params.search_categories)
        if params.search_engines:
            qs["engines"] = ",".join(params.search_engines)
        if params.search_time_range and params.search_time_range != "anytime":
            qs["time_range"] = params.search_time_range

        try:
            resp = await client.get(f"{base}/search", params=qs)
            # SearXNG returns 500 for empty results
            if resp.status_code == 500:
                body_text = resp.text.lower()
                if "empty results" in body_text:
                    return self._empty_response(query)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("SearXNG request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                category=r.get("category", "general"),
                engines=r.get("engines", []),
                parsed_url=self._parse_hostname(r.get("url", "")),
                score=r.get("score", 0),
                published_date=r.get("publishedDate") or None,
                thumbnail=r.get("thumbnail") or None,
            )
            for r in data.get("results", [])
        ]

        return SearchResponse(
            query=query,
            results=results,
            result_count=data.get("number_of_results", len(results)),
            cost_time_ms=cost,
        )
