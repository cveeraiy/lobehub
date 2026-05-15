"""Kagi search provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class KagiProvider(SearchProvider):
    name = "kagi"

    BASE_URL = "https://kagi.com/api/v0/search"

    @property
    def _api_key(self) -> str | None:
        return settings.kagi_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        qs: dict[str, Any] = {"q": query, "limit": 15}

        try:
            resp = await client.get(
                self.BASE_URL,
                params=qs,
                headers={"Authorization": f"Bot {self._api_key}" if self._api_key else ""},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Kagi request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("snippet", ""),
                category="general",
                engines=["kagi"],
                parsed_url=self._parse_hostname(r.get("url", "")),
                score=1,
            )
            for r in data.get("data", [])
        ]

        return SearchResponse(
            query=query,
            results=results,
            result_count=len(results),
            cost_time_ms=cost,
        )
