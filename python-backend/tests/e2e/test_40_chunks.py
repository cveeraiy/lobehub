"""E2E tests for /api/chunks endpoints — chunk CRUD, count, tasks."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/chunks"

# Module-level state
_KB_ID: str | None = None
_DOC_ID: str | None = None
_CHUNK_ID: str | None = None


# ── Setup ───────────────────────────────────────────────────────────


async def test_setup_kb(client):
    """Create a knowledge base."""
    global _KB_ID
    r = await client.post(
        "/api/knowledge-bases",
        json={"name": "chunk-test-kb", "description": "KB for chunk tests"},
    )
    assert r.status_code in (200, 201)
    _KB_ID = r.json()["id"]


async def test_setup_document(client):
    """Create a document to attach chunks to."""
    global _DOC_ID
    r = await client.post(
        "/api/documents",
        json={
            "title": "Chunk Source Doc",
            "content": "Some content for chunking. This chunk mentions alpha parity search.",
            "knowledge_base_id": _KB_ID,
        },
    )
    assert r.status_code == 201
    _DOC_ID = r.json()["id"]
    parse = await client.post(f"/api/documents/{_DOC_ID}/parse")
    assert parse.status_code == 200


# ── Count ───────────────────────────────────────────────────────────


async def test_count_chunks(client):
    """GET /api/chunks/count"""
    r = await client.get(f"{PREFIX}/count")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert isinstance(data["count"], int)


# ── Tasks ───────────────────────────────────────────────────────────


async def test_create_parse_task(client):
    """POST /api/chunks/create-parse-task requires a file ID — test with doc ID (may fail gracefully)."""
    r = await client.post(
        f"{PREFIX}/create-parse-task",
        json={"id": "nonexistent-file-id"},
    )
    # The endpoint creates a task regardless of whether the file exists
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "id" in data


async def test_create_embedding_task(client):
    """POST /api/chunks/create-embedding-task"""
    r = await client.post(
        f"{PREFIX}/create-embedding-task",
        json={"id": "nonexistent-file-id"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True


# ── Chunk CRUD/search ──────────────────────────────────────────────


async def test_get_chunks_by_knowledge_base_empty(client):
    """GET /api/chunks/by-knowledge-base/{kb_id} returns chunks for parsed docs."""
    assert _KB_ID
    r = await client.get(f"{PREFIX}/by-knowledge-base/{_KB_ID}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_chunks_by_document_id(client):
    """GET /api/chunks/by-file/{id} accepts a document id fallback."""
    assert _DOC_ID
    r = await client.get(f"{PREFIX}/by-file/{_DOC_ID}")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) >= 1


async def test_semantic_search_chat_lexical_fallback(client):
    """POST /api/chunks/semantic-search-chat works without an embedding provider."""
    assert _DOC_ID
    r = await client.post(
        f"{PREFIX}/semantic-search-chat",
        json={"query": "alpha parity", "file_ids": [_DOC_ID], "top_k": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["chunks"]) >= 1
    assert len(data["fileResults"]) >= 1


async def test_get_chunk_nonexistent(client):
    """GET /api/chunks/{id} for nonexistent chunk returns 404."""
    r = await client.get(f"{PREFIX}/nonexistent-chunk-id")
    assert r.status_code == 404


async def test_batch_delete_empty(client):
    """POST /api/chunks/batch-delete with empty list is a no-op."""
    r = await client.post(f"{PREFIX}/batch-delete", json={"ids": []})
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_get_file_contents(client):
    """POST /api/chunks/get-file-contents for nonexistent files."""
    r = await client.post(
        f"{PREFIX}/get-file-contents",
        json={"file_ids": ["fake-file-1"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1


# ── Cleanup ─────────────────────────────────────────────────────────


async def test_cleanup(client):
    """Remove test documents and KB."""
    if _DOC_ID:
        await client.delete(f"/api/documents/{_DOC_ID}")
    if _KB_ID:
        await client.delete(f"/api/knowledge-bases/{_KB_ID}")
