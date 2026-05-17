"""Phase 16 — Briefs: CRUD, resolve, dismiss."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_briefs(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/briefs")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_brief(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/briefs", json={
        "type": "insight",
        "title": "E2E Brief",
        "summary": "Test brief content",
    })
    assert r.status_code in (200, 201)
    body = r.json()
    data = body.get("data") or body
    state.brief_id = data.get("id") or data.get("briefId")


@pytest.mark.asyncio
async def test_get_unresolved_briefs(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/briefs/unresolved")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_brief(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.brief_id:
        pytest.skip("No brief created")
    r = await client.delete(f"/api/briefs/{state.brief_id}")
    assert r.status_code == 200
