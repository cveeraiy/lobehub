"""Phase 10 — Knowledge Base & Documents."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_create_knowledge_base(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/knowledge-bases", json={
        "name": "E2E Knowledge Base",
        "description": "Test KB",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.knowledge_base_id = data.get("id") or data.get("knowledgeBaseId")


@pytest.mark.asyncio
async def test_list_knowledge_bases(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/knowledge-bases")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_knowledge_base(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.knowledge_base_id:
        pytest.skip("No KB created")
    r = await client.delete(f"/api/knowledge-bases/{state.knowledge_base_id}")
    assert r.status_code == 200
