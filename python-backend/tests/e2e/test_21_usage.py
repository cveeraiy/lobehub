"""Phase 22 — Usage & API Keys."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── Usage ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_usage_by_month(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/usage/by-month")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_usage_by_day(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/usage/by-day")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_usage_by_range(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/usage/by-range?start=2024-01-01&end=2024-12-31")
    assert r.status_code == 200


# ── API Keys ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_api_key(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/api-keys", json={
        "name": "E2E Test Key",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.api_key_id = data.get("id") or data.get("keyId")


@pytest.mark.asyncio
async def test_list_api_keys(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/api-keys")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_api_key(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.api_key_id:
        pytest.skip("No API key created")
    r = await client.delete(f"/api/api-keys/{state.api_key_id}")
    assert r.status_code == 200
