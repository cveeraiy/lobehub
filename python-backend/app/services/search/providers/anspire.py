"""Anspire search provider."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_DAYS_MAP = {"day": 1, "week": 7, "month": 30, "year": 365}


class AnspireProvider(SearchProvider):
    name = "anspire"

    BASE_URL = "https://plugin.anspire.cn/api/ntsearch/search"

    @property
    def _api_key(self) -> str | None:
        return settings.anspire_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        qs: dict[str, Any] = {"query": query, "top_k": 20, "mode": 0}

        if params.search_time_range and params.search_time_range != "anytime":
            days = _DAYS_MAP.get(params.search_time_range)
            if days:
                now = datetime.now(timezone.utc)
                fmt = "%Y-%m-%d %H:%M:%S"
                qs["FromTime"] = (now - timedelta(days=days)).strftime(fmt)
                qs["ToTime"] = now.strftime(fmt)

        try:
            resp = await client.get(
                self.BASE_URL,
                params=qs,
                headers={
                    "Accept": "*/*",
                    "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Anspire request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                category="general",
                engines=["anspire"],
                parsed_url=self._parse_hostname(r.get("url", "")),
                score=r.get("score", 0),
            )
            for r in data.get("results", [])
        ]

        return SearchResponse(
            query=query,
            results=results,
            result_count=len(results),
            cost_time_ms=cost,
        )
