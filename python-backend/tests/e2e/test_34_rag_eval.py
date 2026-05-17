"""Phase 34 — RAG Evaluation: datasets, records, evaluations, execution."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e

_KB_ID: str | None = None
_DATASET_ID: str | None = None
_RECORD_ID: str | None = None
_EVALUATION_ID: str | None = None


# ── 34.1  Setup: create a knowledge base for RAG eval ────────────────

@pytest.mark.asyncio
async def test_setup_kb(client: httpx.AsyncClient) -> None:
    global _KB_ID
    r = await client.post("/api/knowledge-bases", json={
        "name": f"rag-eval-test-kb-{id(object())}",
        "description": "KB for RAG eval testing",
    })
    assert r.status_code == 201
    _KB_ID = r.json()["id"]


# ── 34.2  Create dataset ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_dataset(client: httpx.AsyncClient) -> None:
    global _DATASET_ID
    assert _KB_ID
    r = await client.post("/api/rag-eval/datasets", json={
        "name": "E2E Eval Dataset",
        "description": "Test dataset",
        "knowledge_base_id": _KB_ID,
    })
    assert r.status_code == 200
    _DATASET_ID = r.json()
    assert _DATASET_ID


# ── 34.3  List datasets ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_datasets(client: httpx.AsyncClient) -> None:
    assert _KB_ID
    r = await client.get(f"/api/rag-eval/datasets?knowledgeBaseId={_KB_ID}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(d["id"] == _DATASET_ID for d in data)


# ── 34.4  Update dataset ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_dataset(client: httpx.AsyncClient) -> None:
    assert _DATASET_ID
    r = await client.patch(f"/api/rag-eval/datasets/{_DATASET_ID}", json={
        "name": "Updated Eval Dataset",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 34.5  Create dataset record ─────────────────────────────────────

@pytest.mark.asyncio
async def test_create_record(client: httpx.AsyncClient) -> None:
    global _RECORD_ID
    assert _DATASET_ID
    r = await client.post("/api/rag-eval/dataset-records", json={
        "dataset_id": _DATASET_ID,
        "question": "What is RAG?",
        "ideal": "Retrieval-Augmented Generation",
    })
    assert r.status_code == 200
    _RECORD_ID = r.json()
    assert _RECORD_ID


# ── 34.6  List dataset records ───────────────────────────────────────

@pytest.mark.asyncio
async def test_list_records(client: httpx.AsyncClient) -> None:
    assert _DATASET_ID
    r = await client.get(f"/api/rag-eval/dataset-records?dataset_id={_DATASET_ID}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


# ── 34.7  Update dataset record ─────────────────────────────────────

@pytest.mark.asyncio
async def test_update_record(client: httpx.AsyncClient) -> None:
    assert _RECORD_ID
    r = await client.patch(f"/api/rag-eval/dataset-records/{_RECORD_ID}", json={
        "question": "What is RAG (updated)?",
        "ideal": "Retrieval-Augmented Generation (updated)",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 34.8  Import dataset records (batch) ─────────────────────────────

@pytest.mark.asyncio
async def test_import_records(client: httpx.AsyncClient) -> None:
    assert _DATASET_ID
    r = await client.post("/api/rag-eval/dataset-records/import", json={
        "dataset_id": _DATASET_ID,
        "records": [
            {"question": "Q1", "ideal": "A1"},
            {"question": "Q2", "ideal": "A2"},
            {"question": "Q3"},
        ],
    })
    assert r.status_code == 200
    assert r.json()["imported"] == 3


# ── 34.9  Create evaluation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_evaluation(client: httpx.AsyncClient) -> None:
    global _EVALUATION_ID
    assert _KB_ID and _DATASET_ID
    r = await client.post("/api/rag-eval/evaluations", json={
        "name": "E2E Evaluation",
        "description": "Test eval",
        "knowledge_base_id": _KB_ID,
        "dataset_id": _DATASET_ID,
    })
    assert r.status_code == 200
    _EVALUATION_ID = r.json()
    assert _EVALUATION_ID


# ── 34.10  List evaluations ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_evaluations(client: httpx.AsyncClient) -> None:
    assert _KB_ID
    r = await client.get(f"/api/rag-eval/evaluations?knowledgeBaseId={_KB_ID}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(e["id"] == _EVALUATION_ID for e in data)


# ── 34.11  Start evaluation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_evaluation(client: httpx.AsyncClient) -> None:
    assert _EVALUATION_ID
    r = await client.post(f"/api/rag-eval/evaluations/{_EVALUATION_ID}/start")
    assert r.status_code == 200
    assert r.json()["success"] is True


# ── 34.12  Check evaluation status ──────────────────────────────────

@pytest.mark.asyncio
async def test_check_evaluation_status(client: httpx.AsyncClient) -> None:
    assert _EVALUATION_ID
    r = await client.get(f"/api/rag-eval/evaluations/{_EVALUATION_ID}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _EVALUATION_ID
    assert "status" in data


# ── 34.13  Delete evaluation ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_evaluation(client: httpx.AsyncClient) -> None:
    assert _EVALUATION_ID
    r = await client.delete(f"/api/rag-eval/evaluations/{_EVALUATION_ID}")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 34.14  Delete dataset record ────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_record(client: httpx.AsyncClient) -> None:
    assert _RECORD_ID
    r = await client.delete(f"/api/rag-eval/dataset-records/{_RECORD_ID}")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 34.15  Delete dataset ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_dataset(client: httpx.AsyncClient) -> None:
    assert _DATASET_ID
    r = await client.delete(f"/api/rag-eval/datasets/{_DATASET_ID}")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 34.16  Cleanup KB ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup(client: httpx.AsyncClient) -> None:
    if _KB_ID:
        await client.delete(f"/api/knowledge-bases/{_KB_ID}")
