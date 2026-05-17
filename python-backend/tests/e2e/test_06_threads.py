"""Phase 7 — Threads: CRUD + messages."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_create_thread(client: httpx.AsyncClient, state: SharedState) -> None:
    # Ensure a topic exists first
    r = await client.post("/api/sessions", json={"type": "agent", "meta": {"title": "Thread Session"}})
    assert r.status_code == 201
    state.session_id = r.json().get("id") or r.json().get("sessionId")

    r = await client.post("/api/topics", json={"session_id": state.session_id, "title": "Thread Topic"})
    assert r.status_code == 201
    state.topic_id = r.json().get("id") or r.json().get("topicId")

    r = await client.post("/api/threads", json={
        "topic_id": state.topic_id,
        "title": "E2E Thread",
    })
    assert r.status_code == 201
    data = r.json()
    state.thread_id = data.get("id") or data.get("threadId")
    assert state.thread_id


@pytest.mark.asyncio
async def test_list_threads(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/threads")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_thread(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.thread_id
    r = await client.get(f"/api/threads/{state.thread_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_thread(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.thread_id
    r = await client.put(f"/api/threads/{state.thread_id}", json={
        "title": "Updated Thread",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_thread_messages(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.thread_id
    r = await client.get(f"/api/threads/{state.thread_id}/messages")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_thread(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.thread_id
    r = await client.delete(f"/api/threads/{state.thread_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.topic_id:
        await client.delete(f"/api/topics/{state.topic_id}")
    if state.session_id:
        await client.delete(f"/api/sessions/{state.session_id}")
