"""Phase 3 — Sessions & Session Groups: CRUD + group membership."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── 3.1  Create session ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/sessions", json={
        "type": "agent",
        "meta": {"title": "E2E Test Session"},
    })
    assert r.status_code == 201
    data = r.json()
    state.session_id = data.get("id") or data.get("sessionId")
    assert state.session_id


# ── 3.2  List sessions ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_sessions(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.get("/api/sessions")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


# ── 3.3  Get single session ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_session(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id, "Requires session from test_create_session"
    r = await client.get(f"/api/sessions/{state.session_id}")
    assert r.status_code == 200


# ── 3.4  Update session ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_session(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id
    r = await client.put(
        f"/api/sessions/{state.session_id}",
        json={"meta": {"title": "Updated E2E Session"}},
    )
    assert r.status_code == 200


# ── 3.5  Create session group ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session_group(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/session-groups", json={
        "name": "E2E Test Group",
    })
    assert r.status_code == 201
    data = r.json()
    state.session_group_id = data.get("id") or data.get("groupId")
    assert state.session_group_id


# ── 3.6  Add session to group ────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_session_to_group(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_group_id and state.session_id
    r = await client.put(
        f"/api/session-groups/{state.session_group_id}/sessions/{state.session_id}",
    )
    assert r.status_code == 200


# ── 3.7  Remove session from group ───────────────────────────────────

@pytest.mark.asyncio
async def test_remove_session_from_group(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_group_id and state.session_id
    r = await client.delete(
        f"/api/session-groups/{state.session_group_id}/sessions/{state.session_id}",
    )
    assert r.status_code == 200


# ── 3.8  Delete session group ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_session_group(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_group_id
    r = await client.delete(f"/api/session-groups/{state.session_group_id}")
    assert r.status_code == 200


# ── 3.9  Delete session ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_session(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id
    r = await client.delete(f"/api/sessions/{state.session_id}")
    assert r.status_code == 200
