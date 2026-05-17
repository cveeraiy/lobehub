"""E2E tests for /api/documents endpoints — document CRUD, batch ops, history, stats."""

import json
import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/documents"

# Module-level state
_DOC_ID: str | None = None
_DOC_ID_2: str | None = None
_HISTORY_ID: str | None = None
_KB_ID: str | None = None
_SLUG: str = f"test-doc-e2e-{uuid.uuid4().hex[:8]}"


# ── Setup ───────────────────────────────────────────────────────────


async def test_setup_kb(client):
    """Create a knowledge base for document tests."""
    global _KB_ID
    r = await client.post(
        "/api/knowledge-bases",
        json={"name": "doc-test-kb", "description": "For document tests"},
    )
    assert r.status_code in (200, 201)
    _KB_ID = r.json()["id"]


# ── Create ──────────────────────────────────────────────────────────


async def test_create_document(client):
    """POST /api/documents creates a document."""
    global _DOC_ID
    r = await client.post(
        PREFIX,
        json={
            "title": "Test Document",
            "content": "# Test\n\nParagraph content here.",
            "file_type": "markdown",
            "slug": _SLUG,
            "knowledge_base_id": _KB_ID,
        },
    )
    assert r.status_code == 201
    _DOC_ID = r.json()["id"]


async def test_create_batch(client):
    """POST /api/documents/batch creates multiple documents."""
    global _DOC_ID_2
    r = await client.post(
        f"{PREFIX}/batch",
        json={
            "documents": [
                {"title": "Batch Doc 1", "content": "Content A", "file_type": "document"},
                {"title": "Batch Doc 2", "content": "Content B", "file_type": "document"},
            ]
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert len(data["ids"]) == 2
    _DOC_ID_2 = data["ids"][0]


# ── Read ────────────────────────────────────────────────────────────


async def test_list_documents(client):
    """GET /api/documents returns all docs."""
    r = await client.get(PREFIX)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(d["id"] == _DOC_ID for d in data)


async def test_list_documents_by_kb(client):
    """GET /api/documents?knowledge_base_id=... filters by KB."""
    assert _KB_ID
    r = await client.get(PREFIX, params={"knowledge_base_id": _KB_ID})
    assert r.status_code == 200
    data = r.json()
    assert all(d.get("knowledge_base_id") == _KB_ID for d in data)


async def test_get_document(client):
    """GET /api/documents/{id} returns a single document."""
    assert _DOC_ID
    r = await client.get(f"{PREFIX}/{_DOC_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _DOC_ID
    assert data["title"] == "Test Document"


async def test_get_nonexistent_document(client):
    """GET /api/documents/{id} for missing doc returns 404."""
    r = await client.get(f"{PREFIX}/nonexistent-id-xxx")
    assert r.status_code == 404


async def test_get_by_slug(client):
    """GET /api/documents/by-slug/{slug}"""
    r = await client.get(f"{PREFIX}/by-slug/{_SLUG}")
    assert r.status_code == 200
    assert r.json()["id"] == _DOC_ID


async def test_query_documents(client):
    """GET /api/documents/query with pagination."""
    r = await client.get(f"{PREFIX}/query", params={"current": 1, "page_size": 10})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


async def test_folder_breadcrumb(client):
    """GET /api/documents/folder-breadcrumb/{slug}"""
    r = await client.get(f"{PREFIX}/folder-breadcrumb/{_SLUG}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


# ── Update ──────────────────────────────────────────────────────────


async def test_update_document(client):
    """PUT /api/documents/{id} updates fields."""
    assert _DOC_ID
    r = await client.put(
        f"{PREFIX}/{_DOC_ID}",
        json={"title": "Updated Title", "content": "Updated content."},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Verify
    r2 = await client.get(f"{PREFIX}/{_DOC_ID}")
    assert r2.json()["title"] == "Updated Title"


# ── History ─────────────────────────────────────────────────────────


async def test_save_history(client):
    """POST /api/documents/history creates a history snapshot."""
    global _HISTORY_ID
    assert _DOC_ID
    r = await client.post(
        f"{PREFIX}/history",
        json={
            "document_id": _DOC_ID,
            "editor_data": json.dumps({"blocks": [{"type": "paragraph", "text": "v1"}]}),
            "save_source": "test",
        },
    )
    assert r.status_code == 201
    _HISTORY_ID = r.json()["id"]


async def test_list_history(client):
    """GET /api/documents/history/{doc_id}"""
    assert _DOC_ID
    r = await client.get(f"{PREFIX}/history/{_DOC_ID}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_history_item(client):
    """GET /api/documents/history-item/{id}"""
    if not _HISTORY_ID:
        pytest.skip("No history item")
    r = await client.get(f"{PREFIX}/history-item/{_HISTORY_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _HISTORY_ID
    assert data["editor_data"] is not None


async def test_compare_history(client):
    """GET /api/documents/history-compare"""
    if not _HISTORY_ID:
        pytest.skip("No history item")
    r = await client.get(
        f"{PREFIX}/history-compare",
        params={"left_id": _HISTORY_ID, "right_id": _HISTORY_ID},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["left"] is not None
    assert data["right"] is not None


# ── Stats ───────────────────────────────────────────────────────────


async def test_document_stats(client):
    """GET /api/documents/{id}/stats"""
    assert _DOC_ID
    r = await client.get(f"{PREFIX}/{_DOC_ID}/stats")
    assert r.status_code == 200
    data = r.json()
    assert "chunk_count" in data
    assert "total_char_count" in data


# ── Parse (placeholder) ────────────────────────────────────────────


async def test_parse_document(client):
    """POST /api/documents/{id}/parse returns content."""
    assert _DOC_ID
    r = await client.post(f"{PREFIX}/{_DOC_ID}/parse")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _DOC_ID


# ── Delete ──────────────────────────────────────────────────────────


async def test_batch_delete(client):
    """POST /api/documents/batch-delete removes multiple docs."""
    assert _DOC_ID_2
    r = await client.post(f"{PREFIX}/batch-delete", json={"ids": [_DOC_ID_2]})
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_delete_document(client):
    """DELETE /api/documents/{id}"""
    assert _DOC_ID
    r = await client.delete(f"{PREFIX}/{_DOC_ID}")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── Cleanup ─────────────────────────────────────────────────────────


async def test_cleanup(client):
    """Remove KB."""
    if _KB_ID:
        await client.delete(f"/api/knowledge-bases/{_KB_ID}")
