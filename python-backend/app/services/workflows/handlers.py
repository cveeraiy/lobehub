"""Shared workflow handlers for HTTP and Temporal transports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.misc import AsyncTask
from app.models.task import Brief, Task
from app.services.agent_eval.service import AgentEvalService
from app.services.task.runner import TaskRunnerService


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
    dry_run = bool(payload.get("dryRun") or payload.get("dry_run"))
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
    ]
    if dry_run:
        return {"dispatched": 0, "dryRun": True, "due": len(due), "skipped": 0, "success": True, "total": len(tasks)}

    dispatched = 0
    failures: list[dict[str, str]] = []
    for item in due:
        try:
            await run_task_tick(session, item["taskId"], item["userId"])
            dispatched += 1
        except Exception as exc:
            failures.append({"error": str(exc), "taskId": item["taskId"]})
    return {
        "dispatched": dispatched,
        "due": len(due),
        "failures": failures,
        "skipped": 0,
        "success": not failures,
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
    result = await svc.execute_run(run_id)
    return {"success": True, **result}


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


async def execute_workflow_handler(name: str, payload: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    handler = WORKFLOW_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown workflow: {name}")
    return await handler(payload, session)
