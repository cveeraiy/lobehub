"""MessageGroups, MessageTts, MessageTranslates, MessageChunks tables. (Non-MVP)

Source: src/database/schemas/message.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class MessageGroup(SQLModel, table=True):
    __tablename__ = "message_groups"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="message_groups_client_id_user_id_unique"),
        Index("message_groups_user_id_idx", "user_id"),
        Index("message_groups_topic_id_idx", "topic_id"),
        Index("message_groups_type_idx", "type"),
        Index("message_groups_parent_group_id_idx", "parent_group_id"),
        Index("message_groups_parent_message_id_idx", "parent_message_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("messageGroups"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    topic_id: Optional[str] = Field(default=None, foreign_key="topics.id")

    parent_group_id: Optional[str] = Field(default=None, foreign_key="message_groups.id")
    parent_message_id: Optional[str] = Field(default=None, foreign_key="messages.id")

    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("editor_data"))
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    client_id: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class MessageTts(SQLModel, table=True):
    __tablename__ = "message_tts"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="message_tts_client_id_user_id_unique"),
        Index("message_tts_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        foreign_key="messages.id",
        primary_key=True,
        max_length=255,
    )

    content_md5: Optional[str] = None
    file_id: Optional[str] = Field(default=None, foreign_key="files.id")
    voice: Optional[str] = None
    client_id: Optional[str] = None
    user_id: str = Field(foreign_key="users.id", nullable=False)


class MessageTranslate(SQLModel, table=True):
    __tablename__ = "message_translates"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="message_translates_client_id_user_id_unique"),
        Index("message_translates_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        foreign_key="messages.id",
        primary_key=True,
        max_length=255,
    )

    content: Optional[str] = None
    from_: Optional[str] = Field(default=None, sa_column=Column("from", Text))
    to: Optional[str] = Field(default=None, sa_column=Column("to", Text))
    client_id: Optional[str] = None
    user_id: str = Field(foreign_key="users.id", nullable=False)


class MessageChunk(SQLModel, table=True):
    __tablename__ = "message_chunks"
    __table_args__ = (
        Index("message_chunks_message_id_idx", "message_id"),
        Index("message_chunks_chunk_id_idx", "chunk_id"),
    )

    message_id: str = Field(foreign_key="messages.id", primary_key=True, nullable=False)
    chunk_id: str = Field(
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("chunks.id"), primary_key=True),
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
