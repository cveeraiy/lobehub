"""Task system router — CRUD, run, status, comments, briefs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.task.service import TaskService
from app.services.task.runner import TaskRunnerService
from app.services.task.lifecycle import TaskLifecycleService, TopicCompleteParams

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# ── Schemas ──────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    identifier: str
    seq: int = 0
    name: Optional[str] = None
    description: Optional[str] = None
    instruction: str
    status: str = "backlog"
    priority: int = 0
    parent_task_id: Optional[str] = None
    assignee_agent_id: Optional[str] = None
    automation_mode: Optional[str] = None
    heartbeat_interval: Optional[int] = None
    heartbeat_timeout: Optional[int] = None
    schedule_pattern: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    context: Optional[dict[str, Any]] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instruction: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    assignee_agent_id: Optional[str] = None
    automation_mode: Optional[str] = None
    heartbeat_interval: Optional[int] = None
    config: Optional[dict[str, Any]] = None
    context: Optional[dict[str, Any]] = None


class TaskRunRequest(BaseModel):
    continue_topic_id: Optional[str] = None
    extra_prompt: Optional[str] = None


class CommentCreate(BaseModel):
    task_id: str
    content: str
    author_agent_id: Optional[str] = None


class TopicCompleteRequest(BaseModel):
    task_id: str
    task_identifier: str
    operation_id: str
    reason: str
    topic_id: Optional[str] = None
    last_assistant_content: Optional[str] = None
    error_message: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    tasks = await svc.list_tasks(status=status, limit=limit, offset=offset)
    return [_serialize_task(t) for t in tasks]


@router.post("")
async def create_task(
    body: TaskCreate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    task = await svc.create(**body.model_dump(exclude_none=True))
    await session.commit()
    return _serialize_task(task)


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return _serialize_task(task)


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    updates = body.model_dump(exclude_none=True)
    if updates:
        await svc.update_fields(task.id, **updates)
        await session.commit()
    return {"ok": True}


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    await svc.delete_task(task.id)
    await session.commit()
    return {"ok": True}


@router.post("/{task_id}/run")
async def run_task(
    task_id: str,
    body: TaskRunRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    runner = TaskRunnerService(session, user_id)
    try:
        result = await runner.run_task(
            task_id,
            continue_topic_id=body.continue_topic_id,
            extra_prompt=body.extra_prompt,
        )
        await session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{task_id}/status")
async def update_status(
    task_id: str,
    status: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    await svc.update_status(task.id, status)
    await session.commit()
    return {"ok": True, "status": status}


# ── Topics ───────────────────────────────────────────────────────────

@router.get("/{task_id}/topics")
async def list_topics(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    topics = await svc.find_topics(task_id)
    return [
        {
            "id": t.id,
            "task_id": t.task_id,
            "topic_id": t.topic_id,
            "seq": t.seq,
            "status": t.status,
            "operation_id": t.operation_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in topics
    ]


# ── Briefs ───────────────────────────────────────────────────────────

@router.get("/{task_id}/briefs")
async def list_briefs(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    briefs = await svc.find_briefs(task_id)
    return [
        {
            "id": b.id,
            "type": b.type,
            "priority": b.priority,
            "title": b.title,
            "summary": b.summary,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in briefs
    ]


# ── Comments ─────────────────────────────────────────────────────────

@router.get("/{task_id}/comments")
async def list_comments(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    comments = await svc.get_comments(task_id)
    return [
        {
            "id": c.id,
            "content": c.content,
            "author_agent_id": c.author_agent_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ]


@router.post("/{task_id}/comments")
async def add_comment(
    task_id: str,
    body: CommentCreate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    comment = await svc.add_comment(
        task_id=task_id,
        content=body.content,
        author_agent_id=body.author_agent_id,
    )
    await session.commit()
    return {"id": comment.id}


# ── Subtasks ─────────────────────────────────────────────────────────

@router.get("/{task_id}/subtasks")
async def list_subtasks(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    svc = TaskService(session, user_id)
    subtasks = await svc.find_subtasks(task_id)
    return [_serialize_task(t) for t in subtasks]


# ── Lifecycle webhook ────────────────────────────────────────────────

@router.post("/lifecycle/on-topic-complete")
async def on_topic_complete(
    body: TopicCompleteRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    lifecycle = TaskLifecycleService(session, user_id)
    await lifecycle.on_topic_complete(TopicCompleteParams(
        task_id=body.task_id,
        task_identifier=body.task_identifier,
        operation_id=body.operation_id,
        reason=body.reason,
        topic_id=body.topic_id,
        last_assistant_content=body.last_assistant_content,
        error_message=body.error_message,
    ))
    await session.commit()
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

def _serialize_task(t: Any) -> dict[str, Any]:
    return {
        "id": t.id,
        "identifier": t.identifier,
        "name": t.name,
        "description": t.description,
        "instruction": t.instruction[:200] if t.instruction else "",
        "status": t.status,
        "priority": t.priority,
        "assignee_agent_id": t.assignee_agent_id,
        "parent_task_id": t.parent_task_id,
        "automation_mode": t.automation_mode,
        "total_topics": t.total_topics,
        "current_topic_id": t.current_topic_id,
        "error": t.error,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
