"""Exa AI search provider."""

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


class ExaProvider(SearchProvider):
    name = "exa"

    BASE_URL = "https://api.exa.ai"

    @property
    def _api_key(self) -> str | None:
        return settings.exa_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        body: dict[str, Any] = {
            "query": query,
            "numResults": 10,
            "type": "auto",
        }

        if params.search_time_range and params.search_time_range != "anytime":
            days = _DAYS_MAP.get(params.search_time_range)
            if days:
                now = datetime.now(timezone.utc)
                body["endPublishedDate"] = now.isoformat()
                body["startPublishedDate"] = (now - timedelta(days=days)).isoformat()

        if params.search_categories:
            cat = next((c for c in params.search_categories if c == "news"), None)
            if cat:
                body["category"] = cat

        try:
            resp = await client.post(
                f"{self.BASE_URL}/search",
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self._api_key or "",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Exa request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("text", ""),
                category=body.get("category", "general"),
                engines=["exa"],
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
