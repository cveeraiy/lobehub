"""Phase 9 — Plugins & Skills: CRUD."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── Plugins ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_plugins(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/plugins")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_install_plugin(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/plugins/install", json={
        "identifier": "e2e-test-plugin",
        "type": "customPlugin",
        "manifest": {"identifier": "e2e-test-plugin", "api": []},
    })
    assert r.status_code in (200, 201)
    state.plugin_identifier = "e2e-test-plugin"


@pytest.mark.asyncio
async def test_update_plugin(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.plugin_identifier:
        pytest.skip("No plugin installed")
    r = await client.put(f"/api/plugins/{state.plugin_identifier}", json={
        "settings": {"key": "value"},
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_uninstall_plugin(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.plugin_identifier:
        pytest.skip("No plugin to uninstall")
    r = await client.delete(f"/api/plugins/{state.plugin_identifier}")
    assert r.status_code == 200


# ── Skills ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_skills(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/skills")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_skill(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/skills", json={
        "identifier": "e2e-test-skill",
        "name": "E2E Test Skill",
        "description": "Created by e2e tests",
        "type": "builtin",
        "manifest": {"tools": []},
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.skill_id = data.get("id") or data.get("skillId")


@pytest.mark.asyncio
async def test_get_skill(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.skill_id:
        pytest.skip("No skill created")
    r = await client.get(f"/api/skills/{state.skill_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_skills(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/skills/search/query?q=test")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_skill(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.skill_id:
        pytest.skip("No skill to delete")
    r = await client.delete(f"/api/skills/{state.skill_id}")
    assert r.status_code == 200
