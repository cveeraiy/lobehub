"""Workflow transport endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.services.workflows.handlers import execute_workflow_handler
from app.services.workflows.temporal_backend import (
    TemporalUnavailableError,
    cancel_temporal_workflow,
    start_temporal_workflow,
    workflow_id_for,
)

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


class WorkflowCancelBody(BaseModel):
    workflow_id: str | None = Field(default=None, alias="workflowId")
    workflow_name: str | None = Field(default=None, alias="workflowName")
    workflow_run_id: str | None = Field(default=None, alias="workflowRunId")
    payload: dict[str, Any] = {}
    reason: str | None = None
    terminate: bool = False

    model_config = {"populate_by_name": True}


async def _json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


async def _run_workflow(name: str, payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    if settings.temporal_enabled:
        try:
            return await start_temporal_workflow(name, payload)
        except TemporalUnavailableError:
            if not settings.temporal_fallback_to_inline:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Temporal backend is unavailable") from None
        except Exception as exc:
            if not settings.temporal_fallback_to_inline:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Temporal backend failed: {exc}") from exc
    try:
        return await execute_workflow_handler(name, payload, session)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/control/cancel")
async def cancel_workflow(body: WorkflowCancelBody):
    workflow_id = body.workflow_id
    if not workflow_id and body.workflow_name:
        workflow_id = workflow_id_for(body.workflow_name, body.payload)
    if not workflow_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "workflowId or workflowName is required")
    try:
        return await cancel_temporal_workflow(
            workflow_id,
            reason=body.reason,
            run_id=body.workflow_run_id,
            terminate=body.terminate,
        )
    except TemporalUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Temporal backend is unavailable") from None
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Temporal backend failed: {exc}") from exc


@router.post("/task/heartbeat-tick")
async def heartbeat_tick(request: Request, session: AsyncSession = Depends(get_db)):
    return await _run_workflow("task/heartbeat-tick", await _json(request), session)


@router.post("/task/schedule-execute")
async def schedule_execute(request: Request, session: AsyncSession = Depends(get_db)):
    return await _run_workflow("task/schedule-execute", await _json(request), session)


@router.post("/task/schedule-dispatch")
async def schedule_dispatch(request: Request, session: AsyncSession = Depends(get_db)):
    return await _run_workflow("task/schedule-dispatch", await _json(request), session)


@router.post("/task/watchdog")
async def task_watchdog(session: AsyncSession = Depends(get_db)):
    return await _run_workflow("task/watchdog", {}, session)


@router.post("/agent-eval-run/run-benchmark")
@router.post("/agent-eval-run/run-agent-trajectory")
@router.post("/agent-eval-run/run-thread-trajectory")
@router.post("/agent-eval-run/resume-agent-trajectory")
@router.post("/agent-eval-run/resume-thread-trajectory")
@router.post("/agent-eval-run/execute-test-case")
@router.post("/agent-eval-run/paginate-test-cases")
async def run_eval_workflow(request: Request, session: AsyncSession = Depends(get_db)):
    name = request.url.path.removeprefix("/api/workflows/")
    return await _run_workflow(name, await _json(request), session)


@router.post("/agent-eval-run/finalize-run")
@router.post("/agent-eval-run/on-thread-complete")
@router.post("/agent-eval-run/on-trajectory-complete")
async def finalize_eval_workflow(request: Request, session: AsyncSession = Depends(get_db)):
    name = request.url.path.removeprefix("/api/workflows/")
    return await _run_workflow(name, await _json(request), session)


@router.post("/memory-user-memory/call-cron-hourly-analysis")
@router.post("/memory-user-memory/pipelines/chat-topic/process-users")
@router.post("/memory-user-memory/pipelines/chat-topic/process-user-topics")
@router.post("/memory-user-memory/pipelines/chat-topic/process-topics")
async def memory_extraction_workflow(request: Request, session: AsyncSession = Depends(get_db)):
    name = request.url.path.removeprefix("/api/workflows/")
    return await _run_workflow(name, await _json(request), session)


@router.post("/memory-user-memory/pipelines/chat-topic/process-topic")
async def memory_process_topic_workflow(request: Request, session: AsyncSession = Depends(get_db)):
    return await _run_workflow("memory-user-memory/pipelines/chat-topic/process-topic", await _json(request), session)


@router.post("/memory-user-memory/pipelines/persona/update-writing")
async def persona_update_workflow(request: Request, session: AsyncSession = Depends(get_db)):
    return await _run_workflow("memory-user-memory/pipelines/persona/update-writing", await _json(request), session)


@router.post("/agent-signal/run")
async def agent_signal_run_workflow():
    """Retired TS/Upstash transport for agent signal jobs."""
    raise HTTPException(
        status.HTTP_410_GONE,
        "Agent signal workflow transport is retired; use /api/agent-signal endpoints",
    )
