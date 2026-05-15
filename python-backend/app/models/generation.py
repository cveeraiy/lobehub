"""GenerationTopics, GenerationBatches, Generations tables. (Non-MVP)

Source: packages/database/src/schemas/generation.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class GenerationTopic(SQLModel, table=True):
    __tablename__ = "generation_topics"
    __table_args__ = (
        Index("generation_topics_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("generationTopics"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    title: Optional[str] = None
    favorite: bool = Field(default=False)
    # 'text2image' | 'image2image' | 'image2video' | 'text2video'
    type: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class GenerationBatch(SQLModel, table=True):
    __tablename__ = "generation_batches"
    __table_args__ = (
        Index("generation_batches_user_id_idx", "user_id"),
        Index("generation_batches_topic_id_idx", "topic_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("generationBatches"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    topic_id: Optional[str] = Field(default=None, foreign_key="generation_topics.id")

    model: Optional[str] = None
    provider: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    params: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("params"))

    async_task_id: Optional[str] = Field(default=None, foreign_key="async_tasks.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class Generation(SQLModel, table=True):
    __tablename__ = "generations"
    __table_args__ = (
        Index("generations_user_id_idx", "user_id"),
        Index("generations_batch_id_idx", "batch_id"),
        Index("generations_topic_id_idx", "topic_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("generations"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    batch_id: Optional[str] = Field(default=None, foreign_key="generation_batches.id")
    topic_id: Optional[str] = Field(default=None, foreign_key="generation_topics.id")

    # 'text2image' | 'image2image' | 'image2video' | 'text2video'
    type: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    prompt: Optional[str] = None

    file_id: Optional[str] = Field(default=None, foreign_key="files.id")
    duration: Optional[int] = None
    seed: Optional[int] = None
    params: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("params"))

    # 'pending' | 'processing' | 'success' | 'failed'
    status: Optional[str] = Field(default="pending")
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
