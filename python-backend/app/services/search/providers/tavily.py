"""Tavily search provider."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class TavilyProvider(SearchProvider):
    name = "tavily"

    BASE_URL = "https://api.tavily.com"

    @property
    def _api_key(self) -> str | None:
        return settings.tavily_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = self._start_timer()

        body: dict[str, Any] = {
            "query": query,
            "max_results": 15,
            "include_answer": False,
            "include_image_descriptions": True,
            "include_images": False,
            "include_raw_content": False,
            "search_depth": "basic",
        }

        if params.search_time_range and params.search_time_range != "anytime":
            body["time_range"] = params.search_time_range

        if params.search_categories:
            topic = next(
                (c for c in params.search_categories if c in ("news", "general")), None
            )
            if topic:
                body["topic"] = topic

        try:
            resp = await client.post(
                f"{self.BASE_URL}/search",
                json=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}" if self._api_key else "",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Tavily request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                category=body.get("topic", "general"),
                engines=["tavily"],
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

    @staticmethod
    def _start_timer() -> float:
        import time
        return time.monotonic()
