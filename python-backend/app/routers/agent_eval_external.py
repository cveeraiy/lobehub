"""Agent Eval External router — external/programmatic eval API.

Mirrors TS agentEvalExternalProcedure endpoints:
  datasetGet, runGet, runSetStatus, runTopicsList, runTopicReportResult,
  reportResult, reportResultsBatch, messagesList, threadsList, testCasesCount
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field as PField
from sqlalchemy import and_, asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.agent_eval.service import AgentEvalService

router = APIRouter(prefix="/api/agent-eval-external", tags=["Agent Eval External"])


# ── Schemas ──────────────────────────────────────────────────────────


class ReportResultBody(BaseModel):
    model_config = {"populate_by_name": True}
    run_id: str = PField(alias="runId")
    topic_id: str = PField(alias="topicId")
    correct: bool
    score: float
    result: Optional[dict[str, Any]] = None
    thread_id: Optional[str] = PField(default=None, alias="threadId")


class ReportResultsBatchBody(BaseModel):
    model_config = {"populate_by_name": True}
    run_id: str = PField(alias="runId")
    items: list[dict[str, Any]]


class RunSetStatusBody(BaseModel):
    model_config = {"populate_by_name": True}
    run_id: str = PField(alias="runId")
    status: str


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/datasets/{dataset_id}")
async def dataset_get(
    dataset_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get dataset by ID."""
    svc = AgentEvalService(session, user_id)
    ds = await svc.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    return {
        "id": ds.id,
        "benchmarkId": ds.benchmark_id,
        "name": ds.name,
        "identifier": getattr(ds, "identifier", None),
        "metadata": getattr(ds, "metadata_", None) or {},
    }


