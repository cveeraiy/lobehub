"""Phase 25 — Home: sidebar agents, search, agent group assignment."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── 25.0  Setup — create an agent for home tests ────────────────────

@pytest.mark.asyncio
async def test_setup_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/agents", json={
        "slug": f"home-test-{id(state)}",
        "title": "Home Test Agent",
        "description": "Agent for home router tests",
        "system_role": "test",
    })
    assert r.status_code == 201
    state.agent_id = r.json().get("id")
    assert state.agent_id


# ── 25.1  Sidebar agents ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sidebar_agents(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/home/sidebar-agents")
    assert r.status_code == 200
    data = r.json()
    assert "pinned" in data
    assert "groups" in data
    assert "ungrouped" in data
    assert isinstance(data["pinned"], list)
    assert isinstance(data["groups"], list)
    assert isinstance(data["ungrouped"], list)


# ── 25.2  Search agents ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_agents(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/home/search-agents", params={"keyword": "Home Test"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_search_agents_no_results(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/home/search-agents", params={"keyword": "zzz_nonexistent_zzz"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 0


# ── 25.3  Update agent group ────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_agent_group(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    # Assign to no group (null)
    r = await client.put("/api/home/agent-group", json={
        "agent_id": state.agent_id,
        "session_group_id": None,
    })
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True


# ── 25.4  Cleanup ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.agent_id:
        r = await client.delete(f"/api/agents/{state.agent_id}")
        assert r.status_code == 200
