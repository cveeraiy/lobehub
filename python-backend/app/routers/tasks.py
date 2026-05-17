"""Task system router — CRUD, run, status, comments, briefs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field as PField
from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.task import Brief, Task, TaskComment, TaskDependency, TaskDocument, TaskTopic
from app.models.topic import Topic
from app.services.task.service import TaskService
from app.services.task.runner import TaskRunnerService
from app.services.task.lifecycle import TaskLifecycleService, TopicCompleteParams

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# ── Schemas ──────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    identifier: str = ""
    seq: int = 0
    name: Optional[str] = None
    description: Optional[str] = None
    instruction: str
    status: str = "backlog"
    priority: int = 0
    parent_task_id: Optional[str] = PField(default=None, alias="parentTaskId")
    assignee_agent_id: Optional[str] = PField(default=None, alias="assigneeAgentId")
    assignee_user_id: Optional[str] = PField(default=None, alias="assigneeUserId")
    created_by_agent_id: Optional[str] = PField(default=None, alias="createdByAgentId")
    identifier_prefix: Optional[str] = PField(default=None, alias="identifierPrefix")
    automation_mode: Optional[str] = PField(default=None, alias="automationMode")
    heartbeat_interval: Optional[int] = PField(default=None, alias="heartbeatInterval")
    heartbeat_timeout: Optional[int] = PField(default=None, alias="heartbeatTimeout")
    schedule_pattern: Optional[str] = PField(default=None, alias="schedulePattern")
    config: Optional[dict[str, Any]] = None
    context: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instruction: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    assignee_agent_id: Optional[str] = PField(default=None, alias="assigneeAgentId")
    assignee_user_id: Optional[str] = PField(default=None, alias="assigneeUserId")
    automation_mode: Optional[str] = PField(default=None, alias="automationMode")
    heartbeat_interval: Optional[int] = PField(default=None, alias="heartbeatInterval")
    heartbeat_timeout: Optional[int] = PField(default=None, alias="heartbeatTimeout")
    schedule_pattern: Optional[str] = PField(default=None, alias="schedulePattern")
    schedule_timezone: Optional[str] = PField(default=None, alias="scheduleTimezone")
    config: Optional[dict[str, Any]] = None
    context: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class TaskRunRequest(BaseModel):
    continue_topic_id: Optional[str] = PField(default=None, alias="continueTopicId")
    prompt: Optional[str] = None
    extra_prompt: Optional[str] = PField(default=None, alias="extraPrompt")

    model_config = {"populate_by_name": True}


class CommentCreate(BaseModel):
    content: str
    task_id: Optional[str] = PField(default=None, alias="taskId")
    author_agent_id: Optional[str] = PField(default=None, alias="authorAgentId")
    brief_id: Optional[str] = PField(default=None, alias="briefId")
    topic_id: Optional[str] = PField(default=None, alias="topicId")

    model_config = {"populate_by_name": True}


class UpdateStatusBody(BaseModel):
    status: str
    error: Optional[str] = None


class TopicCompleteRequest(BaseModel):
    task_id: str
    task_identifier: str
    operation_id: str
    reason: str
    topic_id: Optional[str] = None
    last_assistant_content: Optional[str] = None
    error_message: Optional[str] = None


# ── Fixed-path endpoints (must be before /{task_id} catch-all) ─────

# ── Flat comment routes (frontend uses paths without task_id) ──────


@router.put("/comments/{comment_id}")
async def update_comment_flat(
    comment_id: str,
    body: UpdateCommentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update a task comment (flat path — no task_id required)."""
    comment = (await session.execute(
        select(TaskComment).where(and_(
            TaskComment.id == comment_id,
            TaskComment.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "Comment not found")
    await session.execute(
        update(TaskComment).where(TaskComment.id == comment_id).values(
            content=body.content, updated_at=_now()
        )
    )
    return {"success": True, "message": "Comment updated"}


@router.delete("/comments/{comment_id}")
async def delete_comment_flat(
    comment_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a task comment (flat path — no task_id required)."""
    result = await session.execute(
        delete(TaskComment).where(and_(
            TaskComment.id == comment_id,
            TaskComment.user_id == user_id,
        ))
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Comment not found")
    return {"success": True, "message": "Comment deleted"}


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_tasks(
    status: Optional[str] = None,
    statuses: Optional[str] = None,
    priorities: Optional[str] = None,
    assigneeAgentId: Optional[str] = None,
    parentTaskId: Optional[str] = None,
    parentIdentifier: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Task).where(Task.created_by_user_id == user_id)
    count_stmt = select(func.count()).select_from(Task).where(Task.created_by_user_id == user_id)

    if status:
        stmt = stmt.where(Task.status == status)
        count_stmt = count_stmt.where(Task.status == status)
    if statuses:
        vals = [s.strip() for s in statuses.split(",")]
        stmt = stmt.where(Task.status.in_(vals))
        count_stmt = count_stmt.where(Task.status.in_(vals))
    if priorities:
        vals = [int(p.strip()) for p in priorities.split(",")]
        stmt = stmt.where(Task.priority.in_(vals))
        count_stmt = count_stmt.where(Task.priority.in_(vals))
    if assigneeAgentId:
        stmt = stmt.where(Task.assignee_agent_id == assigneeAgentId)
        count_stmt = count_stmt.where(Task.assignee_agent_id == assigneeAgentId)

    resolved_parent_id = parentTaskId
    if parentIdentifier:
        parent = (await session.execute(
            select(Task).where(and_(
                Task.created_by_user_id == user_id,
                Task.identifier == parentIdentifier.upper(),
            ))
        )).scalar_one_or_none()
        if parent:
            resolved_parent_id = parent.id
        else:
            return {"data": [], "success": True, "total": 0}

    if resolved_parent_id is not None:
        if resolved_parent_id == "":
            stmt = stmt.where(Task.parent_task_id.is_(None))
            count_stmt = count_stmt.where(Task.parent_task_id.is_(None))
        else:
            stmt = stmt.where(Task.parent_task_id == resolved_parent_id)
            count_stmt = count_stmt.where(Task.parent_task_id == resolved_parent_id)

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Task.sort_order, desc(Task.created_at)).offset(offset).limit(limit)
    tasks = (await session.execute(stmt)).scalars().all()
    return {"data": [_serialize_task(t) for t in tasks], "success": True, "total": total}


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
@router.put("/{task_id}")
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
    updates = body.model_dump(exclude_none=True, by_alias=False)
    if updates:
        await svc.update_fields(task.id, **updates)
        await session.commit()
    updated = await svc.resolve(task_id)
    return {"data": _serialize_task(updated) if updated else None, "message": "Task updated", "success": True}


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
        extra = body.extra_prompt or body.prompt
        result = await runner.run_task(
            task_id,
            continue_topic_id=body.continue_topic_id,
            extra_prompt=extra,
        )
        await session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/{task_id}/status")
@router.post("/{task_id}/status")
async def update_status(
    task_id: str,
    body: Optional[UpdateStatusBody] = None,
    status: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    new_status = (body.status if body else None) or status
    error_msg = body.error if body else None
    if not new_status:
        raise HTTPException(400, "status is required")

    if error_msg and new_status != "failed":
        raise HTTPException(400, "Task error can only be provided when status is failed.")

    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    extra: dict[str, Any] = {}
    if new_status == "running":
        extra["started_at"] = _now()
    if new_status in ("completed", "failed", "canceled"):
        extra["completed_at"] = _now()
    if error_msg:
        extra["error"] = error_msg

    await svc.update_status(task.id, new_status)
    if extra:
        await session.execute(
            update(Task).where(Task.id == task.id).values(**extra, updated_at=_now())
        )
    await session.commit()
    updated = await svc.resolve(task_id)
    return {"data": _serialize_task(updated) if updated else None, "message": f"Task {new_status}", "success": True}


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
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    comment = TaskComment(
        task_id=task.id,
        user_id=user_id,
        author_user_id=user_id,
        author_agent_id=body.author_agent_id,
        content=body.content,
        brief_id=body.brief_id,
        topic_id=body.topic_id,
    )
    session.add(comment)
    await session.commit()
    return {"data": _serialize_comment(comment), "message": "Comment added", "success": True}


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
        "sortOrder": t.sort_order,
        "assigneeAgentId": t.assignee_agent_id,
        "assigneeUserId": getattr(t, "assignee_user_id", None),
        "parentTaskId": t.parent_task_id,
        "automationMode": t.automation_mode,
        "totalTopics": t.total_topics,
        "currentTopicId": t.current_topic_id,
        "error": t.error,
        "heartbeatInterval": t.heartbeat_interval,
        "heartbeatTimeout": t.heartbeat_timeout,
        "lastHeartbeatAt": t.last_heartbeat_at.isoformat() if t.last_heartbeat_at else None,
        "schedulePattern": getattr(t, "schedule_pattern", None),
        "scheduleTimezone": getattr(t, "schedule_timezone", None),
        "config": t.config,
        "context": t.context,
        "startedAt": t.started_at.isoformat() if t.started_at else None,
        "completedAt": t.completed_at.isoformat() if t.completed_at else None,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
        "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
    }


def _serialize_comment(c: Any) -> dict[str, Any]:
    return {
        "id": c.id,
        "taskId": c.task_id,
        "content": c.content,
        "authorUserId": getattr(c, "author_user_id", None),
        "authorAgentId": c.author_agent_id,
        "briefId": getattr(c, "brief_id", None),
        "topicId": getattr(c, "topic_id", None),
        "createdAt": c.created_at.isoformat() if c.created_at else None,
        "updatedAt": c.updated_at.isoformat() if getattr(c, "updated_at", None) else None,
    }


# ── Missing TS parity endpoints ────────────────────────────────────


class DependencyBody(BaseModel):
    depends_on_id: str = PField(alias="dependsOnId")
    type: str = "blocks"  # 'blocks' | 'relates'

    model_config = {"populate_by_name": True}


class PinDocumentBody(BaseModel):
    document_id: str = PField(alias="documentId")
    pinned_by: str = PField(default="user", alias="pinnedBy")

    model_config = {"populate_by_name": True}


class ReorderSubtasksBody(BaseModel):
    order: list[str]


class UpdateCheckpointBody(BaseModel):
    checkpoint: dict[str, Any]


class UpdateReviewBody(BaseModel):
    review: dict[str, Any]


class RunReviewBody(BaseModel):
    content: Optional[str] = None
    topic_id: Optional[str] = PField(default=None, alias="topicId")

    model_config = {"populate_by_name": True}


class UpdateConfigBody(BaseModel):
    config: dict[str, Any]


class GroupListBody(BaseModel):
    groups: list[dict[str, Any]]
    parent_task_id: Optional[str] = PField(default=None, alias="parentTaskId")
    assignee_agent_id: Optional[str] = PField(default=None, alias="assigneeAgentId")

    model_config = {"populate_by_name": True}


class UpdateCommentBody(BaseModel):
    content: str


# ── Dependencies ────────────────────────────────────────────────────


@router.post("/{task_id}/dependencies")
async def add_dependency(
    task_id: str,
    body: DependencyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Add a dependency between tasks."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    dep_task = await svc.resolve(body.depends_on_id)
    if not dep_task:
        raise HTTPException(404, "Dependency task not found")
    td = TaskDependency(
        task_id=task.id,
        depends_on_id=dep_task.id,
        user_id=user_id,
        type=body.type,
    )
    session.add(td)
    await session.flush()
    return {"success": True, "message": "Dependency added"}


@router.delete("/{task_id}/dependencies/{depends_on_id}")
async def remove_dependency(
    task_id: str,
    depends_on_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove a dependency between tasks."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    dep_task = await svc.resolve(depends_on_id)
    if not dep_task:
        raise HTTPException(404, "Dependency task not found")
    await session.execute(
        delete(TaskDependency).where(and_(
            TaskDependency.task_id == task.id,
            TaskDependency.depends_on_id == dep_task.id,
            TaskDependency.user_id == user_id,
        ))
    )
    return {"success": True, "message": "Dependency removed"}


@router.get("/{task_id}/dependencies")
async def get_dependencies(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get all dependencies for a task."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    deps = (await session.execute(
        select(TaskDependency).where(and_(
            TaskDependency.task_id == task.id,
            TaskDependency.user_id == user_id,
        ))
    )).scalars().all()
    return [
        {
            "id": d.id,
            "task_id": d.task_id,
            "depends_on_id": d.depends_on_id,
            "type": d.type,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in deps
    ]


# ── Pinned Documents ────────────────────────────────────────────────


@router.post("/{task_id}/pinned-documents")
async def pin_document(
    task_id: str,
    body: PinDocumentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Pin a document to a task."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    td = TaskDocument(
        task_id=task.id,
        document_id=body.document_id,
        user_id=user_id,
        pinned_by=body.pinned_by,
    )
    session.add(td)
    await session.flush()
    return {"success": True, "message": "Document pinned"}


@router.delete("/{task_id}/pinned-documents/{document_id}")
async def unpin_document(
    task_id: str,
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Unpin a document from a task."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    await session.execute(
        delete(TaskDocument).where(and_(
            TaskDocument.task_id == task.id,
            TaskDocument.document_id == document_id,
            TaskDocument.user_id == user_id,
        ))
    )
    return {"success": True, "message": "Document unpinned"}


@router.get("/{task_id}/pinned-documents")
async def get_pinned_documents(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get all pinned documents for a task."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    docs = (await session.execute(
        select(TaskDocument).where(and_(
            TaskDocument.task_id == task.id,
            TaskDocument.user_id == user_id,
        ))
    )).scalars().all()
    return [
        {
            "id": d.id,
            "task_id": d.task_id,
            "document_id": d.document_id,
            "pinned_by": d.pinned_by,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


# ── Reorder / Heartbeat / Watchdog ─────────────────────────────────


@router.post("/{task_id}/reorder-subtasks")
@router.put("/{task_id}/subtasks/order")
async def reorder_subtasks(
    task_id: str,
    body: ReorderSubtasksBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Reorder subtasks by identifier list."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    subtasks = await svc.find_subtasks(task.id)
    id_map = {s.identifier.upper(): s.id for s in subtasks}
    result = []
    for i, ident in enumerate(body.order):
        key = ident.upper()
        tid = id_map.get(key)
        if not tid:
            raise HTTPException(400, f"Subtask not found: {ident}")
        await session.execute(
            update(Task).where(Task.id == tid).values(sort_order=i, updated_at=_now())
        )
        result.append({"identifier": ident, "sortOrder": i})
    return {"success": True, "data": result}


@router.post("/{task_id}/heartbeat")
async def heartbeat(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update task heartbeat timestamp."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    await session.execute(
        update(Task).where(Task.id == task.id).values(
            last_heartbeat_at=_now(),
            updated_at=_now(),
        )
    )
    return {"success": True, "message": "Heartbeat updated"}


@router.post("/watchdog")
async def watchdog(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Find tasks that have timed out on heartbeat and mark them failed."""
    now = _now()
    stmt = select(Task).where(and_(
        Task.status == "running",
        Task.automation_mode == "heartbeat",
        Task.heartbeat_timeout.isnot(None),
        Task.last_heartbeat_at.isnot(None),
    ))
    tasks = (await session.execute(stmt)).scalars().all()
    failed = []
    for t in tasks:
        elapsed = (now - t.last_heartbeat_at).total_seconds()
        if t.heartbeat_timeout and elapsed > t.heartbeat_timeout:
            await session.execute(
                update(Task).where(Task.id == t.id).values(
                    status="failed",
                    error="Heartbeat timeout",
                    completed_at=now,
                    updated_at=now,
                )
            )
            brief = Brief(
                user_id=t.created_by_user_id,
                task_id=t.id,
                agent_id=t.assignee_agent_id,
                type="error",
                priority="urgent",
                title=f"{t.identifier} heartbeat timeout",
                summary=f"Task has been running without heartbeat for more than {t.heartbeat_timeout} seconds.",
            )
            session.add(brief)
            failed.append(t.identifier)
    return {
        "success": True,
        "checked": len(tasks),
        "failed": failed,
        "message": f"{len(failed)} stuck tasks marked as failed" if failed else "No stuck tasks found",
    }


# ── Checkpoints ─────────────────────────────────────────────────────


@router.get("/{task_id}/checkpoint")
async def get_checkpoint(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get checkpoint configuration from task config."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    config = task.config or {}
    return {"success": True, "data": config.get("checkpoint")}


@router.put("/{task_id}/checkpoint")
async def update_checkpoint(
    task_id: str,
    body: UpdateCheckpointBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update checkpoint configuration in task config."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    config = dict(task.config or {})
    config["checkpoint"] = body.checkpoint
    await session.execute(
        update(Task).where(Task.id == task.id).values(config=config, updated_at=_now())
    )
    return {"success": True, "data": body.checkpoint}


# ── Reviews ─────────────────────────────────────────────────────────


@router.get("/{task_id}/review")
async def get_review(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get review configuration from task config."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    config = task.config or {}
    return {"success": True, "data": config.get("review")}


@router.put("/{task_id}/review")
async def update_review(
    task_id: str,
    body: UpdateReviewBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update review configuration in task config."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    config = dict(task.config or {})
    config["review"] = body.review
    await session.execute(
        update(Task).where(Task.id == task.id).values(config=config, updated_at=_now())
    )
    return {"success": True, "data": body.review}


@router.post("/{task_id}/run-review")
@router.post("/{task_id}/review/run")
async def run_review(
    task_id: str,
    body: RunReviewBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Run review on task output (placeholder — needs TaskReviewService)."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    config = task.config or {}
    review_config = config.get("review")
    if not review_config or not review_config.get("enabled"):
        raise HTTPException(400, "Review is not enabled for this task")
    if not body.content:
        raise HTTPException(400, "Content is required for review")
    return {
        "success": True,
        "data": {
            "passed": True,
            "overallScore": 1.0,
            "rubricResults": [],
            "message": "Review placeholder — implement TaskReviewService integration",
        },
    }


# ── Config Update ───────────────────────────────────────────────────


@router.put("/{task_id}/config")
async def update_config(
    task_id: str,
    body: UpdateConfigBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update task config (merge with existing)."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    config = dict(task.config or {})
    config.update(body.config)
    await session.execute(
        update(Task).where(Task.id == task.id).values(config=config, updated_at=_now())
    )
    return {"success": True, "data": config}


# ── Task Tree ───────────────────────────────────────────────────────


@router.get("/{task_id}/tree")
async def get_task_tree(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get task with full subtask tree (recursive)."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    async def _build_tree(t: Task) -> dict[str, Any]:
        subtasks = await svc.find_subtasks(t.id)
        children = [await _build_tree(s) for s in subtasks]
        node = _serialize_task(t)
        node["children"] = children
        return node

    tree = await _build_tree(task)
    return {"success": True, "data": tree}


# ── Group List ──────────────────────────────────────────────────────


@router.post("/group-list")
async def group_list(
    body: GroupListBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Fetch tasks grouped by status groups."""
    results: dict[str, Any] = {}
    for group in body.groups:
        key = group["key"]
        statuses = group.get("statuses", [])
        limit = group.get("limit", 50)
        offset = group.get("offset", 0)
        stmt = (
            select(Task)
            .where(and_(
                Task.created_by_user_id == user_id,
                Task.status.in_(statuses),
            ))
        )
        if body.parent_task_id is not None:
            stmt = stmt.where(Task.parent_task_id == body.parent_task_id)
        if body.assignee_agent_id:
            stmt = stmt.where(Task.assignee_agent_id == body.assignee_agent_id)
        stmt = stmt.order_by(Task.sort_order, Task.created_at.desc()).offset(offset).limit(limit)
        tasks = (await session.execute(stmt)).scalars().all()
        results[key] = {
            "tasks": [_serialize_task(t) for t in tasks],
            "total": len(tasks),
        }
    return {"success": True, "data": results}


# ── Cancel / Delete Topic ───────────────────────────────────────────


@router.post("/topics/{topic_id}/cancel")
async def cancel_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Cancel a running task topic."""
    tt = (await session.execute(
        select(TaskTopic).where(and_(
            TaskTopic.topic_id == topic_id,
            TaskTopic.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not tt:
        raise HTTPException(404, "Topic not found")
    if tt.status != "running":
        raise HTTPException(400, f"Topic is not running (current status: {tt.status})")
    await session.execute(
        update(TaskTopic).where(TaskTopic.id == tt.id).values(
            status="canceled", updated_at=_now()
        )
    )
    await session.execute(
        update(Task).where(Task.id == tt.task_id).values(
            status="paused", updated_at=_now()
        )
    )
    return {"success": True, "message": "Topic canceled"}


@router.delete("/topics/{topic_id}")
async def delete_topic(
    topic_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a task topic and its associated topic."""
    tt = (await session.execute(
        select(TaskTopic).where(and_(
            TaskTopic.topic_id == topic_id,
            TaskTopic.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not tt:
        raise HTTPException(404, "Topic not found")
    await session.execute(
        delete(TaskTopic).where(TaskTopic.id == tt.id)
    )
    await session.execute(
        delete(Topic).where(and_(Topic.id == topic_id, Topic.user_id == user_id))
    )
    return {"success": True, "message": "Topic deleted"}


# ── Comment update/delete ───────────────────────────────────────────


@router.put("/{task_id}/comments/{comment_id}")
async def update_comment(
    task_id: str,
    comment_id: str,
    body: UpdateCommentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update a task comment."""
    comment = (await session.execute(
        select(TaskComment).where(and_(
            TaskComment.id == comment_id,
            TaskComment.task_id == task_id,
            TaskComment.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "Comment not found")
    await session.execute(
        update(TaskComment).where(TaskComment.id == comment_id).values(
            content=body.content, updated_at=_now()
        )
    )
    return {"success": True, "message": "Comment updated"}


@router.delete("/{task_id}/comments/{comment_id}")
async def delete_comment(
    task_id: str,
    comment_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a task comment."""
    result = await session.execute(
        delete(TaskComment).where(and_(
            TaskComment.id == comment_id,
            TaskComment.task_id == task_id,
            TaskComment.user_id == user_id,
        ))
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Comment not found")
    return {"success": True, "message": "Comment deleted"}


# ── Detail (aggregated task view) ─────────────────────────────────


@router.get("/{task_id}/detail")
async def get_task_detail(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get full task detail with subtasks, dependencies, topics, briefs, comments, etc."""
    svc = TaskService(session, user_id)
    task = await svc.resolve(task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    # Auto-detect heartbeat timeout for running tasks
    if task.status == "running" and task.heartbeat_timeout and task.last_heartbeat_at:
        elapsed = (_now() - task.last_heartbeat_at).total_seconds()
        if elapsed > task.heartbeat_timeout:
            await session.execute(
                update(Task).where(Task.id == task.id).values(
                    status="paused", error="Heartbeat timeout", updated_at=_now()
                )
            )
            await session.execute(
                update(TaskTopic).where(and_(
                    TaskTopic.task_id == task.id,
                    TaskTopic.status == "running",
                )).values(status="timeout", updated_at=_now())
            )
            await session.commit()
            task = await svc.resolve(task_id)
            if not task:
                raise HTTPException(404, "Task not found")

    # Clear stale heartbeat error
    if task.status != "running" and task.error == "Heartbeat timeout":
        await session.execute(
            update(Task).where(Task.id == task.id).values(error=None, updated_at=_now())
        )
        await session.commit()
        task = await svc.resolve(task_id)
        if not task:
            raise HTTPException(404, "Task not found")

    # Fetch all descendants (subtasks recursively)
    all_descendants = await _find_all_descendants(session, user_id, task.id)

    # Fetch dependencies, topics, briefs, comments
    deps = (await session.execute(
        select(TaskDependency).where(and_(
            TaskDependency.task_id == task.id,
            TaskDependency.user_id == user_id,
        ))
    )).scalars().all()

    topics = (await session.execute(
        select(TaskTopic).where(and_(
            TaskTopic.task_id == task.id,
            TaskTopic.user_id == user_id,
        )).order_by(TaskTopic.seq)
    )).scalars().all()

    briefs = (await session.execute(
        select(Brief).where(and_(
            Brief.task_id == task.id,
            Brief.user_id == user_id,
        )).order_by(Brief.created_at)
    )).scalars().all()

    comments = (await session.execute(
        select(TaskComment).where(and_(
            TaskComment.task_id == task.id,
            TaskComment.user_id == user_id,
        )).order_by(TaskComment.created_at)
    )).scalars().all()

    pinned_docs = (await session.execute(
        select(TaskDocument).where(and_(
            TaskDocument.task_id == task.id,
            TaskDocument.user_id == user_id,
        ))
    )).scalars().all()

    # Build nested subtask tree
    children_map: dict[str, list[Any]] = {}
    for s in all_descendants:
        pid = s.parent_task_id or ""
        children_map.setdefault(pid, []).append(s)

    # Build dependency map for descendants
    desc_ids = [s.id for s in all_descendants]
    desc_dep_map: dict[str, str] = {}
    if desc_ids:
        desc_deps = (await session.execute(
            select(TaskDependency).where(TaskDependency.task_id.in_(desc_ids))
        )).scalars().all()
        id_to_ident = {s.id: s.identifier for s in all_descendants}
        for dd in desc_deps:
            dep_ident = id_to_ident.get(dd.depends_on_id)
            if dep_ident:
                desc_dep_map[dd.task_id] = dep_ident

    def _build_subtree(parent_id: str) -> list[dict[str, Any]]:
        children = children_map.get(parent_id, [])
        result = []
        for s in children:
            node: dict[str, Any] = {
                "identifier": s.identifier,
                "name": s.name,
                "status": s.status,
                "priority": s.priority,
                "automationMode": s.automation_mode,
            }
            blocked = desc_dep_map.get(s.id)
            if blocked:
                node["blockedBy"] = blocked
            if s.heartbeat_interval is not None:
                node["heartbeat"] = {"interval": s.heartbeat_interval}
            if s.schedule_pattern or s.schedule_timezone:
                node["schedule"] = {
                    "pattern": s.schedule_pattern,
                    "timezone": s.schedule_timezone,
                }
            sub = _build_subtree(s.id)
            if sub:
                node["children"] = sub
            result.append(node)
        return result

    subtasks = _build_subtree(task.id)

    # Resolve parent
    parent = None
    if task.parent_task_id:
        parent_task = (await session.execute(
            select(Task).where(and_(Task.id == task.parent_task_id, Task.created_by_user_id == user_id))
        )).scalar_one_or_none()
        if parent_task:
            parent = {"identifier": parent_task.identifier, "name": parent_task.name}

    # Resolve dependency identifiers
    dep_task_ids = list({d.depends_on_id for d in deps})
    dep_info_map: dict[str, dict[str, Any]] = {}
    if dep_task_ids:
        dep_tasks = (await session.execute(
            select(Task).where(Task.id.in_(dep_task_ids))
        )).scalars().all()
        dep_info_map = {t.id: {"identifier": t.identifier, "name": t.name} for t in dep_tasks}

    # Build activities
    _iso = lambda d: d.isoformat() if d else None  # noqa: E731
    activities: list[dict[str, Any]] = []

    # Topics
    for t in topics:
        handoff = t.handoff or {}
        activities.append({
            "type": "topic",
            "id": t.topic_id,
            "seq": t.seq,
            "status": t.status,
            "operationId": t.operation_id,
            "title": handoff.get("title") or "Untitled",
            "summary": handoff.get("summary"),
            "time": _iso(t.created_at),
        })

    # Briefs
    for b in briefs:
        activities.append({
            "type": "brief",
            "id": b.id,
            "briefType": b.type,
            "priority": b.priority,
            "title": b.title,
            "summary": b.summary,
            "taskId": b.task_id,
            "topicId": b.topic_id,
            "agentId": b.agent_id,
            "actions": b.actions,
            "artifacts": b.artifacts,
            "readAt": _iso(b.read_at),
            "resolvedAction": b.resolved_action,
            "resolvedAt": _iso(b.resolved_at),
            "resolvedComment": b.resolved_comment,
            "time": _iso(b.created_at),
        })

    # Comments
    for c in comments:
        activities.append({
            "type": "comment",
            "id": c.id,
            "content": c.content,
            "agentId": c.author_agent_id,
            "time": _iso(c.created_at),
        })

    # Sort by time ascending
    activities.sort(key=lambda a: a.get("time") or "")

    task_config = task.config or {}
    schedule_config = task_config.get("schedule", {}) or {}

    detail: dict[str, Any] = {
        "identifier": task.identifier,
        "name": task.name,
        "description": task.description,
        "instruction": task.instruction,
        "status": task.status,
        "priority": task.priority,
        "error": task.error,
        "agentId": task.assignee_agent_id,
        "userId": task.assignee_user_id,
        "automationMode": task.automation_mode,
        "config": task_config if task_config else None,
        "checkpoint": task_config.get("checkpoint"),
        "review": task_config.get("review"),
        "createdAt": _iso(task.created_at),
        "parent": parent,
        "subtasks": subtasks,
        "dependencies": [
            {
                "dependsOn": dep_info_map.get(d.depends_on_id, {}).get("identifier", d.depends_on_id),
                "name": dep_info_map.get(d.depends_on_id, {}).get("name"),
                "type": d.type,
            }
            for d in deps
        ],
        "activities": activities if activities else None,
        "topicCount": len(topics) if topics else None,
        "workspace": [
            {
                "documentId": d.document_id,
                "pinnedBy": d.pinned_by,
            }
            for d in pinned_docs
        ] if pinned_docs else None,
    }

    # Heartbeat info
    if task.heartbeat_interval or task.heartbeat_timeout or task.last_heartbeat_at:
        detail["heartbeat"] = {
            "interval": task.heartbeat_interval,
            "timeout": task.heartbeat_timeout,
            "lastAt": _iso(task.last_heartbeat_at),
        }

    # Schedule info
    if task.schedule_pattern or task.schedule_timezone or schedule_config.get("maxExecutions") is not None:
        detail["schedule"] = {
            "pattern": task.schedule_pattern,
            "timezone": task.schedule_timezone,
            "maxExecutions": schedule_config.get("maxExecutions"),
        }

    return {"data": detail, "success": True}


async def _find_all_descendants(
    session: AsyncSession, user_id: str, root_task_id: str,
) -> list[Any]:
    """Recursively find all descendant tasks."""
    result: list[Any] = []
    queue = [root_task_id]
    while queue:
        parent_id = queue.pop(0)
        children = (await session.execute(
            select(Task).where(and_(
                Task.parent_task_id == parent_id,
                Task.created_by_user_id == user_id,
            )).order_by(Task.sort_order)
        )).scalars().all()
        for child in children:
            result.append(child)
            queue.append(child.id)
    return result


# ── Clear All ───────────────────────────────────────────────────────


@router.delete("")
async def clear_all_tasks(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all tasks for the current user."""
    result = await session.execute(
        delete(Task).where(Task.created_by_user_id == user_id)
    )
    return {"success": True, "count": result.rowcount}
