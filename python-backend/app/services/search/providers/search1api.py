"""Search1API provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_TIME_RANGE_MAP: dict[str, str] = {
    "day": "day",
    "week": "month",  # Search1API has no "week", map to closest
    "month": "month",
    "year": "year",
}


class Search1APIProvider(SearchProvider):
    name = "search1api"

    BASE_URL = "https://api.search1api.com/search"

    @property
    def _api_key(self) -> str | None:
        return settings.search1api_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        time_range = None
        if params.search_time_range and params.search_time_range != "anytime":
            time_range = _TIME_RANGE_MAP.get(params.search_time_range)

        # Build request body — array of query objects
        if params.search_engines and len(params.search_engines) > 0:
            per_engine = max(1, 20 // len(params.search_engines))
            body = [
                {
                    "query": query,
                    "max_results": per_engine,
                    "crawl_results": 0,
                    "image": False,
                    "search_service": engine,
                    **({"time_range": time_range} if time_range else {}),
                }
                for engine in params.search_engines
            ]
        else:
            body = [
                {
                    "query": query,
                    "max_results": 15,
                    "crawl_results": 0,
                    "image": False,
                    **({"time_range": time_range} if time_range else {}),
                }
            ]

        try:
            resp = await client.post(
                self.BASE_URL,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Search1API request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        all_results: list[SearchResult] = []
        for item in data.get("results", []):
            if not item.get("success") or not item.get("data"):
                continue
            sp = item["data"].get("searchParameters", {})
            for r in item["data"].get("results", []):
                all_results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("link", ""),
                    content=r.get("content", "") or r.get("snippet", ""),
                    category="general",
                    engines=[sp.get("search_service", "search1api")],
                    parsed_url=self._parse_hostname(r.get("link", "")),
                    score=1,
                ))

        return SearchResponse(
            query=query,
            results=all_results,
            result_count=len(all_results),
            cost_time_ms=cost,
        )
