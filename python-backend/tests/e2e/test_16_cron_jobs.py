"""Phase 17 — Agent Cron Jobs: CRUD, stats, batch."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_setup_agent_for_cron(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/agents", json={
        "slug": f"cron-agent-{id(state)}",
        "title": "Cron Agent",
        "model": "gpt-4o-mini",
        "system_role": "test",
    })
    assert r.status_code == 201
    state.agent_id = r.json().get("id") or r.json().get("agentId")


@pytest.mark.asyncio
async def test_create_cron_job(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.post("/api/agent-cron-jobs", json={
        "agent_id": state.agent_id,
        "name": "E2E Cron",
        "schedule": "0 9 * * *",
        "prompt": "Daily check",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    cron_data = data.get("data", data)
    state.cron_job_id = cron_data.get("id") or cron_data.get("cronJobId")


@pytest.mark.asyncio
async def test_list_cron_jobs(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent-cron-jobs")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_cron_stats(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent-cron-jobs/stats")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_cron_job(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.cron_job_id:
        pytest.skip("No cron job")
    r = await client.put(f"/api/agent-cron-jobs/{state.cron_job_id}", json={
        "name": "Updated Cron",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_cron_job(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.cron_job_id:
        pytest.skip("No cron job")
    r = await client.delete(f"/api/agent-cron-jobs/{state.cron_job_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_agent(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.agent_id:
        await client.delete(f"/api/agents/{state.agent_id}")
