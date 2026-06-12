"""Brave Search provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_TIME_RANGE_MAP = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}


class BraveProvider(SearchProvider):
    name = "brave"

    BASE_URL = "https://api.search.brave.com/res/v1"

    @property
    def _api_key(self) -> str | None:
        return settings.brave_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        qs: dict[str, Any] = {"q": query, "count": 15, "result_filter": "web"}

        if params.search_time_range and params.search_time_range != "anytime":
            freshness = _TIME_RANGE_MAP.get(params.search_time_range)
            if freshness:
                qs["freshness"] = freshness

        try:
            resp = await client.get(
                f"{self.BASE_URL}/web/search",
                params=qs,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self._api_key or "",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Brave request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        web_results = data.get("web", {}).get("results", [])
        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("description", ""),
                category="general",
                engines=["brave"],
                parsed_url=self._parse_hostname(r.get("url", "")),
                score=1,
            )
            for r in web_results
        ]

        return SearchResponse(
            query=query,
            results=results,
            result_count=len(results),
            cost_time_ms=cost,
        )
