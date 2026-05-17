"""Phase 33 — Chat Groups: multi-agent group CRUD, agents, duplicate."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e

_GROUP_ID: str | None = None
_SUPERVISOR_ID: str | None = None
_MEMBER_IDS: list[str] = []


# ── 33.1  Create simple chat group ───────────────────────────────────

@pytest.mark.asyncio
async def test_create_chat_group(client: httpx.AsyncClient) -> None:
    global _GROUP_ID, _SUPERVISOR_ID
    r = await client.post("/api/chat-groups", json={
        "name": "E2E Test Group",
        "description": "Group for testing",
    })
    assert r.status_code == 201
    data = r.json()
    assert "group" in data
    assert data["group"]["name"] == "E2E Test Group"
    assert "supervisor_agent_id" in data
    _GROUP_ID = data["group"]["id"]
    _SUPERVISOR_ID = data["supervisor_agent_id"]


# ── 33.2  List chat groups ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_chat_groups(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/chat-groups")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(g["id"] == _GROUP_ID for g in data)


# ── 33.3  Get chat group ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_chat_group(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    r = await client.get(f"/api/chat-groups/{_GROUP_ID}")
    assert r.status_code == 200
    assert r.json()["id"] == _GROUP_ID


# ── 33.4  Get chat group detail (with agents) ───────────────────────

@pytest.mark.asyncio
async def test_get_chat_group_detail(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    r = await client.get(f"/api/chat-groups/{_GROUP_ID}/detail")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _GROUP_ID
    assert "agents" in data
    # Should have the supervisor
    assert len(data["agents"]) >= 1


# ── 33.5  Update chat group ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_chat_group(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    r = await client.put(f"/api/chat-groups/{_GROUP_ID}", json={
        "name": "Updated Group Name",
        "description": "Updated description",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 33.6  Get group agents ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_group_agents(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    r = await client.get(f"/api/chat-groups/{_GROUP_ID}/agents")
    assert r.status_code == 200
    agents = r.json()
    assert isinstance(agents, list)
    assert len(agents) >= 1  # at least supervisor


# ── 33.7  Create group with members ─────────────────────────────────

@pytest.mark.asyncio
async def test_create_group_with_members(client: httpx.AsyncClient) -> None:
    global _MEMBER_IDS
    r = await client.post("/api/chat-groups/with-members", json={
        "group_config": {
            "name": "E2E Multi-Agent Group",
            "description": "Group with members",
        },
        "members": [
            {"title": "Analyst", "system_role": "You are an analyst."},
            {"title": "Writer", "system_role": "You are a writer."},
        ],
        "supervisor_config": {
            "title": "Coordinator",
        },
    })
    assert r.status_code == 201
    data = r.json()
    assert "group_id" in data
    assert "supervisor_agent_id" in data
    assert len(data["agent_ids"]) == 2
    _MEMBER_IDS = data["agent_ids"]
    # Cleanup: store for deletion
    _with_members_group_id = data["group_id"]


# ── 33.8  Batch create agents in group ──────────────────────────────

@pytest.mark.asyncio
async def test_batch_create_agents(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    r = await client.post(f"/api/chat-groups/{_GROUP_ID}/agents/batch-create", json={
        "group_id": _GROUP_ID,
        "agents": [
            {"title": "Batch Agent 1", "system_role": "You are a helper."},
            {"title": "Batch Agent 2", "system_role": "You are an assistant."},
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["agent_ids"]) == 2


# ── 33.9  Check removal (virtual agents) ────────────────────────────

@pytest.mark.asyncio
async def test_check_removal(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    agents = (await client.get(f"/api/chat-groups/{_GROUP_ID}/agents")).json()
    agent_ids = [a["id"] for a in agents]
    r = await client.post(f"/api/chat-groups/{_GROUP_ID}/check-removal", json={
        "agent_ids": agent_ids,
    })
    assert r.status_code == 200
    data = r.json()
    assert "virtual_agent_ids" in data
    assert "non_virtual_agent_ids" in data


# ── 33.10  Remove agents from group ─────────────────────────────────

@pytest.mark.asyncio
async def test_remove_agents(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    # Get batch-created agents (last two)
    agents = (await client.get(f"/api/chat-groups/{_GROUP_ID}/agents")).json()
    batch_agents = [a for a in agents if a["role"] == "participant"]
    if batch_agents:
        agent_ids = [a["id"] for a in batch_agents[:1]]  # remove one
        r = await client.post(f"/api/chat-groups/{_GROUP_ID}/agents/remove", json={
            "agent_ids": agent_ids,
            "delete_virtual_agents": True,
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ── 33.11  Duplicate group ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_group(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    r = await client.post(f"/api/chat-groups/{_GROUP_ID}/duplicate", json={
        "new_title": "Duplicated Group",
    })
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    # Cleanup the duplicate
    await client.delete(f"/api/chat-groups/{data['id']}")


# ── 33.12  Get nonexistent group → 404 ──────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent_group(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/chat-groups/nonexistent-id")
    assert r.status_code == 404


# ── 33.13  Delete chat group ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_chat_group(client: httpx.AsyncClient) -> None:
    assert _GROUP_ID
    r = await client.delete(f"/api/chat-groups/{_GROUP_ID}")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Verify supervisor was cleaned up
    r2 = await client.get(f"/api/chat-groups/{_GROUP_ID}")
    assert r2.status_code == 404


# ── 33.14  Cleanup with-members group ───────────────────────────────

@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient) -> None:
    # Clean up groups created by with-members test
    groups = (await client.get("/api/chat-groups")).json()
    for g in groups:
        if g.get("name") in ("E2E Multi-Agent Group",):
            await client.delete(f"/api/chat-groups/{g['id']}")
