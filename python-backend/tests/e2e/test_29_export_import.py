"""Phase 29 — Export & Import: data export/import round-trip."""

from __future__ import annotations

import io
import json

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── 29.0  Setup — create session + message for export ───────────────

@pytest.mark.asyncio
async def test_setup(client: httpx.AsyncClient, state: SharedState) -> None:
    # Create session
    r = await client.post("/api/sessions", json={"type": "agent"})
    assert r.status_code == 201
    state.session_id = r.json().get("id")
    assert state.session_id

    # Create a message in that session
    r = await client.post("/api/messages", json={
        "role": "user",
        "content": "Export test message",
        "session_id": state.session_id,
    })
    assert r.status_code == 201
    state.message_id = r.json().get("id")


# ── 29.1  Export all ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_all(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/export/all")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "agents" in data
    assert "sessions" in data
    assert "topics" in data
    assert "messages" in data


# ── 29.2  Export session as markdown ─────────────────────────────────

@pytest.mark.asyncio
async def test_export_session_markdown(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id
    r = await client.get(f"/api/export/session/{state.session_id}/markdown")
    assert r.status_code == 200
    assert "text/markdown" in r.headers.get("content-type", "")
    assert "Export test message" in r.text


# ── 29.3  Export session as JSON ─────────────────────────────────────

@pytest.mark.asyncio
async def test_export_session_json(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.session_id
    r = await client.get(f"/api/export/session/{state.session_id}/json")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "session" in data
    assert "messages" in data


# ── 29.4  Export nonexistent session ─────────────────────────────────

@pytest.mark.asyncio
async def test_export_nonexistent_session(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/export/session/nonexistent-id/json")
    assert r.status_code == 404


# ── 29.5  Import data ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_data(client: httpx.AsyncClient, state: SharedState) -> None:
    payload = {
        "version": 1,
        "agents": [
            {"slug": f"import-test-{id(object())}", "title": "Imported Agent"},
        ],
        "sessions": [],
        "topics": [],
        "messages": [],
    }
    content = json.dumps(payload).encode()

    # File upload needs multipart — build a fresh client without the JSON content-type
    auth_header = {k: v for k, v in client.headers.items() if k.lower() == "authorization"}
    async with httpx.AsyncClient(base_url=str(client.base_url), headers=auth_header, timeout=30.0) as upload_client:
        r = await upload_client.post(
            "/api/import",
            files={"file": ("import.json", io.BytesIO(content), "application/json")},
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data["imported"]["agents"] >= 1
    assert data["results"]["agents"]["added"] >= 1


@pytest.mark.asyncio
async def test_import_json_body(client: httpx.AsyncClient) -> None:
    payload = {
        "data": {
            "agents": [
                {"slug": f"import-json-{id(object())}", "title": "Imported JSON Agent"},
            ],
            "messages": [],
            "sessions": [],
            "topics": [],
        },
    }

    r = await client.post("/api/import", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data["results"]["agents"]["added"] >= 1


@pytest.mark.asyncio
async def test_import_pg_counts(client: httpx.AsyncClient) -> None:
    payload = {
        "data": {
            "messages": [{"id": "message-1"}, {"id": "message-2"}],
            "sessions": [{"id": "session-1"}],
        },
        "schemaHash": "test",
    }

    r = await client.post("/api/import/pg", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data["results"]["messages"]["added"] == 2
    assert data["results"]["sessions"]["added"] == 1


# ── 29.6  Import invalid file ───────────────────────────────────────

@pytest.mark.asyncio
async def test_import_invalid_file(client: httpx.AsyncClient) -> None:
    auth_header = {k: v for k, v in client.headers.items() if k.lower() == "authorization"}
    async with httpx.AsyncClient(base_url=str(client.base_url), headers=auth_header, timeout=30.0) as upload_client:
        r = await upload_client.post(
            "/api/import",
            files={"file": ("data.txt", io.BytesIO(b"not json"), "text/plain")},
        )
    assert r.status_code == 400


# ── 29.7  Cleanup ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.message_id:
        await client.delete(f"/api/messages/{state.message_id}")
    if state.session_id:
        await client.delete(f"/api/sessions/{state.session_id}")
