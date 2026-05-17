"""Phase 26 — Notebook: document CRUD linked to topics."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── 26.0  Setup — create a session + topic for notebook tests ───────

@pytest.mark.asyncio
async def test_setup(client: httpx.AsyncClient, state: SharedState) -> None:
    # Create session
    r = await client.post("/api/sessions", json={"type": "agent"})
    assert r.status_code == 201
    state.session_id = r.json().get("id")
    assert state.session_id

    # Create topic
    r = await client.post("/api/topics", json={
        "session_id": state.session_id,
        "title": "Notebook Test Topic",
    })
    assert r.status_code == 201
    state.topic_id = r.json().get("id")
    assert state.topic_id


# ── 26.1  Create document ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_document(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.topic_id
    r = await client.post("/api/notebook/documents", json={
        "title": "Test Notebook Doc",
        "content": "# Hello\n\nThis is test content.",
        "topic_id": state.topic_id,
        "type": "markdown",
    })
    assert r.status_code == 201
    data = r.json()
    state.document_id = data.get("id")
    assert state.document_id


# ── 26.2  List documents ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_documents(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/notebook/documents")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_documents_by_topic(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.topic_id
    r = await client.get("/api/notebook/documents", params={"topic_id": state.topic_id})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


# ── 26.3  Get single document ───────────────────────────────────────

@pytest.mark.asyncio
async def test_get_document(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.document_id
    r = await client.get(f"/api/notebook/documents/{state.document_id}")
    assert r.status_code == 200
    data = r.json()
    assert data.get("id") == state.document_id
    assert "content" in data  # get includes content


# ── 26.4  Update document ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_document(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.document_id
    r = await client.put(f"/api/notebook/documents/{state.document_id}", json={
        "title": "Updated Notebook Doc",
        "content": "# Updated\n\nNew content.",
    })
    assert r.status_code == 200


# ── 26.5  Delete document ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_document(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.document_id
    r = await client.delete(f"/api/notebook/documents/{state.document_id}")
    assert r.status_code == 200


# ── 26.6  Cleanup ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.topic_id:
        await client.delete(f"/api/topics/{state.topic_id}")
    if state.session_id:
        await client.delete(f"/api/sessions/{state.session_id}")
