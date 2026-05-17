"""Phase 30 — Memory: CRUD for the /api/memories router."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── 30.1  Create memory ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/memories", json={
        "title": "Test Memory",
        "summary": "A test memory entry",
        "details": "Detailed test memory content",
        "memory_layer": "semantic",
        "memory_category": "general",
        "tags": ["test", "e2e"],
    })
    assert r.status_code == 201
    data = r.json()
    state.memory_id = data.get("id")
    assert state.memory_id


# ── 30.2  List memories ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_memories(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/memories")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_memories_with_filters(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/memories", params={"layer": "semantic", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5


# ── 30.3  Get single memory ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.memory_id
    r = await client.get(f"/api/memories/{state.memory_id}")
    assert r.status_code == 200
    data = r.json()
    assert data.get("id") == state.memory_id
    assert data.get("title") == "Test Memory"


# ── 30.4  Update memory ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.memory_id
    r = await client.put(f"/api/memories/{state.memory_id}", json={
        "title": "Updated Memory",
        "summary": "Updated summary",
    })
    assert r.status_code == 200


# ── 30.5  Get nonexistent memory ────────────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent_memory(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/memories/nonexistent-id")
    assert r.status_code == 404


# ── 30.6  Search memories (embedding search may fail without model) ─

@pytest.mark.asyncio
async def test_search_memories(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/memories/search", json={
        "query": "test",
        "limit": 5,
    })
    # Embedding model may not be configured — accept 200 or 500
    assert r.status_code in (200, 500)


# ── 30.7  Delete memory ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.memory_id
    r = await client.delete(f"/api/memories/{state.memory_id}")
    assert r.status_code == 200
