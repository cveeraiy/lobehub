"""Web search API router — exposes the unified search service over HTTP."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_current_user_id
from app.services.search.service import search_service
from app.services.search.providers.registry import available_providers

router = APIRouter(prefix="/api/web-search", tags=["Web Search"])


class WebSearchRequest(BaseModel):
    query: str
    search_categories: Optional[list[str]] = None
    search_engines: Optional[list[str]] = None
    search_time_range: Optional[str] = None


class SearchResultItem(BaseModel):
    title: str
    url: str
    content: str
    category: str = "general"
    engines: list[str] = []
    parsed_url: str = ""
    score: float = 1.0


class WebSearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    result_count: int = 0
    cost_time_ms: int = 0


@router.post("", response_model=WebSearchResponse)
async def web_search(
    body: WebSearchRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Execute a web search using the configured provider chain."""
    resp = await search_service.web_search(
        body.query,
        search_categories=body.search_categories,
        search_engines=body.search_engines,
        search_time_range=body.search_time_range,
    )
    return WebSearchResponse(
        query=resp.query,
        results=[
            SearchResultItem(
                title=r.title,
                url=r.url,
                content=r.content,
                category=r.category,
                engines=r.engines,
                parsed_url=r.parsed_url,
                score=r.score,
            )
            for r in resp.results
        ],
        result_count=resp.result_count,
        cost_time_ms=resp.cost_time_ms,
    )


@router.get("/providers")
async def list_providers(user_id: str = Depends(get_current_user_id)):
    """Return available search provider identifiers."""
    return {"providers": available_providers()}
