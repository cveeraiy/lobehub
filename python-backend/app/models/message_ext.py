"""MessageGroups, MessageTts, MessageTranslates, MessageChunks tables. (Non-MVP)

Source: packages/database/src/schemas/message.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class MessageGroup(SQLModel, table=True):
    __tablename__ = "message_groups"
    __table_args__ = (
        Index("message_groups_user_id_idx", "user_id"),
        Index("message_groups_session_id_idx", "session_id"),
        Index("message_groups_topic_id_idx", "topic_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("messageGroups"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    session_id: Optional[str] = Field(default=None, foreign_key="sessions.id")
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
        Index("message_tts_message_id_idx", "message_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        primary_key=True,
        max_length=255,
    )
    message_id: str = Field(foreign_key="messages.id", nullable=False)

    content_md5: Optional[str] = None
    file_id: Optional[str] = None
    voice: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class MessageTranslate(SQLModel, table=True):
    __tablename__ = "message_translates"
    __table_args__ = (
        Index("message_translates_message_id_idx", "message_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        primary_key=True,
        max_length=255,
    )
    message_id: str = Field(foreign_key="messages.id", nullable=False)

    content: Optional[str] = None
    from_lang: Optional[str] = None
    to_lang: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class MessageChunk(SQLModel, table=True):
    __tablename__ = "message_chunks"
    __table_args__ = (
        Index("message_chunks_message_id_idx", "message_id"),
        Index("message_chunks_chunk_id_idx", "chunk_id"),
    )

    message_id: str = Field(foreign_key="messages.id", primary_key=True, nullable=False)
    chunk_id: str = Field(foreign_key="chunks.id", primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
