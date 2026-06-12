"""Agent eval tables: benchmarks, datasets, test_cases, runs, run_topics. (Non-MVP)

Source: src/database/schemas/agentEvals.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, create_nanoid, json_column


class AgentEvalBenchmark(SQLModel, table=True):
    __tablename__ = "agent_eval_benchmarks"
    __table_args__ = (
        Index("agent_eval_benchmarks_user_id_idx", "user_id"),
        Index("agent_eval_benchmarks_agent_id_idx", "agent_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("evalBenchmarks"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    agent_id: str = Field(foreign_key="agents.id", nullable=False)

    name: str = Field(nullable=False)
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class AgentEvalDataset(SQLModel, table=True):
    __tablename__ = "agent_eval_datasets"
    __table_args__ = (
        Index("agent_eval_datasets_user_id_idx", "user_id"),
        Index("agent_eval_datasets_benchmark_id_idx", "benchmark_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("evalDatasets"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    benchmark_id: str = Field(foreign_key="agent_eval_benchmarks.id", nullable=False)

    name: str = Field(nullable=False)
    description: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class AgentEvalTestCase(SQLModel, table=True):
    __tablename__ = "agent_eval_test_cases"
    __table_args__ = (
        Index("agent_eval_test_cases_user_id_idx", "user_id"),
        Index("agent_eval_test_cases_dataset_id_idx", "dataset_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("evalTestCases"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    dataset_id: str = Field(foreign_key="agent_eval_datasets.id", nullable=False)

    input: str = Field(nullable=False)
    expected_output: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class AgentEvalRun(SQLModel, table=True):
    __tablename__ = "agent_eval_runs"
    __table_args__ = (
        Index("agent_eval_runs_user_id_idx", "user_id"),
        Index("agent_eval_runs_benchmark_id_idx", "benchmark_id"),
        Index("agent_eval_runs_status_idx", "status"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("evalRuns"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    benchmark_id: str = Field(foreign_key="agent_eval_benchmarks.id", nullable=False)
    dataset_id: Optional[str] = Field(default=None, foreign_key="agent_eval_datasets.id")

    # 'pending' | 'running' | 'completed' | 'failed' | 'canceled'
    status: str = Field(default="pending")
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))
    results: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("results"))
    error: Optional[str] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class AgentEvalRunTopic(SQLModel, table=True):
    __tablename__ = "agent_eval_run_topics"
    __table_args__ = (
        Index("agent_eval_run_topics_run_id_idx", "run_id"),
        Index("agent_eval_run_topics_topic_id_idx", "topic_id"),
    )

    id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True, max_length=255)
    run_id: str = Field(foreign_key="agent_eval_runs.id", nullable=False)
    topic_id: Optional[str] = Field(default=None, foreign_key="topics.id")
    test_case_id: Optional[str] = Field(default=None, foreign_key="agent_eval_test_cases.id")

    # 'pending' | 'running' | 'completed' | 'failed'
    status: str = Field(default="pending")
    score: Optional[float] = None
    result: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("result"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
