"""RAG eval tables. (Non-MVP)

Source: packages/database/src/schemas/ragEvals.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, json_column, text_array_column


class RagEvalDataset(SQLModel, table=True):
    __tablename__ = "rag_eval_datasets"
    __table_args__ = (
        Index("rag_eval_datasets_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(16), primary_key=True, max_length=255)
    name: str = Field(nullable=False)
    description: Optional[str] = None

    knowledge_base_id: Optional[str] = Field(default=None, foreign_key="knowledge_bases.id")
    user_id: Optional[str] = Field(default=None, foreign_key="users.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class RagEvalDatasetRecord(SQLModel, table=True):
    __tablename__ = "rag_eval_dataset_records"
    __table_args__ = (
        Index("rag_eval_dataset_records_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(32), primary_key=True, max_length=255)
    dataset_id: str = Field(foreign_key="rag_eval_datasets.id", nullable=False)

    ideal: Optional[str] = None
    question: Optional[str] = None
    reference_files: Optional[list[str]] = Field(default=None, sa_column=text_array_column("reference_files"))
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    user_id: Optional[str] = Field(default=None, foreign_key="users.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class RagEvalEvaluation(SQLModel, table=True):
    __tablename__ = "rag_eval_evaluations"
    __table_args__ = (
        Index("rag_eval_evaluations_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(32), primary_key=True, max_length=255)
    name: str = Field(nullable=False)
    description: Optional[str] = None

    eval_records_url: Optional[str] = None
    status: Optional[str] = Field(default="pending", max_length=255)
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))

    dataset_id: str = Field(foreign_key="rag_eval_datasets.id", nullable=False)
    knowledge_base_id: Optional[str] = Field(default=None, foreign_key="knowledge_bases.id")
    language_model: Optional[str] = None
    embedding_model: Optional[str] = None

    user_id: Optional[str] = Field(default=None, foreign_key="users.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class RagEvalEvaluationRecord(SQLModel, table=True):
    __tablename__ = "rag_eval_evaluation_records"
    __table_args__ = (
        Index("rag_eval_evaluation_records_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(32), primary_key=True, max_length=255)
    question: str = Field(nullable=False)
    answer: Optional[str] = None
    context: Optional[list[str]] = Field(default=None, sa_column=text_array_column("context"))
    ideal: Optional[str] = None

    status: Optional[str] = Field(default="pending", max_length=255)
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))

    language_model: Optional[str] = None
    embedding_model: Optional[str] = None
    question_embedding_id: Optional[str] = Field(default=None, foreign_key="embeddings.id")

    duration: Optional[int] = None
    dataset_record_id: str = Field(foreign_key="rag_eval_dataset_records.id", nullable=False)
    evaluation_id: str = Field(foreign_key="rag_eval_evaluations.id", nullable=False)

    user_id: Optional[str] = Field(default=None, foreign_key="users.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
