"""Phase 16 — Briefs: CRUD, resolve, dismiss."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_briefs(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/briefs")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_brief(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post(
        "/api/briefs",
        json={
            "type": "insight",
            "title": "E2E Brief",
            "summary": "Test brief content",
        },
    )
    assert r.status_code in (200, 201)
    body = r.json()
    data = body.get("data") or body
    state.brief_id = data.get("id") or data.get("briefId")


@pytest.mark.asyncio
async def test_get_unresolved_briefs(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/briefs/unresolved")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_unresolved_briefs_are_enriched_and_priority_sorted(
    client: httpx.AsyncClient,
) -> None:
    suffix = uuid4().hex[:8]
    agent = await client.post(
        "/api/agents",
        json={
            "slug": f"brief-e2e-agent-{suffix}",
            "title": "Brief E2E Agent",
            "avatar": "🤖",
            "background_color": "#fff",
            "model": "gpt-4o-mini",
            "system_role": "You are a helpful assistant.",
        },
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]

    task = await client.post(
        "/api/tasks",
        json={
            "name": "Brief enrichment task",
            "instruction": "Verify brief enrichment",
            "assigneeAgentId": agent_id,
        },
    )
    assert task.status_code in (200, 201)
    task_id = task.json()["id"]

    normal = await client.post(
        "/api/briefs",
        json={
            "type": "insight",
            "priority": "normal",
            "title": "Normal brief",
            "summary": "Normal summary",
            "task_id": task_id,
            "actions": [{"key": "acknowledge", "label": "Got it", "type": "resolve"}],
        },
    )
    assert normal.status_code == 201
    normal_id = normal.json()["data"]["id"]

    urgent = await client.post(
        "/api/briefs",
        json={
            "type": "error",
            "priority": "urgent",
            "title": "Urgent brief",
            "summary": "Urgent summary",
            "task_id": task_id,
            "artifacts": {
                "documents": [{"id": "doc-test", "kind": "text", "title": "Doc"}],
            },
        },
    )
    assert urgent.status_code == 201
    urgent_id = urgent.json()["data"]["id"]

    r = await client.get("/api/briefs/unresolved")
    assert r.status_code == 200
    data = r.json()["data"]
    ids = [item["id"] for item in data]
    assert ids.index(urgent_id) < ids.index(normal_id)

    enriched = next(item for item in data if item["id"] == urgent_id)
    assert enriched["taskId"] == task_id
    assert enriched["taskStatus"] == "backlog"
    assert enriched["agents"][0]["id"] == agent_id
    assert enriched["agents"][0]["title"] == "Brief E2E Agent"
    assert enriched["artifacts"]["documents"][0]["id"] == "doc-test"

    await client.delete(f"/api/briefs/{normal_id}")
    await client.delete(f"/api/briefs/{urgent_id}")
    await client.delete(f"/api/tasks/{task_id}")
    await client.delete(f"/api/agents/{agent_id}")


@pytest.mark.asyncio
async def test_delete_brief(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.brief_id:
        pytest.skip("No brief created")
    r = await client.delete(f"/api/briefs/{state.brief_id}")
    assert r.status_code == 200
