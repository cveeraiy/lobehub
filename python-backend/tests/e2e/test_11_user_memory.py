"""Phase 12 — User Memory: memories, identities, preferences."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_memories_empty(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/user-memory")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/user-memory", json={
        "content": "E2E test memory content",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.memory_id = data.get("id") or data.get("memoryId")


@pytest.mark.asyncio
async def test_get_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.memory_id:
        pytest.skip("No memory created")
    r = await client.get(f"/api/user-memory/{state.memory_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.memory_id:
        pytest.skip("No memory")
    r = await client.put(f"/api/user-memory/{state.memory_id}", json={
        "content": "Updated memory content",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_memory_stats(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/user-memory/stats")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_identity(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/user-memory/identities", json={
        "type": "name",
        "description": "Created by e2e tests",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.identity_id = data.get("id") or data.get("identityId")


@pytest.mark.asyncio
async def test_list_identities(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/user-memory/identities")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_identity(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.identity_id:
        pytest.skip("No identity")
    r = await client.delete(f"/api/user-memory/identities/{state.identity_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_preference(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/user-memory/preferences", json={
        "type": "communication",
        "conclusion_directives": "Test preference value",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.preference_id = data.get("id") or data.get("preferenceId")


@pytest.mark.asyncio
async def test_list_preferences(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/user-memory/preferences")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_preference(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.preference_id:
        pytest.skip("No preference")
    r = await client.delete(f"/api/user-memory/preferences/{state.preference_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_memory(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.memory_id:
        pytest.skip("No memory")
    r = await client.delete(f"/api/user-memory/{state.memory_id}")
    assert r.status_code == 200
