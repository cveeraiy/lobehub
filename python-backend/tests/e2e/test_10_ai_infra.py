"""Phase 11 — AI Infrastructure: Providers & Models."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_providers(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/ai-infra/providers")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/ai-infra/providers", json={
        "id": "e2e-test-provider",
        "name": "E2E Test Provider",
        "type": "openai",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.provider_id = data.get("id") or "e2e-test-provider"


@pytest.mark.asyncio
async def test_get_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.provider_id:
        pytest.skip("No provider created")
    r = await client.get(f"/api/ai-infra/providers/{state.provider_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.provider_id:
        pytest.skip("No provider")
    r = await client.put(f"/api/ai-infra/providers/{state.provider_id}", json={
        "name": "Updated Provider",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_toggle_provider_enabled(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.provider_id:
        pytest.skip("No provider")
    r = await client.put(f"/api/ai-infra/providers/{state.provider_id}/enabled", json={
        "enabled": True,
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_provider_models(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.provider_id:
        pytest.skip("No provider")
    r = await client.get(f"/api/ai-infra/providers/{state.provider_id}/models")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_model(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.provider_id:
        pytest.skip("No provider")
    r = await client.post("/api/ai-infra/models", json={
        "id": "e2e-test-model",
        "provider_id": state.provider_id,
        "display_name": "E2E Model",
        "type": "chat",
    })
    assert r.status_code in (200, 201)
    state.model_id = "e2e-test-model"


@pytest.mark.asyncio
async def test_get_runtime(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/ai-infra/runtime")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_model(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.model_id or not state.provider_id:
        pytest.skip("No model")
    r = await client.delete(f"/api/ai-infra/models/{state.model_id}/provider/{state.provider_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_provider(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.provider_id:
        pytest.skip("No provider")
    r = await client.delete(f"/api/ai-infra/providers/{state.provider_id}")
    assert r.status_code == 200
