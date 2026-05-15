"""Google Programmable Search Engine (PSE) provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_TIME_RANGE_MAP = {"day": "d1", "week": "w1", "month": "m1", "year": "y1"}


class GoogleProvider(SearchProvider):
    name = "google"

    BASE_URL = "https://www.googleapis.com/customsearch/v1"

    @property
    def _api_key(self) -> str | None:
        return settings.google_pse_api_key

    @property
    def _engine_id(self) -> str | None:
        return settings.google_pse_engine_id

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        qs: dict[str, Any] = {
            "q": query,
            "key": self._api_key or "",
            "cx": self._engine_id or "",
            "num": 10,
        }

        if params.search_time_range and params.search_time_range != "anytime":
            dr = _TIME_RANGE_MAP.get(params.search_time_range)
            if dr:
                qs["dateRestrict"] = dr

        try:
            resp = await client.get(self.BASE_URL, params=qs)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Google PSE request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                content=r.get("snippet", ""),
                category="general",
                engines=["google"],
                parsed_url=self._parse_hostname(r.get("link", "")),
                score=1,
            )
            for r in data.get("items", [])
        ]

        return SearchResponse(
            query=query,
            results=results,
            result_count=len(results),
            cost_time_ms=cost,
        )
