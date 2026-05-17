"""Threads, TopicDocuments, TopicShares tables. (Non-MVP)

Source: packages/database/src/schemas/topic.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class Thread(SQLModel, table=True):
    __tablename__ = "threads"
    __table_args__ = (
        Index("threads_topic_id_idx", "topic_id"),
        Index("threads_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("threads"),
        primary_key=True,
        max_length=255,
    )
    topic_id: str = Field(foreign_key="topics.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    title: Optional[str] = None
    source_message_id: Optional[str] = Field(default=None, foreign_key="messages.id")
    # 'standalone' | 'continuation' | 'isolation' | 'eval'
    type: Optional[str] = Field(default="standalone", max_length=255)
    status: Optional[str] = Field(default=None, max_length=255)

    parent_thread_id: Optional[str] = Field(default=None, foreign_key="threads.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class TopicDocument(SQLModel, table=True):
    __tablename__ = "topic_documents"
    __table_args__ = (
        Index("topic_documents_topic_id_idx", "topic_id"),
        Index("topic_documents_document_id_idx", "document_id"),
    )

    topic_id: str = Field(foreign_key="topics.id", primary_key=True, nullable=False)
    document_id: str = Field(foreign_key="documents.id", primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class TopicShare(SQLModel, table=True):
    __tablename__ = "topic_shares"
    __table_args__ = (
        UniqueConstraint("topic_id", "user_id", name="topic_shares_topic_id_user_id_unique"),
        Index("topic_shares_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        primary_key=True,
        max_length=255,
    )
    topic_id: str = Field(foreign_key="topics.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    is_public: bool = Field(default=True)
    password_hash: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    expires_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
