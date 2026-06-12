"""Abstract base for search providers."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

from app.services.search.types import SearchParams, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


class SearchProvider(ABC):
    """Every search backend must implement ``query``."""

    name: str = "base"

    @abstractmethod
    async def query(self, query: str, params: SearchParams | None = None) -> SearchResponse:
        """Execute a search and return uniform results."""
        ...

    # ── Helpers available to all providers ──────────────────────────

    @staticmethod
    def _parse_hostname(url: str) -> str:
        try:
            return urlparse(url).hostname or ""
        except Exception:
            return ""

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.monotonic() - start) * 1000)

    def _empty_response(self, query: str, *, error: str | None = None) -> SearchResponse:
        return SearchResponse(query=query, results=[], result_count=0, error_detail=error)
