"""Bocha AI search provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_TIME_RANGE_MAP = {"day": "oneDay", "week": "oneWeek", "month": "oneMonth", "year": "oneYear"}


class BochaProvider(SearchProvider):
    name = "bocha"

    BASE_URL = "https://api.bochaai.com/v1/web-search"

    @property
    def _api_key(self) -> str | None:
        return settings.bocha_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        body: dict[str, Any] = {"query": query, "count": 15, "summary": True}

        if params.search_time_range and params.search_time_range != "anytime":
            freshness = _TIME_RANGE_MAP.get(params.search_time_range)
            if freshness:
                body["freshness"] = freshness

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
            logger.error("Bocha request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        pages = data.get("data", {}).get("webPages", {}).get("value", [])
        results = [
            SearchResult(
                title=r.get("name", ""),
                url=r.get("url", ""),
                content=r.get("summary", "") or r.get("snippet", ""),
                category="general",
                engines=["bocha"],
                parsed_url=self._parse_hostname(r.get("url", "")),
                score=1,
            )
            for r in pages
        ]

        return SearchResponse(
            query=query,
            results=results,
            result_count=len(results),
            cost_time_ms=cost,
        )
