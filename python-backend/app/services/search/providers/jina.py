"""Jina Reader search provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class JinaProvider(SearchProvider):
    name = "jina"

    BASE_URL = "https://s.jina.ai/"

    @property
    def _api_key(self) -> str | None:
        return settings.jina_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        body: dict[str, Any] = {"q": query}

        try:
            resp = await client.post(
                self.BASE_URL,
                json=body,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
                    "Content-Type": "application/json",
                    "X-Respond-With": "no-content",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Jina request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("description", ""),
                category="general",
                engines=["jina"],
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
