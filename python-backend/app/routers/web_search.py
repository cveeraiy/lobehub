"""Web search API router — exposes the unified search service over HTTP."""

from __future__ import annotations

import json
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


class CrawlRequest(BaseModel):
    urls: list[str]
    impls: Optional[list[str]] = None


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


def _crawl_result(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("error"):
        return {
            "crawler": "python-url-crawler",
            "data": {
                "content": str(payload["error"]),
                "errorMessage": str(payload["error"]),
                "errorType": "CrawlError",
                "url": url,
            },
            "originalUrl": url,
        }

    return {
        "crawler": "python-url-crawler",
        "data": {
            "content": payload.get("content", ""),
            "contentType": "json" if payload.get("content_type") == "application/json" else "text",
            "length": payload.get("length"),
            "title": payload.get("title") or "",
            "url": payload.get("url") or url,
        },
        "originalUrl": url,
    }


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


@router.post("/crawl")
async def crawl_pages(
    body: CrawlRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Crawl pages and return the same uniform result shape as the TS crawler service."""
    from app.tools.url_crawler import url_crawler

    results: list[dict[str, Any]] = []
    for url in body.urls:
        raw = await url_crawler({"url": url})
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": raw}
        results.append(_crawl_result(url, payload))

    return {"results": results}


@router.get("/providers")
async def list_providers(user_id: str = Depends(get_current_user_id)):
    """Return available search provider identifiers."""
    return {"providers": available_providers()}
