"""Phase 27 — Recent: recently accessed items listing."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


# ── 27.1  Get recent items ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_recent(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/recent")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_recent_with_limit(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/recent", params={"limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5
