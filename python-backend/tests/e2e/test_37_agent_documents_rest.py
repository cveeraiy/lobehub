"""E2E tests for /api/agent-documents (REST adapter) endpoints."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/agent-documents"

# Module-level state
_AGENT_ID: str | None = None
_DOC_ID: str | None = None
_LINK_ID: str | None = None
_COPY_DOC_ID: str | None = None
_COPY_LINK_ID: str | None = None


# ── Setup ───────────────────────────────────────────────────────────


async def test_setup_agent(client):
    """Create an agent for document tests."""
    global _AGENT_ID
    r = await client.post("/api/agents", json={"slug": "doc-rest-agent", "title": "DocRestAgent"})
    assert r.status_code == 201
    _AGENT_ID = r.json()["id"]


# ── Templates ───────────────────────────────────────────────────────


async def test_get_templates(client):
    """GET /api/agent-documents/templates returns template list."""
    r = await client.get(f"{PREFIX}/templates")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "name" in data[0]
    assert "filenames" in data[0]


async def test_initialize_template(client):
    """POST /api/agent-documents/initialize-template creates docs from template."""
    assert _AGENT_ID
    r = await client.post(
        f"{PREFIX}/initialize-template",
        json={"agentId": _AGENT_ID, "templateSet": "default"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] >= 1
    assert data["templateSet"] == "default"


# ── CRUD ────────────────────────────────────────────────────────────


async def test_create_document(client):
    """POST /api/agent-documents creates a document linked to agent."""
    global _DOC_ID, _LINK_ID
    assert _AGENT_ID
    r = await client.post(
        PREFIX,
        json={"agentId": _AGENT_ID, "title": "Test Doc", "content": "# Hello\n\nWorld"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "documentId" in data
    _DOC_ID = data["documentId"]
    _LINK_ID = data["id"]


async def test_list_documents(client):
    """GET /api/agent-documents/list?agentId=... returns docs."""
    assert _AGENT_ID
    r = await client.get(f"{PREFIX}/list", params={"agentId": _AGENT_ID})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(d.get("title") == "Test Doc" for d in data)


async def test_get_documents(client):
    """GET /api/agent-documents?agent_id=... returns serialized docs."""
    assert _AGENT_ID
    r = await client.get(PREFIX, params={"agent_id": _AGENT_ID})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(d.get("documentId") == _DOC_ID for d in data)


async def test_read_document(client):
    """GET /api/agent-documents/{doc_id}/read returns document content."""
    assert _DOC_ID and _AGENT_ID
    r = await client.get(f"{PREFIX}/{_DOC_ID}/read", params={"agent_id": _AGENT_ID})
    assert r.status_code == 200
    data = r.json()
    assert data["content"] == "# Hello\n\nWorld"


async def test_replace_content(client):
    """PUT /api/agent-documents/{doc_id}/content updates content."""
    assert _DOC_ID and _AGENT_ID
    r = await client.put(
        f"{PREFIX}/{_DOC_ID}/content",
        json={"agentId": _AGENT_ID, "content": "Updated content"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_rename_document(client):
    """PUT /api/agent-documents/{doc_id}/rename renames the doc."""
    assert _DOC_ID and _AGENT_ID
    r = await client.put(
        f"{PREFIX}/{_DOC_ID}/rename",
        json={"agentId": _AGENT_ID, "newTitle": "Renamed Doc"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_update_load_rule(client):
    """PUT /api/agent-documents/{doc_id}/load-rule updates load rules."""
    assert _DOC_ID and _AGENT_ID
    r = await client.put(
        f"{PREFIX}/{_DOC_ID}/load-rule",
        json={
            "agentId": _AGENT_ID,
            "rule": {"rule": "always", "policyLoadFormat": "markdown", "priority": 1},
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_copy_document(client):
    """POST /api/agent-documents/{doc_id}/copy creates a copy."""
    global _COPY_DOC_ID, _COPY_LINK_ID
    assert _DOC_ID and _AGENT_ID
    r = await client.post(
        f"{PREFIX}/{_DOC_ID}/copy",
        json={"agentId": _AGENT_ID, "newTitle": "Copied Doc"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "documentId" in data
    _COPY_DOC_ID = data["documentId"]
    _COPY_LINK_ID = data["id"]


async def test_modify_nodes(client):
    """POST /api/agent-documents/{doc_id}/modify-nodes stores operations."""
    assert _DOC_ID and _AGENT_ID
    r = await client.post(
        f"{PREFIX}/{_DOC_ID}/modify-nodes",
        json={"agentId": _AGENT_ID, "operations": [{"type": "insert", "path": [0]}]},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── Delete ──────────────────────────────────────────────────────────


async def test_delete_copy(client):
    """DELETE copied document."""
    assert _COPY_DOC_ID and _AGENT_ID
    r = await client.delete(
        f"{PREFIX}/{_COPY_DOC_ID}", params={"agent_id": _AGENT_ID}
    )
    assert r.status_code == 200
    assert r.json()["deleted"] is True


async def test_delete_document(client):
    """DELETE original document."""
    assert _DOC_ID and _AGENT_ID
    r = await client.delete(f"{PREFIX}/{_DOC_ID}", params={"agent_id": _AGENT_ID})
    assert r.status_code == 200


# ── Cleanup ─────────────────────────────────────────────────────────


async def test_cleanup(client):
    """Remove test agent and template docs."""
    if _AGENT_ID:
        # Delete template docs linked to agent
        docs = await client.get(f"{PREFIX}/list", params={"agentId": _AGENT_ID})
        if docs.status_code == 200:
            for d in docs.json():
                await client.delete(
                    f"{PREFIX}/{d['id']}", params={"agent_id": _AGENT_ID}
                )
        await client.delete(f"/api/agents/{_AGENT_ID}")
