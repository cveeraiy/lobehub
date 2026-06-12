"""Firecrawl search provider (V2 API)."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_TIME_RANGE_MAP = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}


class FirecrawlProvider(SearchProvider):
    name = "firecrawl"

    @property
    def _api_key(self) -> str | None:
        return settings.firecrawl_api_key

    @property
    def _base_url(self) -> str:
        return settings.firecrawl_url or "https://api.firecrawl.dev/v2"

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        body: dict[str, Any] = {
            "query": query,
            "limit": 20,
            "sources": [{"type": "web"}, {"type": "news"}],
        }

        if params.search_time_range and params.search_time_range != "anytime":
            tbs = _TIME_RANGE_MAP.get(params.search_time_range)
            if tbs:
                body["tbs"] = tbs

        try:
            resp = await client.post(
                f"{self._base_url.rstrip('/')}/search",
                json=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Firecrawl request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        all_results: list[SearchResult] = []

        # Web results
        for r in data.get("data", {}).get("web", []):
            all_results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("description", "") or r.get("markdown", ""),
                category="general",
                engines=["firecrawl"],
                parsed_url=self._parse_hostname(r.get("url", "")),
                score=1,
            ))

        # News results
        for r in data.get("data", {}).get("news", []):
            all_results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("snippet", "") or r.get("markdown", ""),
                category="news",
                engines=["firecrawl"],
                parsed_url=self._parse_hostname(r.get("url", "")),
                score=1,
            ))

        return SearchResponse(
            query=query,
            results=all_results,
            result_count=len(all_results),
            cost_time_ms=cost,
        )
