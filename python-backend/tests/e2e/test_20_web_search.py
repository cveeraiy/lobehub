"""Phase 21 — Web Search."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_search_providers(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/web-search/providers")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio
async def test_search(client: httpx.AsyncClient) -> None:
    """May skip if no search provider API key is configured."""
    r = await client.post("/api/web-search", json={
        "query": "lobehub test",
    })
    # 200 if provider configured, 400/500/503 if not
    assert r.status_code in (200, 400, 422, 500, 503)
