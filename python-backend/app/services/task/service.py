"""TaskService — CRUD and status transitions for tasks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Brief, Task, TaskComment, TaskDependency, TaskDocument, TaskTopic

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({"canceled", "completed", "failed"})


class TaskService:
    """Thin service wrapping task table operations."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id

    # ── Read ─────────────────────────────────────────────────────────

    async def find_by_id(self, task_id: str) -> Task | None:
        stmt = select(Task).where(Task.id == task_id, Task.created_by_user_id == self._uid)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def resolve(self, id_or_identifier: str) -> Task | None:
        """Look up by ID first, then by identifier."""
        task = await self.find_by_id(id_or_identifier)
        if task:
            return task
        stmt = select(Task).where(
            Task.identifier == id_or_identifier,
            Task.created_by_user_id == self._uid,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_tasks(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Task]:
        stmt = select(Task).where(Task.created_by_user_id == self._uid)
        if status:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(min(limit, 200))
        return (await self._db.execute(stmt)).scalars().all()

    async def find_subtasks(self, task_id: str) -> Sequence[Task]:
        stmt = (
            select(Task)
            .where(Task.parent_task_id == task_id, Task.created_by_user_id == self._uid)
            .order_by(Task.sort_order)
        )
        return (await self._db.execute(stmt)).scalars().all()

    # ── Write ────────────────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> Task:
        task = Task(created_by_user_id=self._uid, **kwargs)
        self._db.add(task)
        await self._db.flush()
        return task

    async def update_fields(self, task_id: str, **fields: Any) -> None:
        fields["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.execute(
            update(Task)
            .where(Task.id == task_id, Task.created_by_user_id == self._uid)
            .values(**fields)
        )

    async def update_status(
        self,
        task_id: str,
        status: str,
        *,
        error: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        fields: dict[str, Any] = {"status": status, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}
        if error is not None:
            fields["error"] = error
        if started_at is not None:
            fields["started_at"] = started_at
        if completed_at is not None:
            fields["completed_at"] = completed_at
        await self._db.execute(
            update(Task)
            .where(Task.id == task_id, Task.created_by_user_id == self._uid)
            .values(**fields)
        )

    async def update_heartbeat(self, task_id: str) -> None:
        await self._db.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(last_heartbeat_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )

    async def update_current_topic(self, task_id: str, topic_id: str) -> None:
        await self.update_fields(task_id, current_topic_id=topic_id)

    async def increment_topic_count(self, task_id: str) -> None:
        await self._db.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(total_topics=func.coalesce(Task.total_topics, 0) + 1)
        )

    async def delete_task(self, task_id: str) -> None:
        await self._db.execute(
            delete(Task).where(Task.id == task_id, Task.created_by_user_id == self._uid)
        )

    # ── TaskTopic helpers ────────────────────────────────────────────

    async def find_topics(self, task_id: str) -> Sequence[TaskTopic]:
        stmt = (
            select(TaskTopic)
            .where(TaskTopic.task_id == task_id, TaskTopic.user_id == self._uid)
            .order_by(TaskTopic.seq)
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def add_topic(
        self,
        task_id: str,
        topic_id: str,
        *,
        seq: int,
        operation_id: str | None = None,
    ) -> TaskTopic:
        tt = TaskTopic(
            task_id=task_id,
            topic_id=topic_id,
            user_id=self._uid,
            seq=seq,
            operation_id=operation_id,
        )
        self._db.add(tt)
        await self._db.flush()
        return tt

    async def update_topic_status(
        self, task_id: str, topic_id: str, status: str
    ) -> None:
        await self._db.execute(
            update(TaskTopic)
            .where(
                TaskTopic.task_id == task_id,
                TaskTopic.topic_id == topic_id,
                TaskTopic.user_id == self._uid,
            )
            .values(status=status, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )

    async def timeout_running_topics(self, task_id: str) -> None:
        await self._db.execute(
            update(TaskTopic)
            .where(TaskTopic.task_id == task_id, TaskTopic.status == "running")
            .values(status="timeout", updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )

    # ── Brief helpers ────────────────────────────────────────────────

    async def find_briefs(self, task_id: str) -> Sequence[Brief]:
        stmt = (
            select(Brief)
            .where(Brief.task_id == task_id, Brief.user_id == self._uid)
            .order_by(Brief.created_at.desc())
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def create_brief(self, **kwargs: Any) -> Brief:
        brief = Brief(user_id=self._uid, **kwargs)
        self._db.add(brief)
        await self._db.flush()
        return brief

    # ── Comment helpers ──────────────────────────────────────────────

    async def get_comments(self, task_id: str) -> Sequence[TaskComment]:
        stmt = (
            select(TaskComment)
            .where(TaskComment.task_id == task_id, TaskComment.user_id == self._uid)
            .order_by(TaskComment.created_at)
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def add_comment(self, **kwargs: Any) -> TaskComment:
        comment = TaskComment(user_id=self._uid, **kwargs)
        self._db.add(comment)
        await self._db.flush()
        return comment

    # ── Dependencies helpers ─────────────────────────────────────────

    async def get_dependencies(self, task_id: str) -> Sequence[TaskDependency]:
        stmt = select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.user_id == self._uid,
        )
        return (await self._db.execute(stmt)).scalars().all()
