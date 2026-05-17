"""E2E tests for /api/agent-eval-external endpoints.

These tests depend on agent-eval data (benchmarks, datasets, runs) being
created first. We set up the required data via the /api/agent-eval endpoints.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/agent-eval-external"
EVAL_PREFIX = "/api/agent-eval"

# Module-level state
_AGENT_ID: str | None = None
_SESSION_ID: str | None = None
_BENCHMARK_ID: str | None = None
_DATASET_ID: str | None = None
_TEST_CASE_ID: str | None = None
_RUN_ID: str | None = None
_TOPIC_ID: str | None = None


# ── Setup ───────────────────────────────────────────────────────────


async def test_setup_agent(client):
    """Create an agent for eval tests."""
    global _AGENT_ID
    r = await client.post("/api/agents", json={"slug": "eval-ext-agent", "title": "EvalExtAgent"})
    assert r.status_code == 201
    _AGENT_ID = r.json()["id"]


async def test_setup_session(client):
    """Create a session for topic creation."""
    global _SESSION_ID
    assert _AGENT_ID
    r = await client.post("/api/sessions", json={"agent_id": _AGENT_ID})
    assert r.status_code == 201
    _SESSION_ID = r.json()["id"]


async def test_setup_topic(client):
    """Create a topic for messages/threads queries."""
    global _TOPIC_ID
    assert _SESSION_ID
    r = await client.post(
        "/api/topics",
        json={"session_id": _SESSION_ID, "title": "eval-ext-topic"},
    )
    assert r.status_code in (200, 201)
    _TOPIC_ID = r.json()["id"]


async def test_setup_benchmark(client):
    """Create a benchmark."""
    global _BENCHMARK_ID
    assert _AGENT_ID
    r = await client.post(
        f"{EVAL_PREFIX}/benchmarks",
        json={"name": "ext-bench", "agentId": _AGENT_ID},
    )
    assert r.status_code in (200, 201), f"Failed to create benchmark: {r.text}"
    _BENCHMARK_ID = r.json()["id"]


async def test_setup_dataset(client):
    """Create a dataset under the benchmark."""
    global _DATASET_ID
    if not _BENCHMARK_ID:
        pytest.skip("No benchmark")
    r = await client.post(
        f"{EVAL_PREFIX}/datasets",
        json={"name": "ext-ds", "benchmarkId": _BENCHMARK_ID},
    )
    assert r.status_code in (200, 201), f"Failed to create dataset: {r.text}"
    _DATASET_ID = r.json()["id"]


async def test_setup_test_case(client):
    """Create a test case in the dataset."""
    global _TEST_CASE_ID
    if not _DATASET_ID:
        pytest.skip("No dataset")
    r = await client.post(
        f"{EVAL_PREFIX}/test-cases",
        json={
            "datasetId": _DATASET_ID,
            "input": "What is the capital of France?",
            "expected_output": "Paris",
        },
    )
    assert r.status_code in (200, 201), f"Failed to create test case: {r.text}"
    _TEST_CASE_ID = r.json()["id"]


async def test_setup_run(client):
    """Create a run with benchmarkId."""
    global _RUN_ID
    if not _BENCHMARK_ID or not _DATASET_ID:
        pytest.skip("No benchmark/dataset")
    r = await client.post(
        f"{EVAL_PREFIX}/runs",
        json={
            "benchmarkId": _BENCHMARK_ID,
            "datasetId": _DATASET_ID,
            "name": "ext-run",
        },
    )
    assert r.status_code in (200, 201), f"Failed to create run: {r.text}"
    _RUN_ID = r.json()["id"]


# ── External API tests ──────────────────────────────────────────────


async def test_dataset_get(client):
    """GET /api/agent-eval-external/datasets/{id}"""
    if not _DATASET_ID:
        pytest.skip("No dataset")
    r = await client.get(f"{PREFIX}/datasets/{_DATASET_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _DATASET_ID


async def test_dataset_get_nonexistent(client):
    """GET nonexistent dataset returns 404."""
    r = await client.get(f"{PREFIX}/datasets/nonexistent-id")
    assert r.status_code == 404


async def test_run_get(client):
    """GET /api/agent-eval-external/runs/{id}"""
    if not _RUN_ID:
        pytest.skip("No run")
    r = await client.get(f"{PREFIX}/runs/{_RUN_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == _RUN_ID


async def test_run_topics_list(client):
    """GET /api/agent-eval-external/runs/{id}/topics"""
    if not _RUN_ID:
        pytest.skip("No run")
    r = await client.get(f"{PREFIX}/runs/{_RUN_ID}/topics")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


async def test_test_cases_count(client):
    """GET /api/agent-eval-external/test-cases/count?datasetId=..."""
    if not _DATASET_ID:
        pytest.skip("No dataset")
    r = await client.get(
        f"{PREFIX}/test-cases/count", params={"datasetId": _DATASET_ID}
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1


async def test_messages_list(client):
    """GET /api/agent-eval-external/messages?topicId=..."""
    if not _TOPIC_ID:
        pytest.skip("No topic")
    r = await client.get(
        f"{PREFIX}/messages", params={"topicId": _TOPIC_ID}
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_threads_list(client):
    """GET /api/agent-eval-external/threads?topicId=..."""
    if not _TOPIC_ID:
        pytest.skip("No topic")
    r = await client.get(
        f"{PREFIX}/threads", params={"topicId": _TOPIC_ID}
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Cleanup ─────────────────────────────────────────────────────────


async def test_cleanup(client):
    """Remove test data."""
    if _RUN_ID:
        await client.delete(f"{EVAL_PREFIX}/runs/{_RUN_ID}")
    if _TEST_CASE_ID:
        await client.delete(f"{EVAL_PREFIX}/test-cases/{_TEST_CASE_ID}")
    if _DATASET_ID:
        await client.delete(f"{EVAL_PREFIX}/datasets/{_DATASET_ID}")
    if _BENCHMARK_ID:
        await client.delete(f"{EVAL_PREFIX}/benchmarks/{_BENCHMARK_ID}")
    if _TOPIC_ID:
        await client.delete(f"/api/topics/{_TOPIC_ID}")
    if _SESSION_ID:
        await client.delete(f"/api/sessions/{_SESSION_ID}")
    if _AGENT_ID:
        await client.delete(f"/api/agents/{_AGENT_ID}")
