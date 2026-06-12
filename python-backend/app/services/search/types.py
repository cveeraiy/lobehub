"""Shared types for the search service layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SearchParams:
    """Parameters forwarded to a search provider query."""

    search_categories: Optional[list[str]] = None
    search_engines: Optional[list[str]] = None
    search_time_range: Optional[str] = None  # "day", "week", "month", "year", "anytime"


@dataclass
class SearchResult:
    """Uniform search result returned by every provider."""

    title: str
    url: str
    content: str
    category: str = "general"
    engines: list[str] = field(default_factory=list)
    parsed_url: str = ""
    score: float = 1.0
    published_date: Optional[str] = None
    thumbnail: Optional[str] = None


@dataclass
class SearchResponse:
    """Uniform response wrapper."""

    query: str
    results: list[SearchResult]
    result_count: int = 0
    cost_time_ms: int = 0
    error_detail: Optional[str] = None
