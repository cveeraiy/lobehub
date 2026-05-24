"""Messages, MessagePlugins, MessagesFiles, MessageQueries, MessageQueryChunks tables.

Source: src/database/schemas/message.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Column, ForeignKey, Index, Numeric, PrimaryKeyConstraint, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
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
        Index("messages_quota_id_idx", "quota_id"),
        Index("messages_group_id_idx", "group_id"),
        Index("messages_message_group_id_idx", "message_group_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("messages"),
        primary_key=True,
        max_length=255,
    )
    # 'user' | 'assistant' | 'system' | 'tool'
    role: str = Field(nullable=False, max_length=255)
    content: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("editor_data"))
    summary: Optional[str] = None
    reasoning: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("reasoning"))
    search: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("search"))
    reasoning_content: Optional[str] = None

    model: Optional[str] = None
    provider: Optional[str] = None
    favorite: Optional[bool] = Field(default=False, nullable=True)

    # Relationships
    user_id: str = Field(foreign_key="users.id", nullable=False)
    session_id: Optional[str] = Field(default=None, foreign_key="sessions.id")
    topic_id: Optional[str] = Field(default=None, foreign_key="topics.id")
    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")
    parent_id: Optional[str] = Field(default=None, foreign_key="messages.id")
    quota_id: Optional[str] = Field(default=None, foreign_key="messages.id")
    group_id: Optional[str] = Field(default=None, foreign_key="chat_groups.id")
    target_id: Optional[str] = None
    thread_id: Optional[str] = Field(default=None, foreign_key="threads.id", index=True)

    # 'default' | 'group'
    message_group_id: Optional[str] = Field(default=None, foreign_key="message_groups.id")

    # Tool-related
    tool_call_id: Optional[str] = None
    tools: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("tools"))

    # Metadata
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))
    trace_id: Optional[str] = None
    observation_id: Optional[str] = None

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
        UniqueConstraint("client_id", "user_id", name="message_plugins_client_id_user_id_unique"),
        Index("message_plugins_user_id_idx", "user_id"),
        Index("message_plugins_tool_call_id_idx", "tool_call_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        foreign_key="messages.id",
        primary_key=True,
        max_length=255,
    )

    # 'default' | 'markdown' | 'standalone' | 'builtin'
    type: Optional[str] = Field(default="default", max_length=255)
    intervention: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("intervention"))
    api_name: Optional[str] = None
    arguments: Optional[str] = None
    identifier: Optional[str] = None
    state: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("state"))
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))
    client_id: Optional[str] = None
    user_id: str = Field(foreign_key="users.id", nullable=False)
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


# ── message_queries ─────────────────────────────────────────────────────────


class MessageQuery(SQLModel, table=True):
    __tablename__ = "message_queries"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="message_queries_client_id_user_id_unique"),
        Index("message_queries_message_id_idx", "message_id"),
        Index("message_queries_user_id_idx", "user_id"),
        Index("message_queries_embeddings_id_idx", "embeddings_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        sa_column=Column(PG_UUID(as_uuid=False), primary_key=True),
    )
    message_id: str = Field(foreign_key="messages.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    rewrite_query: Optional[str] = None
    user_query: Optional[str] = None
    client_id: Optional[str] = None
    embeddings_id: Optional[str] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("embeddings.id")),
    )


# ── message_query_chunks (junction) ─────────────────────────────────────────


class MessageQueryChunk(SQLModel, table=True):
    __tablename__ = "message_query_chunks"
    __table_args__ = (
        PrimaryKeyConstraint("chunk_id", "id", "query_id", name="message_query_chunks_chunk_id_id_query_id_pk"),
        Index("message_query_chunks_query_id_idx", "query_id"),
        Index("message_query_chunks_chunk_id_idx", "chunk_id"),
        Index("message_query_chunks_user_id_idx", "user_id"),
        Index("message_query_chunks_message_id_idx", "id"),
    )

    id: str = Field(
        sa_column=Column("id", String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
    )
    query_id: str = Field(
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("message_queries.id"), nullable=False),
    )
    chunk_id: str = Field(
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("chunks.id"), nullable=False),
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    similarity: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(6, 5)))
