"""Tasks, TaskDependencies, TaskDocuments, TaskTopics, Briefs, TaskComments tables. (Non-MVP)

Source: packages/database/src/schemas/task.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, create_nanoid, json_column


class Task(SQLModel, table=True):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("identifier", "created_by_user_id", name="tasks_identifier_idx"),
        Index("tasks_created_by_user_id_idx", "created_by_user_id"),
        Index("tasks_created_by_agent_id_idx", "created_by_agent_id"),
        Index("tasks_assignee_user_id_idx", "assignee_user_id"),
        Index("tasks_assignee_agent_id_idx", "assignee_agent_id"),
        Index("tasks_parent_task_id_idx", "parent_task_id"),
        Index("tasks_status_idx", "status"),
        Index("tasks_priority_idx", "priority"),
        Index("tasks_automation_mode_idx", "automation_mode"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("tasks"),
        primary_key=True,
        max_length=255,
    )
    identifier: str = Field(nullable=False)
    seq: int = Field(nullable=False)

    created_by_user_id: str = Field(foreign_key="users.id", nullable=False)
    created_by_agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")

    assignee_user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    assignee_agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")

    parent_task_id: Optional[str] = Field(default=None, foreign_key="tasks.id")

    name: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=255)
    instruction: str = Field(nullable=False)

    # 'backlog' | 'running' | 'paused' | 'completed' | 'failed' | 'canceled'
    status: str = Field(default="backlog")
    priority: Optional[int] = Field(default=0)
    sort_order: Optional[int] = Field(default=0)

    # 'heartbeat' | 'schedule'
    automation_mode: Optional[str] = None

    heartbeat_interval: Optional[int] = None
    heartbeat_timeout: Optional[int] = None
    last_heartbeat_at: Optional[datetime] = None

    schedule_pattern: Optional[str] = None
    schedule_timezone: Optional[str] = Field(default="UTC")

    total_topics: Optional[int] = Field(default=0)
    max_topics: Optional[int] = None
    current_topic_id: Optional[str] = Field(default=None, foreign_key="topics.id")

    context: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("context"))
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))
    error: Optional[str] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class TaskDependency(SQLModel, table=True):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_id", name="task_deps_unique_idx"),
        Index("task_deps_task_id_idx", "task_id"),
        Index("task_deps_depends_on_id_idx", "depends_on_id"),
        Index("task_deps_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True, max_length=255)
    task_id: str = Field(foreign_key="tasks.id", nullable=False)
    depends_on_id: str = Field(foreign_key="tasks.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    # 'blocks' | 'relates'
    type: str = Field(default="blocks")
    condition: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("condition"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class TaskDocument(SQLModel, table=True):
    __tablename__ = "task_documents"
    __table_args__ = (
        UniqueConstraint("task_id", "document_id", name="task_docs_unique_idx"),
        Index("task_docs_task_id_idx", "task_id"),
        Index("task_docs_document_id_idx", "document_id"),
        Index("task_docs_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True, max_length=255)
    task_id: str = Field(foreign_key="tasks.id", nullable=False)
    document_id: str = Field(foreign_key="documents.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    # 'agent' | 'user' | 'system'
    pinned_by: str = Field(default="agent")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class TaskTopic(SQLModel, table=True):
    __tablename__ = "task_topics"
    __table_args__ = (
        UniqueConstraint("task_id", "topic_id", name="task_topics_unique_idx"),
        Index("task_topics_task_id_idx", "task_id"),
        Index("task_topics_topic_id_idx", "topic_id"),
        Index("task_topics_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True, max_length=255)
    task_id: str = Field(foreign_key="tasks.id", nullable=False)
    topic_id: Optional[str] = Field(default=None, foreign_key="topics.id")
    user_id: str = Field(foreign_key="users.id", nullable=False)

    seq: int = Field(nullable=False)
    operation_id: Optional[str] = None
    # 'running' | 'completed' | 'failed' | 'timeout' | 'canceled'
    status: str = Field(default="running")

    handoff: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("handoff"))

    review_passed: Optional[int] = None
    review_score: Optional[int] = None
    review_scores: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("review_scores"))
    review_iteration: Optional[int] = None
    reviewed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class Brief(SQLModel, table=True):
    __tablename__ = "briefs"
    __table_args__ = (
        Index("briefs_user_id_idx", "user_id"),
        Index("briefs_task_id_idx", "task_id"),
        Index("briefs_cron_job_id_idx", "cron_job_id"),
        Index("briefs_agent_id_idx", "agent_id"),
        Index("briefs_type_idx", "type"),
        Index("briefs_priority_idx", "priority"),
        Index("briefs_trigger_idx", "trigger"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("briefs"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    task_id: Optional[str] = Field(default=None, foreign_key="tasks.id")
    cron_job_id: Optional[str] = Field(default=None, foreign_key="agent_cron_jobs.id")
    topic_id: Optional[str] = None
    agent_id: Optional[str] = None

    # 'decision' | 'result' | 'insight' | 'error'
    type: str = Field(nullable=False)
    # 'urgent' | 'normal' | 'info'
    priority: Optional[str] = Field(default="info")
    title: str = Field(nullable=False)
    summary: str = Field(nullable=False)
    artifacts: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("artifacts"))
    actions: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("actions"))

    resolved_action: Optional[str] = None
    resolved_comment: Optional[str] = None
    read_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    trigger: Optional[str] = Field(default=None, max_length=255)
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class TaskComment(SQLModel, table=True):
    __tablename__ = "task_comments"
    __table_args__ = (
        Index("task_comments_task_id_idx", "task_id"),
        Index("task_comments_user_id_idx", "user_id"),
        Index("task_comments_author_user_id_idx", "author_user_id"),
        Index("task_comments_agent_id_idx", "author_agent_id"),
        Index("task_comments_brief_id_idx", "brief_id"),
        Index("task_comments_topic_id_idx", "topic_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("taskComments"),
        primary_key=True,
        max_length=255,
    )
    task_id: str = Field(foreign_key="tasks.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    author_user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    author_agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")

    content: str = Field(nullable=False)
    editor_data: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("editor_data"))

    brief_id: Optional[str] = Field(default=None, foreign_key="briefs.id")
    topic_id: Optional[str] = Field(default=None, foreign_key="topics.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
