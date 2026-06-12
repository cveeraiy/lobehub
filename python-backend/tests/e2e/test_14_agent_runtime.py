"""Phase 15 — Agent Runtime (direct Python endpoints)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_agent_run_health(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/agent/run", json={})
    # /api/agent/run may return 200 (health) or 422 (missing fields)
    assert r.status_code in (200, 422)


@pytest.mark.asyncio
async def test_list_operations(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent/operations")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio
async def test_get_status_nonexistent(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent/status/nonexistent-op")
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_interrupt_nonexistent(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/agent/interrupt/nonexistent-op")
    assert r.status_code in (200, 400, 404)


@pytest.mark.asyncio
async def test_delete_nonexistent(client: httpx.AsyncClient) -> None:
    r = await client.delete("/api/agent/nonexistent-op")
    assert r.status_code in (200, 404)
