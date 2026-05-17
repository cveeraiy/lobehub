"""E2E tests for /api/generations and /api/generation-batches endpoints.

Uses /api/image/create to atomically create batch + generation records
(this endpoint writes DB records before dispatching to background workers,
so it works without an LLM).
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

GEN_PREFIX = "/api/generations"
BATCH_PREFIX = "/api/generation-batches"
TOPIC_PREFIX = "/api/generation/topics"

# Module-level state
_TOPIC_ID: str | None = None
_BATCH_ID: str | None = None
_GENERATION_ID: str | None = None


# ── Setup: create generation topic + batch + generation ─────────────


async def test_setup_topic(client):
    """Create a generation topic via the generation router."""
    global _TOPIC_ID
    r = await client.post(TOPIC_PREFIX, json={"title": "Gen Test Topic", "type": "text2image"})
    assert r.status_code == 201
    _TOPIC_ID = r.json()["id"]


async def test_setup_batch_and_generation(client):
    """POST /api/image/create creates batch + generation records atomically."""
    global _BATCH_ID, _GENERATION_ID
    assert _TOPIC_ID
    r = await client.post(
        "/api/image/create",
        json={
            "generationTopicId": _TOPIC_ID,
            "imageNum": 1,
            "model": "test/fake-model",
            "provider": "test-provider",
            "params": {"prompt": "a cute cat"},
        },
    )
    assert r.status_code == 200, f"Failed to create image batch: {r.text}"
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    _BATCH_ID = data["batch"]["id"]
    assert len(data["generations"]) >= 1
    _GENERATION_ID = data["generations"][0]["id"]


# ── Generation Batches ──────────────────────────────────────────────


async def test_list_generation_batches(client):
    """GET /api/generation-batches?topicId=... lists batches for topic."""
    assert _TOPIC_ID
    r = await client.get(BATCH_PREFIX, params={"topicId": _TOPIC_ID})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(b["id"] == _BATCH_ID for b in data)


async def test_list_generation_batches_no_filter(client):
    """GET /api/generation-batches without topicId returns all user batches."""
    r = await client.get(BATCH_PREFIX)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_list_generation_batches_with_type(client):
    """GET /api/generation-batches?type=text2image filters by type."""
    r = await client.get(BATCH_PREFIX, params={"type": "text2image"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # All returned generations should be text2image type
    for batch in data:
        for gen in batch.get("generations", []):
            if gen.get("type"):
                assert "text2image" in gen["type"]


async def test_batch_includes_generations(client):
    """GET /api/generation-batches returns nested generations."""
    assert _BATCH_ID
    r = await client.get(BATCH_PREFIX, params={"topicId": _TOPIC_ID})
    assert r.status_code == 200
    batch = next(b for b in r.json() if b["id"] == _BATCH_ID)
    assert "generations" in batch
    assert len(batch["generations"]) >= 1
    gen = batch["generations"][0]
    assert gen["id"] == _GENERATION_ID
    assert gen["status"] == "pending"


# ── Generations ─────────────────────────────────────────────────────


async def test_get_generation_status(client):
    """GET /api/generations/{id}/status returns generation status."""
    assert _GENERATION_ID
    r = await client.get(f"{GEN_PREFIX}/{_GENERATION_ID}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _GENERATION_ID
    assert data["status"] == "pending"
    assert "fileId" in data


async def test_get_generation_status_nonexistent(client):
    """GET /api/generations/{id}/status returns 404 for nonexistent."""
    r = await client.get(f"{GEN_PREFIX}/nonexistent-gen-id/status")
    assert r.status_code == 404


async def test_delete_generation_nonexistent(client):
    """DELETE /api/generations/{id} is a no-op for nonexistent."""
    r = await client.delete(f"{GEN_PREFIX}/nonexistent-gen-id")
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_delete_generation(client):
    """DELETE /api/generations/{id} removes the generation."""
    assert _GENERATION_ID
    r = await client.delete(f"{GEN_PREFIX}/{_GENERATION_ID}")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Verify it's gone
    r2 = await client.get(f"{GEN_PREFIX}/{_GENERATION_ID}/status")
    assert r2.status_code == 404


# ── Delete batch ────────────────────────────────────────────────────


async def test_delete_nonexistent_batch(client):
    """DELETE /api/generation-batches/{id} for nonexistent returns null."""
    r = await client.delete(f"{BATCH_PREFIX}/nonexistent-batch-id")
    assert r.status_code == 200


async def test_delete_generation_batch(client):
    """DELETE /api/generation-batches/{id} removes batch + its generations."""
    assert _BATCH_ID
    r = await client.delete(f"{BATCH_PREFIX}/{_BATCH_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _BATCH_ID


# ── Generation Topics (verify still listed) ────────────────────────


async def test_list_generation_topics(client):
    """GET /api/generation/topics lists topics."""
    r = await client.get(TOPIC_PREFIX)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(t["id"] == _TOPIC_ID for t in data)


# ── Cleanup ─────────────────────────────────────────────────────────


async def test_cleanup(client):
    """Delete generation topic."""
    if _TOPIC_ID:
        r = await client.delete(f"{TOPIC_PREFIX}/{_TOPIC_ID}")
        assert r.status_code == 200
