"""Phase 5 — Topics: CRUD + search + count."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_create_session_for_topics(client: httpx.AsyncClient, state: SharedState) -> None:
    """Create a session to attach topics to."""
    r = await client.post("/api/sessions", json={
        "type": "agent",
        "meta": {"title": "Topic Test Session"},
    })
    assert r.status_code == 201
    state.session_id = r.json().get("id") or r.json().get("sessionId")


@pytest.mark.asyncio
async def test_create_topic(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id
    r = await client.post("/api/topics", json={
        "session_id": state.session_id,
        "title": "E2E Test Topic",
    })
    assert r.status_code == 201
    data = r.json()
    state.topic_id = data.get("id") or data.get("topicId")
    assert state.topic_id


@pytest.mark.asyncio
async def test_list_topics(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id
    r = await client.get(f"/api/topics?session_id={state.session_id}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_topic(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.topic_id
    r = await client.get(f"/api/topics/{state.topic_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_topic(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.topic_id
    r = await client.put(f"/api/topics/{state.topic_id}", json={
        "title": "Renamed E2E Topic",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_topic(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.topic_id
    r = await client.delete(f"/api/topics/{state.topic_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_session(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.session_id:
        await client.delete(f"/api/sessions/{state.session_id}")
