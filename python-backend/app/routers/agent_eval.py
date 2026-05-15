"""Agent eval router — benchmarks, datasets, test cases, runs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.agent_eval.service import AgentEvalService

router = APIRouter(prefix="/api/agent-eval", tags=["Agent Eval"])


# ── Schemas ──────────────────────────────────────────────────────────

class BenchmarkCreate(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class DatasetCreate(BaseModel):
    benchmark_id: str
    name: str
    description: Optional[str] = None


class TestCaseCreate(BaseModel):
    input: str
    expected_output: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class RunCreate(BaseModel):
    benchmark_id: str
    dataset_id: Optional[str] = None
    config: Optional[dict[str, Any]] = None


# ── Benchmark endpoints ──────────────────────────────────────────────

@router.get("/benchmarks")
async def list_benchmarks(
    agent_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    benchmarks = await svc.list_benchmarks(agent_id)
    return [
        {
            "id": b.id,
            "agent_id": b.agent_id,
            "name": b.name,
            "description": b.description,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in benchmarks
    ]


@router.post("/benchmarks")
async def create_benchmark(
    body: BenchmarkCreate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    bench = await svc.create_benchmark(**body.model_dump(exclude_none=True))
    await session.commit()
    return {"id": bench.id}


@router.delete("/benchmarks/{benchmark_id}")
async def delete_benchmark(
    benchmark_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    await svc.delete_benchmark(benchmark_id)
    await session.commit()
    return {"ok": True}


# ── Dataset endpoints ────────────────────────────────────────────────

@router.get("/datasets")
async def list_datasets(
    benchmark_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    datasets = await svc.list_datasets(benchmark_id)
    return [
        {
            "id": d.id,
            "benchmark_id": d.benchmark_id,
            "name": d.name,
            "description": d.description,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]


@router.post("/datasets")
async def create_dataset(
    body: DatasetCreate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    ds = await svc.create_dataset(**body.model_dump(exclude_none=True))
    await session.commit()
    return {"id": ds.id}


# ── Test Case endpoints ──────────────────────────────────────────────

@router.get("/test-cases")
async def list_test_cases(
    dataset_id: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    cases = await svc.list_test_cases(dataset_id)
    return [
        {
            "id": c.id,
            "input": c.input,
            "expected_output": c.expected_output,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cases
    ]


@router.post("/test-cases")
async def create_test_case(
    dataset_id: str = Query(...),
    body: TestCaseCreate = ...,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    tc = await svc.create_test_case(
        dataset_id=dataset_id,
        input=body.input,
        expected_output=body.expected_output,
        metadata_=body.metadata,
    )
    await session.commit()
    return {"id": tc.id}


@router.post("/test-cases/batch")
async def batch_create_test_cases(
    dataset_id: str = Query(...),
    body: list[TestCaseCreate] = ...,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    cases = await svc.batch_create_test_cases(
        dataset_id,
        [c.model_dump() for c in body],
    )
    await session.commit()
    return {"created": len(cases)}


# ── Run endpoints ────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(
    benchmark_id: str = Query(...),
    limit: int = Query(default=50, le=200),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    runs = await svc.list_runs(benchmark_id, limit=limit)
    return [
        {
            "id": r.id,
            "benchmark_id": r.benchmark_id,
            "dataset_id": r.dataset_id,
            "status": r.status,
            "results": r.results,
            "error": r.error,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.post("/runs")
async def create_run(
    body: RunCreate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    run = await svc.create_run(**body.model_dump(exclude_none=True))
    await session.commit()
    return {"id": run.id}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {
        "id": run.id,
        "benchmark_id": run.benchmark_id,
        "status": run.status,
        "results": run.results,
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.post("/runs/{run_id}/execute")
async def execute_run(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    try:
        result = await svc.execute_run(run_id)
        await session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/runs/{run_id}/topics")
async def list_run_topics(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = AgentEvalService(session, user_id)
    topics = await svc.list_run_topics(run_id)
    return [
        {
            "id": t.id,
            "test_case_id": t.test_case_id,
            "status": t.status,
            "score": t.score,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in topics
    ]
