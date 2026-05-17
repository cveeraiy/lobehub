"""Phase 28 — Search: unified cross-domain search."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


# ── 28.1  Search with results ───────────────────────────────────────

@pytest.mark.asyncio
async def test_search(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": "test"})
    assert r.status_code == 200
    data = r.json()
    assert "messages" in data
    assert "topics" in data
    assert "agents" in data
    assert isinstance(data["messages"], list)
    assert isinstance(data["topics"], list)
    assert isinstance(data["agents"], list)


# ── 28.2  Search with no results ────────────────────────────────────

@pytest.mark.asyncio
async def test_search_no_results(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": "zzz_impossible_query_zzz"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["messages"]) == 0
    assert len(data["topics"]) == 0
    assert len(data["agents"]) == 0


# ── 28.3  Search with custom limit ──────────────────────────────────

@pytest.mark.asyncio
async def test_search_with_limit(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": "test", "limit": 3})
    assert r.status_code == 200
    data = r.json()
    assert len(data["messages"]) <= 3
    assert len(data["topics"]) <= 3
    assert len(data["agents"]) <= 3


# ── 28.4  Search requires q param ───────────────────────────────────

@pytest.mark.asyncio
async def test_search_missing_query(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/search")
    assert r.status_code == 422  # missing required query param
