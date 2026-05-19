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
    assert isinstance(data, list)
    assert [platform["id"] for platform in data] == [
        "discord",
        "telegram",
        "line",
        "slack",
        "feishu",
        "lark",
        "qq",
        "wechat",
        "teams",
    ]
    assert data[0]["connectionMode"] == "websocket"
    assert any(field["key"] == "credentials" for field in data[0]["schema"])
    assert data[1]["connectionMode"] == "webhook"
    assert data[2]["showWebhookUrl"] is True
    assert data[3]["connectionMode"] == "websocket"
    assert data[4]["supportsMarkdown"] is False
    assert data[5]["supportsMarkdown"] is False
    assert data[6]["supportsMarkdown"] is False
    assert data[6]["supportsMessageEdit"] is False
    assert data[7]["connectionMode"] == "polling"
    assert data[7]["supportsMessageEdit"] is False
    assert data[8]["connectionMode"] == "webhook"


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
        "application_id": "discord-app-test-123",
        "platform": "discord",
        "credentials": {"botToken": "test-token-123", "publicKey": "test-public-key"},
        "settings": {"prefix": "!"},
        "enabled": True,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["platform"] == "discord"
    assert data["application_id"] == "discord-app-test-123"
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
    assert r.status_code == 400
    assert r.json()["detail"]["valid"] is False


# ── 32.9  Connect persistent bot (unsupported until gateway port) ───

@pytest.mark.asyncio
async def test_connect_persistent_bot_is_explicitly_unsupported(
    client: httpx.AsyncClient,
    state: SharedState,
) -> None:
    assert state.provider_id
    r = await client.post(f"/api/agent-bot-providers/{state.provider_id}/connect")
    assert r.status_code == 501


# ── 32.10  Connect webhook bot and read runtime status ───────────────

@pytest.mark.asyncio
async def test_connect_webhook_bot_updates_runtime_status(
    client: httpx.AsyncClient,
    state: SharedState,
) -> None:
    assert state.agent_id
    create = await client.post("/api/agent-bot-providers", json={
        "agent_id": state.agent_id,
        "application_id": "telegram-runtime-test-123",
        "platform": "telegram",
        "credentials": {"botToken": "test-token-123"},
    })
    assert create.status_code == 201
    provider = create.json()

    try:
        connect = await client.post(f"/api/agent-bot-providers/{provider['id']}/connect")
        assert connect.status_code == 200
        assert connect.json() == {"status": "connected"}

        status_response = await client.get(
            "/api/agent-bot-providers/runtime-status/get",
            params={"application_id": "telegram-runtime-test-123", "platform": "telegram"},
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["application_id"] == "telegram-runtime-test-123"
        assert status_data["platform"] == "telegram"
        assert status_data["status"] == "connected"
    finally:
        await client.delete(f"/api/agent-bot-providers/{provider['id']}")


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
        "application_id": "discord-app-test-123",
        "platform": "discord",
        "credentials": {"botToken": "another-token", "publicKey": "another-key"},
    })
    # Should conflict on unique (platform, application_id)
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
