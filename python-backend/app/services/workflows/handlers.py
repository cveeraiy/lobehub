"""Shared workflow handlers for HTTP and Temporal transports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.misc import AsyncTask
from app.models.task import Brief, Task
from app.services.agent_eval.service import AgentEvalService
from app.services.task.runner import TaskRunnerService

try:
    from croniter import croniter
except Exception:  # pragma: no cover - dependency is optional until uv sync
    croniter = None


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def run_task_tick(session: AsyncSession, task_id: str, user_id: str) -> dict[str, Any]:
    runner = TaskRunnerService(session, user_id)
    return await runner.run_task(task_id)


def required(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return None


async def heartbeat_tick(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    task_id = required(payload, "taskId", "task_id")
    user_id = required(payload, "userId", "user_id")
    if not task_id or not user_id:
        raise ValueError("Missing required fields: taskId, userId")
    outcome = await run_task_tick(session, task_id, user_id)
    return {"success": True, **outcome}


async def schedule_execute(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    return await heartbeat_tick(payload, session)


async def schedule_dispatch(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    plan = await schedule_dispatch_plan(payload, session)
    if plan.get("dryRun") or not plan["due"]:
        return {
            "dispatched": 0,
            "dryRun": plan.get("dryRun", False),
            "due": len(plan["due"]),
            "skipped": plan["skipped"],
            "success": True,
            "total": plan["total"],
        }

    dispatched = 0
    failures: list[dict[str, str]] = []
    for item in plan["due"]:
        try:
            await run_task_tick(session, item["taskId"], item["userId"])
            dispatched += 1
        except Exception as exc:
            failures.append({"error": str(exc), "taskId": item["taskId"]})
    return {
        "dispatched": dispatched,
        "due": len(plan["due"]),
        "failures": failures,
        "skipped": plan["skipped"],
        "success": not failures,
        "total": plan["total"],
    }


def is_execution_time(
    *,
    cron_pattern: str,
    current_time: datetime | None = None,
    last_executed_at: datetime | None = None,
    timezone: str | None = None,
) -> bool:
    """Return whether a scheduled task is due for the current dispatcher tick."""
    if croniter is None:
        raise RuntimeError("croniter is required for schedule dispatch")

    try:
        tz = ZoneInfo(timezone or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    now = current_time or now_utc_naive()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(tz).replace(second=0, microsecond=0)

    if last_executed_at is not None:
        last = last_executed_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        last = last.astimezone(tz).replace(second=0, microsecond=0)
        if last >= now:
            return False

    return bool(croniter.match(cron_pattern, now))


async def schedule_dispatch_plan(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    dry_run = bool(payload.get("dryRun") or payload.get("dry_run"))
    now_raw = payload.get("now")
    now = None
    if isinstance(now_raw, str):
        try:
            now = datetime.fromisoformat(now_raw.replace("Z", "+00:00"))
        except ValueError:
            now = None

    tasks = (
        await session.execute(
            select(Task).where(
                and_(
                    Task.automation_mode == "schedule",
                    Task.status.in_(["scheduled", "backlog"]),
                    Task.schedule_pattern.isnot(None),
                )
            )
        )
    ).scalars().all()

    due = [
        {
            "pattern": task.schedule_pattern,
            "taskId": task.id,
            "taskIdentifier": task.identifier,
            "timezone": task.schedule_timezone,
            "userId": task.created_by_user_id,
        }
        for task in tasks
        if task.schedule_pattern
        and is_execution_time(
            cron_pattern=task.schedule_pattern,
            current_time=now,
            last_executed_at=task.last_heartbeat_at,
            timezone=task.schedule_timezone,
        )
    ]
    return {
        "dryRun": dry_run,
        "due": due,
        "skipped": len(tasks) - len(due),
        "success": True,
        "total": len(tasks),
    }


async def task_watchdog(_payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    now = now_utc_naive()
    tasks = (
        await session.execute(
            select(Task).where(
                and_(
                    Task.status == "running",
                    Task.automation_mode == "heartbeat",
                    Task.heartbeat_timeout.isnot(None),
                    Task.last_heartbeat_at.isnot(None),
                )
            )
        )
    ).scalars().all()
    failed = []
    for task in tasks:
        elapsed = (now - task.last_heartbeat_at).total_seconds()
        if task.heartbeat_timeout and elapsed > task.heartbeat_timeout:
            await session.execute(
                update(Task)
                .where(Task.id == task.id)
                .values(status="failed", error="Heartbeat timeout", completed_at=now, updated_at=now)
            )
            session.add(
                Brief(
                    agent_id=task.assignee_agent_id,
                    priority="urgent",
                    summary=f"Task has been running without heartbeat for more than {task.heartbeat_timeout} seconds.",
                    task_id=task.id,
                    title=f"{task.identifier} heartbeat timeout",
                    type="error",
                    user_id=task.created_by_user_id,
                )
            )
            failed.append(task.identifier)
    return {"checked": len(tasks), "failed": failed, "success": True}


async def run_eval_workflow(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    run_id = required(payload, "runId", "run_id")
    user_id = required(payload, "userId", "user_id")
    if not run_id or not user_id:
        raise ValueError("Missing required fields: runId, userId")
    svc = AgentEvalService(session, user_id)
    test_case_id = required(payload, "testCaseId", "test_case_id")
    if test_case_id:
        return await svc.execute_test_case(run_id, test_case_id)
    result = await svc.execute_run(run_id)
    return {"success": True, **result}


async def agent_eval_test_case_plan(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    run_id = required(payload, "runId", "run_id")
    user_id = required(payload, "userId", "user_id")
    if not run_id or not user_id:
        raise ValueError("Missing required fields: runId, userId")
    explicit_ids = payload.get("testCaseIds") or payload.get("test_case_ids")
    if isinstance(explicit_ids, list) and explicit_ids:
        return {"runId": run_id, "testCaseIds": [str(case_id) for case_id in explicit_ids], "userId": user_id}
    svc = AgentEvalService(session, user_id)
    return {"runId": run_id, "testCaseIds": await svc.list_run_test_case_ids(run_id), "userId": user_id}


async def finalize_eval_workflow(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    run_id = required(payload, "runId", "run_id")
    user_id = required(payload, "userId", "user_id")
    status_value = payload.get("status") or "completed"
    if not run_id or not user_id:
        raise ValueError("Missing required fields: runId, userId")
    svc = AgentEvalService(session, user_id)
    await svc.update_run_status(run_id, str(status_value))
    return {"runId": run_id, "status": status_value, "success": True}


async def memory_extraction_workflow(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    user_id = required(payload, "userId", "user_id")
    if not user_id:
        raise ValueError("Missing required field: userId")
    task = AsyncTask(user_id=user_id, type="memory_extraction", status="processing")
    session.add(task)
    await session.flush()
    from app.routers.user_memory import ExtractionFromChatTopicsBody, extraction_from_chat_topics

    result = await extraction_from_chat_topics(
        ExtractionFromChatTopicsBody(fromDate=payload.get("fromDate"), toDate=payload.get("toDate")),
        user_id,
        session,
    )
    return {"success": True, "taskId": result.get("id"), "metadata": result.get("metadata")}


async def memory_cancel_requested(payload: dict[str, Any], session: AsyncSession) -> bool:
    task_id = required(payload, "asyncTaskId", "async_task_id")
    user_id = required(payload, "userId", "user_id") or (payload.get("userIds") or [None])[0]
    if not task_id or not user_id:
        return False
    task = (
        await session.execute(select(AsyncTask).where(and_(AsyncTask.id == task_id, AsyncTask.user_id == user_id)))
    ).scalar_one_or_none()
    if not task:
        return False
    if task.status in {"canceled", "cancelled"}:
        return True
    error = task.error or {}
    return bool(error.get("cancelRequestedAt") or error.get("cancel_requested_at"))


async def memory_process_topic_workflow(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    user_id = required(payload, "userId", "user_id")
    topic_id = required(payload, "topicId", "topic_id")
    if not user_id or not topic_id:
        raise ValueError("Missing required fields: userId, topicId")
    from app.routers.user_memory import RequestMemoryFromTopicBody, request_memory_from_chat_topic

    result = await request_memory_from_chat_topic(RequestMemoryFromTopicBody(topic_id=topic_id), user_id, session)
    return {"success": True, **result}


async def persona_update_workflow(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    user_id = required(payload, "userId", "user_id")
    if not user_id:
        raise ValueError("Missing required field: userId")
    task = AsyncTask(user_id=user_id, type="persona_update", status="success")
    session.add(task)
    await session.flush()
    return {"success": True, "taskId": task.id}


async def agent_signal_run_workflow(payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    return {
        "message": "Agent signal workflow transport is retired; use /api/agent-signal endpoints",
        "retired": True,
        "success": False,
    }


WORKFLOW_HANDLERS = {
    "agent-eval-run/execute-test-case": run_eval_workflow,
    "agent-eval-run/finalize-run": finalize_eval_workflow,
    "agent-eval-run/on-thread-complete": finalize_eval_workflow,
    "agent-eval-run/on-trajectory-complete": finalize_eval_workflow,
    "agent-eval-run/paginate-test-cases": run_eval_workflow,
    "agent-eval-run/resume-agent-trajectory": run_eval_workflow,
    "agent-eval-run/resume-thread-trajectory": run_eval_workflow,
    "agent-eval-run/run-agent-trajectory": run_eval_workflow,
    "agent-eval-run/run-benchmark": run_eval_workflow,
    "agent-eval-run/run-thread-trajectory": run_eval_workflow,
    "agent-signal/run": agent_signal_run_workflow,
    "memory-user-memory/call-cron-hourly-analysis": memory_extraction_workflow,
    "memory-user-memory/pipelines/chat-topic/process-topic": memory_process_topic_workflow,
    "memory-user-memory/pipelines/chat-topic/process-topics": memory_extraction_workflow,
    "memory-user-memory/pipelines/chat-topic/process-user-topics": memory_extraction_workflow,
    "memory-user-memory/pipelines/chat-topic/process-users": memory_extraction_workflow,
    "memory-user-memory/pipelines/persona/update-writing": persona_update_workflow,
    "task/heartbeat-tick": heartbeat_tick,
    "task/schedule-dispatch": schedule_dispatch,
    "task/schedule-execute": schedule_execute,
    "task/watchdog": task_watchdog,
}

PLANNER_HANDLERS = {
    "agent-eval-run/test-cases:plan": agent_eval_test_case_plan,
    "memory-user-memory/cancel-check": memory_cancel_requested,
    "task/schedule-dispatch:plan": schedule_dispatch_plan,
}


async def execute_workflow_handler(name: str, payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    handler = WORKFLOW_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown workflow: {name}")
    return await handler(payload, session)


async def execute_workflow_planner(name: str, payload: dict[str, Any], session: AsyncSession) -> Any:
    handler = PLANNER_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown workflow planner: {name}")
    return await handler(payload, session)
