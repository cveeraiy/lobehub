"""Phase 4 — Agents & Agent Groups."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_create_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/agents", json={
        "slug": "e2e-test-agent",
        "title": "E2E Test Agent",
        "description": "Created by e2e tests",
        "model": "gpt-4o-mini",
        "system_role": "You are a helpful assistant.",
    })
    assert r.status_code == 201
    data = r.json()
    state.agent_id = data.get("id") or data.get("agentId")
    assert state.agent_id


@pytest.mark.asyncio
async def test_list_agents(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agents")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.get(f"/api/agents/{state.agent_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.put(f"/api/agents/{state.agent_id}", json={
        "title": "Updated E2E Agent",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_agent_group(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/agent-groups", json={
        "name": "E2E Agent Group",
    })
    assert r.status_code == 201
    data = r.json()
    state.agent_group_id = data.get("id") or data.get("groupId")
    assert state.agent_group_id


@pytest.mark.asyncio
async def test_add_agent_to_group(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_group_id and state.agent_id
    r = await client.put(
        f"/api/agent-groups/{state.agent_group_id}/agents/{state.agent_id}",
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_remove_agent_from_group(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_group_id and state.agent_id
    r = await client.delete(
        f"/api/agent-groups/{state.agent_group_id}/agents/{state.agent_id}",
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_agent_group(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_group_id
    r = await client.delete(f"/api/agent-groups/{state.agent_group_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.delete(f"/api/agents/{state.agent_id}")
    assert r.status_code == 200