@router.get("/runs/{run_id}")
async def run_get(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get run by ID."""
    svc = AgentEvalService(session, user_id)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    config = dict(run.config or {})
    config.setdefault("k", 1)
    return {
        "id": run.id,
        "config": config,
        "createdAt": run.created_at.isoformat() if run.created_at else None,
        "datasetId": run.dataset_id,
        "metrics": getattr(run, "results", None),
        "name": getattr(run, "name", None),
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "status": run.status,
        "targetAgentId": getattr(run, "target_agent_id", None),
    }


@router.post("/runs/{run_id}/set-status")
async def run_set_status(
    run_id: str,
    body: RunSetStatusBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Set run status (external endpoint — only completed/external allowed)."""
    svc = AgentEvalService(session, user_id)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    if body.status not in ("completed", "external"):
        raise HTTPException(400, "External endpoint only supports setting status to completed or external")

    if run.status not in ("external", "completed"):
        raise HTTPException(400, f"Only external runs can be finalized via this endpoint. current={run.status}")

    if body.status == "completed":
        topics = await svc.list_run_topics(run_id)
        has_awaiting = any(
            t.status == "external"
            or (getattr(t, "eval_result", None) or {}).get("awaitingExternalEval") is True
            for t in topics
        )
        if has_awaiting:
            raise HTTPException(400, "Cannot set run to completed while external evaluation is pending")

    await svc.update_run_status(run_id, body.status)
    await session.commit()
    return {"success": True, "runId": run_id, "status": body.status}


@router.get("/runs/{run_id}/topics")
async def run_topics_list(
    run_id: str,
    only_external: bool = Query(default=False, alias="onlyExternal"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List run topics, optionally filtered to external-only."""
    svc = AgentEvalService(session, user_id)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    all_topics = await svc.list_run_topics(run_id)
    topics = (
        [t for t in all_topics if t.status == "external"]
        if only_external
        else all_topics
    )

    return [
        {
            "createdAt": t.created_at.isoformat() if t.created_at else None,
            "evalResult": getattr(t, "eval_result", None),
            "passed": getattr(t, "passed", None),
            "runId": t.run_id,
            "score": t.score,
            "status": t.status,
            "testCaseId": t.test_case_id,
            "topicId": getattr(t, "topic_id", None),
        }
        for t in topics
    ]


@router.post("/runs/{run_id}/report-result")
async def report_result(
    run_id: str,
    body: ReportResultBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Report result for a single test case topic."""
    svc = AgentEvalService(session, user_id)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    rt = await svc.find_run_topic_by_run_and_topic(run_id, body.topic_id)
    if not rt:
        raise HTTPException(404, "Run topic not found")

    eval_result = dict(getattr(rt, "eval_result", None) or {})
    rubric_scores = [{"rubricId": "external", "score": body.score}]
    eval_result["rubricScores"] = rubric_scores
    eval_result["awaitingExternalEval"] = False
    if body.result:
        eval_result["externalResult"] = body.result

    new_status = "passed" if body.correct else "failed"
    await svc.update_run_topic_by_run_and_topic(
        run_id,
        body.topic_id,
        eval_result=eval_result,
        passed=body.correct,
        score=body.score,
        status=new_status,
    )
    await session.commit()

    return {
        "success": True,
        "runId": run_id,
        "topicId": body.topic_id,
        "threadId": body.thread_id,
        "topicFinalized": True,
        "idempotent": False,
        "reportedThreads": 1,
        "totalThreads": 1,
    }


@router.post("/runs/{run_id}/report-results-batch")
async def report_results_batch(
    run_id: str,
    body: ReportResultsBatchBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Batch report results for multiple topics."""
    svc = AgentEvalService(session, user_id)
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    receipts = []
    for item in body.items:
        topic_id = item.get("topicId", "")
        correct = item.get("correct", False)
        score = item.get("score", 0)
        result = item.get("result")

        rt = await svc.find_run_topic_by_run_and_topic(run_id, topic_id)
        if not rt:
            receipts.append({"success": False, "topicId": topic_id, "error": "not found"})
            continue

        eval_result = dict(getattr(rt, "eval_result", None) or {})
        eval_result["rubricScores"] = [{"rubricId": "external", "score": score}]
        eval_result["awaitingExternalEval"] = False
        if result:
            eval_result["externalResult"] = result

        new_status = "passed" if correct else "failed"
        await svc.update_run_topic_by_run_and_topic(
            run_id, topic_id,
            eval_result=eval_result, passed=correct, score=score, status=new_status,
        )
        receipts.append({
            "success": True, "topicId": topic_id,
            "topicFinalized": True, "idempotent": False,
        })

    await session.commit()
    return {"success": True, "runId": run_id, "items": receipts}


@router.get("/test-cases/count")
async def test_cases_count(
    dataset_id: str = Query(alias="datasetId"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Count test cases for a dataset."""
    svc = AgentEvalService(session, user_id)
    count = await svc.count_test_cases(dataset_id)
    return {"count": count}


@router.get("/messages")
async def messages_list(
    topic_id: str = Query(alias="topicId"),
    thread_id: Optional[str] = Query(default=None, alias="threadId"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List messages for a topic/thread (simplified — uses raw SQL)."""
    from sqlalchemy import text
    params: dict[str, Any] = {"uid": user_id, "topic_id": topic_id}
    where = "user_id = :uid AND topic_id = :topic_id AND message_group_id IS NULL"
    if thread_id:
        where += " AND thread_id = :thread_id"
        params["thread_id"] = thread_id

    result = await session.execute(
        text(
            f"SELECT id, content, role, topic_id, thread_id, created_at "
            f"FROM messages WHERE {where} ORDER BY created_at ASC"
        ),
        params,
    )
    return [
        {
            "id": r[0],
            "content": r[1],
            "role": r[2],
            "topicId": r[3],
            "threadId": r[4],
            "createdAt": r[5].isoformat() if r[5] else None,
        }
        for r in result.fetchall()
    ]


@router.get("/threads")
async def threads_list(
    topic_id: str = Query(alias="topicId"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List threads for a topic."""
    from sqlalchemy import text
    result = await session.execute(
        text(
            "SELECT id, topic_id, type FROM threads "
            "WHERE topic_id = :topic_id AND user_id = :uid "
            "ORDER BY created_at ASC"
        ),
        {"topic_id": topic_id, "uid": user_id},
    )
    return [
        {"id": r[0], "topicId": r[1], "type": r[2]}
        for r in result.fetchall()
    ]
