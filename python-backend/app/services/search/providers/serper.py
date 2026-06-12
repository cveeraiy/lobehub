"""Serper (Google) search provider — carried over from the old web_search tool."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.services.search.providers.base import SearchProvider
from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class SerperProvider(SearchProvider):
    name = "serper"

    BASE_URL = "https://google.serper.dev/search"

    @property
    def _api_key(self) -> str | None:
        return settings.serper_api_key

    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        params = params or SearchParams()
        client = get_client()
        start = time.monotonic()

        body: dict[str, Any] = {"q": query, "num": 15}

        try:
            resp = await client.post(
                self.BASE_URL,
                json=body,
                headers={
                    "X-API-KEY": self._api_key or "",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Serper request failed: %s", exc)
            return self._empty_response(query, error=str(exc))

        data = resp.json()
        cost = self._elapsed_ms(start)

        all_results: list[SearchResult] = []

        # Answer box
        answer = data.get("answerBox", {}).get("answer")
        if answer:
            all_results.append(SearchResult(
                title="Answer",
                url="",
                content=answer,
                category="answer",
                engines=["serper"],
                score=2,
            ))

        for r in data.get("organic", []):
            all_results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                content=r.get("snippet", ""),
                category="general",
                engines=["serper"],
                parsed_url=self._parse_hostname(r.get("link", "")),
                score=1,
            ))

        return SearchResponse(
            query=query,
            results=all_results,
            result_count=len(all_results),
            cost_time_ms=cost,
        )
