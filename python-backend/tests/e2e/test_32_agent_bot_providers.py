"""Phase 32 — Agent Bot Providers: CRUD, connect, test, platforms."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── 32.1  List platforms ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_platforms(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent-bot-providers/platforms/list")
    assert r.status_code == 200
    data = r.json()
    assert "platforms" in data
    assert "discord" in data["platforms"]
    assert "slack" in data["platforms"]


# ── 32.2  Setup: create an agent for bot provider tests ──────────────

@pytest.mark.asyncio
async def test_setup_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/agents", json={
        "slug": f"bot-provider-test-agent-{id(object())}",
        "title": "Bot Provider Test Agent",
    })
    assert r.status_code == 201
    state.agent_id = r.json()["id"]


# ── 32.3  Create bot provider ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_bot_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.post("/api/agent-bot-providers", json={
        "agent_id": state.agent_id,
        "platform": "discord",
        "credentials": {"bot_token": "test-token-123"},
        "settings": {"prefix": "!"},
        "enabled": True,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["platform"] == "discord"
    assert data["agent_id"] == state.agent_id
    assert data["enabled"] is True
    state.provider_id = data["id"]


# ── 32.4  List bot providers ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_bot_providers(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.get("/api/agent-bot-providers")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(p["id"] == state.provider_id for p in data)


# ── 32.5  List by agent ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_by_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.get(f"/api/agent-bot-providers/by-agent/{state.agent_id}")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["agent_id"] == state.agent_id


# ── 32.6  Get bot provider ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_bot_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.provider_id
    r = await client.get(f"/api/agent-bot-providers/{state.provider_id}")
    assert r.status_code == 200
    assert r.json()["id"] == state.provider_id


# ── 32.7  Update bot provider ────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_bot_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.provider_id
    r = await client.patch(f"/api/agent-bot-providers/{state.provider_id}", json={
        "enabled": False,
        "settings": {"prefix": "/"},
    })
    assert r.status_code == 200
    assert r.json()["enabled"] is False


# ── 32.8  Test connection ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_test_connection(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.provider_id
    r = await client.post(f"/api/agent-bot-providers/{state.provider_id}/test")
    assert r.status_code == 200
    assert r.json()["valid"] is True


# ── 32.9  Connect bot (placeholder) ─────────────────────────────────

@pytest.mark.asyncio
async def test_connect_bot(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.provider_id
    r = await client.post(f"/api/agent-bot-providers/{state.provider_id}/connect")
    assert r.status_code == 200
    assert r.json()["status"] == "queued"


# ── 32.10  Get nonexistent provider → 404 ────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent-bot-providers/nonexistent-id")
    assert r.status_code == 404


# ── 32.11  Duplicate provider → 409 ──────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.post("/api/agent-bot-providers", json={
        "agent_id": state.agent_id,
        "platform": "discord",
        "credentials": {"bot_token": "another-token"},
    })
    # Should conflict on unique (agent_id, platform)
    assert r.status_code == 409


# ── 32.12  Delete bot provider ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_bot_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.provider_id
    r = await client.delete(f"/api/agent-bot-providers/{state.provider_id}")
    assert r.status_code == 200
    assert r.json()["success"] is True


# ── 32.13  Cleanup ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.agent_id:
        await client.delete(f"/api/agents/{state.agent_id}")
