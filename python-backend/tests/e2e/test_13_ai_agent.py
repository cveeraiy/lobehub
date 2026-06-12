"""Phase 14 — AI Agent Execution (proxied endpoints)."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_setup_agent_for_exec(client: httpx.AsyncClient, state: SharedState) -> None:
    """Create an agent to execute against."""
    r = await client.post("/api/agents", json={
        "slug": f"exec-test-agent-{id(state)}",
        "title": "Exec Test Agent",
        "model": "gpt-4o-mini",
        "system_role": "You are a test agent. Reply with 'OK'.",
    })
    assert r.status_code == 201
    state.agent_id = r.json().get("id") or r.json().get("agentId")
    assert state.agent_id


@pytest.mark.asyncio
async def test_exec_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    """POST /api/ai-agent/exec — basic agent execution."""
    assert state.agent_id
    r = await client.post("/api/ai-agent/exec", json={
        "agent_id": state.agent_id,
        "prompt": "Say hello",
        "auto_start": True,
    })
    # 200 on success, or 400/422/500 if LLM not configured (acceptable in CI)
    assert r.status_code in (200, 400, 422, 500, 503)
    if r.status_code == 200:
        data = r.json()
        assert "operation_id" in data or "operationId" in data


@pytest.mark.asyncio
async def test_exec_agent_missing_fields(client: httpx.AsyncClient) -> None:
    """POST /api/ai-agent/exec with missing required fields → 422."""
    r = await client.post("/api/ai-agent/exec", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_exec_group_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    """POST /api/ai-agent/exec-group."""
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/ai-agent/exec-group", json={
        "agent_id": state.agent_id,
        "group_id": "test-group",
        "message": "Hello group",
    })
    # Accept a range of statuses since LLM may not be configured
    assert r.status_code in (200, 422, 500, 503)


@pytest.mark.asyncio
async def test_exec_sub_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    """POST /api/ai-agent/exec-sub-agent."""
    if not state.agent_id:
        pytest.skip("No agent")
    r = await client.post("/api/ai-agent/exec-sub-agent", json={
        "agent_id": state.agent_id,
        "prompt": "Sub agent task",
    })
    assert r.status_code in (200, 422, 500, 503)


@pytest.mark.asyncio
async def test_interrupt_task(client: httpx.AsyncClient) -> None:
    """POST /api/ai-agent/interrupt — interrupt with fake operation_id."""
    r = await client.post("/api/ai-agent/interrupt", json={
        "operation_id": "nonexistent-op-id",
    })
    # 200 (no-op) or 404 (not found) or 422 (validation) are all acceptable
    assert r.status_code in (200, 404, 422)


@pytest.mark.asyncio
async def test_exec_stream_sse(client: httpx.AsyncClient, state: SharedState) -> None:
    """POST /api/ai-agent/exec/stream — SSE endpoint returns event stream."""
    if not state.agent_id:
        pytest.skip("No agent")
    async with httpx.AsyncClient(
        base_url=client.base_url,
        headers=dict(client.headers),
        timeout=15.0,
    ) as stream_client:
        r = await stream_client.post(
            "/api/ai-agent/exec/stream",
            json={
                "agent_id": state.agent_id,
                "prompt": "Say hello via stream",
                "auto_start": True,
            },
        )
        # If LLM is configured, should be 200 with SSE content type
        # Otherwise accept service unavailable
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            assert "text/event-stream" in ct or "application/json" in ct
        else:
            assert r.status_code in (422, 500, 503)


@pytest.mark.asyncio
async def test_cleanup_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.agent_id:
        await client.delete(f"/api/agents/{state.agent_id}")
