"""Phase 24 — Agent Eval: benchmarks, datasets, test cases, runs."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_setup_agent_for_eval(client: httpx.AsyncClient, state: SharedState) -> None:
    r = await client.post("/api/agents", json={
        "slug": f"eval-agent-{id(state)}",
        "title": "Eval Agent",
        "model": "gpt-4o-mini",
        "system_role": "test",
    })
    assert r.status_code == 201
    state.agent_id = r.json().get("id") or r.json().get("agentId")


@pytest.mark.asyncio
async def test_create_benchmark(client: httpx.AsyncClient, state: SharedState) -> None:
    assert state.agent_id
    r = await client.post("/api/agent-eval/benchmarks", json={
        "agent_id": state.agent_id,
        "name": "E2E Benchmark",
        "description": "Created by e2e tests",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.benchmark_id = data.get("id") or data.get("benchmarkId")


@pytest.mark.asyncio
async def test_list_benchmarks(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent-eval/benchmarks")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_dataset(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.benchmark_id:
        pytest.skip("No benchmark")
    r = await client.post("/api/agent-eval/datasets", json={
        "benchmark_id": state.benchmark_id,
        "name": "E2E Dataset",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.dataset_id = data.get("id") or data.get("datasetId")


@pytest.mark.asyncio
async def test_create_test_case(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.dataset_id:
        pytest.skip("No dataset")
    r = await client.post("/api/agent-eval/test-cases", json={
        "datasetId": state.dataset_id,
        "input": "What is 2+2?",
        "expected_output": "4",
    })
    assert r.status_code in (200, 201)


@pytest.mark.asyncio
async def test_list_test_cases(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.dataset_id:
        pytest.skip("No dataset")
    r = await client.get(f"/api/agent-eval/test-cases?dataset_id={state.dataset_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_eval_run(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.benchmark_id:
        pytest.skip("No benchmark")
    r = await client.post("/api/agent-eval/runs", json={
        "benchmark_id": state.benchmark_id,
        "name": "E2E Run",
    })
    assert r.status_code in (200, 201)
    data = r.json()
    state.eval_run_id = data.get("id") or data.get("runId")


@pytest.mark.asyncio
async def test_get_eval_run(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.eval_run_id:
        pytest.skip("No eval run")
    r = await client.get(f"/api/agent-eval/runs/{state.eval_run_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_list_eval_runs(client: httpx.AsyncClient, state: SharedState) -> None:
    if not state.benchmark_id:
        pytest.skip("No benchmark")
    r = await client.get(f"/api/agent-eval/runs?benchmark_id={state.benchmark_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_eval(client: httpx.AsyncClient, state: SharedState) -> None:
    if state.benchmark_id:
        await client.delete(f"/api/agent-eval/benchmarks/{state.benchmark_id}")
    if state.agent_id:
        await client.delete(f"/api/agents/{state.agent_id}")
