"""Phase 20 — Share & Export/Import."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_create_share(client: httpx.AsyncClient, state: SharedState) -> None:
    # Need a session and topic first
    r = await client.post("/api/sessions", json={"type": "agent", "meta": {"title": "Share Session"}})
    assert r.status_code == 201
    session_id = r.json().get("id") or r.json().get("sessionId")
    state.session_id = session_id

    r = await client.post("/api/topics", json={"session_id": session_id, "title": "Share Topic"})
    assert r.status_code == 201
    topic_id = r.json().get("id") or r.json().get("topicId")

    r = await client.post("/api/share", json={
        "topic_id": topic_id,
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.share_id = data.get("id") or data.get("shareId")


@pytest.mark.asyncio
async def test_get_share(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.share_id:
        pytest.skip("No share created")
    r = await client.get(f"/api/share/{state.share_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_share(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.share_id:
        pytest.skip("No share")
    r = await client.delete(f"/api/share/{state.share_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.session_id:
        await client.delete(f"/api/sessions/{state.session_id}")
