"""Messages, MessagePlugins, MessagesFiles, MessageQueries, MessageQueryChunks tables.

Source: packages/database/src/schemas/message.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


# ── messages ────────────────────────────────────────────────────────────────


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="messages_client_id_user_id_unique"),
        Index("messages_user_id_idx", "user_id"),
        Index("messages_session_id_idx", "session_id"),
        Index("messages_topic_id_idx", "topic_id"),
        Index("messages_agent_id_idx", "agent_id"),
        Index("messages_parent_id_idx", "parent_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("messages"),
        primary_key=True,
        max_length=255,
    )
    # 'user' | 'assistant' | 'system' | 'tool'
    role: str = Field(nullable=False, max_length=255)
    content: Optional[str] = None
    reasoning_content: Optional[str] = None

    model: Optional[str] = None
    provider: Optional[str] = None

    # Relationships
    user_id: str = Field(foreign_key="users.id", nullable=False)
    session_id: Optional[str] = Field(default=None, foreign_key="sessions.id")
    topic_id: Optional[str] = Field(default=None, foreign_key="topics.id")
    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")
    parent_id: Optional[str] = Field(default=None, foreign_key="messages.id")
    thread_id: Optional[str] = Field(default=None, foreign_key="threads.id", index=True)

    # 'default' | 'group'
    message_group_id: Optional[str] = None

    # Tool-related
    tool_call_id: Optional[str] = None
    tools: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("tools"))

    # Metadata
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))

    # 'active' | 'deprecated'
    rag_query_id: Optional[str] = None
    search_query_id: Optional[str] = None

    # Token stats
    token_count: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_price: Optional[float] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None

    client_id: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── message_plugins ─────────────────────────────────────────────────────────


class MessagePlugin(SQLModel, table=True):
    __tablename__ = "message_plugins"
    __table_args__ = (
        Index("message_plugins_message_id_idx", "message_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        primary_key=True,
        max_length=255,
    )
    message_id: str = Field(foreign_key="messages.id", nullable=False)

    # 'default' | 'markdown' | 'standalone' | 'builtin'
    type: Optional[str] = Field(default="default", max_length=255)
    api_name: Optional[str] = None
    arguments: Optional[str] = None
    identifier: Optional[str] = None
    state: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("state"))
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))
    tool_call_id: Optional[str] = None


# ── messages_files (junction) ───────────────────────────────────────────────


class MessageFile(SQLModel, table=True):
    __tablename__ = "messages_files"
    __table_args__ = (
        Index("messages_files_message_id_idx", "message_id"),
        Index("messages_files_file_id_idx", "file_id"),
        Index("messages_files_user_id_idx", "user_id"),
    )

    message_id: str = Field(foreign_key="messages.id", primary_key=True, nullable=False)
    file_id: str = Field(foreign_key="files.id", primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── message_queries ─────────────────────────────────────────────────────────


class MessageQuery(SQLModel, table=True):
    __tablename__ = "message_queries"
    __table_args__ = (
        Index("message_queries_message_id_idx", "message_id"),
        Index("message_queries_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        primary_key=True,
        max_length=255,
    )
    message_id: str = Field(foreign_key="messages.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    rewrite_query: Optional[str] = None
    user_query: Optional[str] = None
    embeddings_id: Optional[str] = None
    rag_type: Optional[str] = None  # 'semantic' | 'fulltext' | 'hybrid'

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── message_query_chunks (junction) ─────────────────────────────────────────


class MessageQueryChunk(SQLModel, table=True):
    __tablename__ = "message_query_chunks"
    __table_args__ = (
        Index("message_query_chunks_query_id_idx", "query_id"),
        Index("message_query_chunks_chunk_id_idx", "chunk_id"),
        Index("message_query_chunks_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        primary_key=True,
        max_length=255,
    )
    query_id: str = Field(foreign_key="message_queries.id", nullable=False)
    chunk_id: str = Field(nullable=False)  # references chunks.id (uuid)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    similarity: Optional[float] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
