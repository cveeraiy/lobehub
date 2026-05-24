"""Agent, AgentsKnowledgeBases, AgentsFiles tables.

Source: src/database/schemas/agent.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, PrimaryKeyConstraint, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column

# ── agents ──────────────────────────────────────────────────────────────────


class Agent(SQLModel, table=True):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("slug", "user_id", name="agents_slug_user_id_unique"),
        UniqueConstraint("market_identifier", "user_id", name="agents_market_identifier_user_id_unique"),
        Index("agents_user_id_idx", "user_id"),
        Index("agents_slug_idx", "slug"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("agents"),
        primary_key=True,
        max_length=255,
    )
    slug: str = Field(nullable=False, max_length=255)

    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = Field(default=None, sa_column=json_column("tags"))
    editor_data: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("editor_data"))

    avatar: Optional[str] = None
    background_color: Optional[str] = None

    market_identifier: Optional[str] = None

    plugins: Optional[list[str]] = Field(default=None, sa_column=json_column("plugins"))

    user_id: str = Field(foreign_key="users.id", nullable=False)

    # Config
    chat_config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("chat_config"))
    model: Optional[str] = None
    provider: Optional[str] = None
    system_role: Optional[str] = None
    tts: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("tts"))

    # Behaviour
    virtual: bool = Field(default=False)
    pinned: bool = Field(default=False)
    opening_message: Optional[str] = None
    opening_questions: Optional[list[str]] = Field(default=None, sa_column=json_column("opening_questions"))

    session_group_id: Optional[str] = Field(
        default=None,
        foreign_key="session_groups.id",
    )

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── agents_knowledge_bases (junction) ───────────────────────────────────────


class AgentKnowledgeBase(SQLModel, table=True):
    __tablename__ = "agents_knowledge_bases"
    __table_args__ = (
        Index("agents_knowledge_bases_agent_id_idx", "agent_id"),
        Index("agents_knowledge_bases_knowledge_base_id_idx", "knowledge_base_id"),
        Index("agents_knowledge_bases_user_id_idx", "user_id"),
    )

    agent_id: str = Field(foreign_key="agents.id", primary_key=True, nullable=False)
    knowledge_base_id: str = Field(foreign_key="knowledge_bases.id", primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    enabled: Optional[bool] = Field(default=True, nullable=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── agents_files (junction) ─────────────────────────────────────────────────


class AgentFile(SQLModel, table=True):
    __tablename__ = "agents_files"
    __table_args__ = (
        PrimaryKeyConstraint("file_id", "agent_id", "user_id", name="agents_files_file_id_agent_id_user_id_pk"),
        Index("agents_files_agent_id_idx", "agent_id"),
        Index("agents_files_file_id_idx", "file_id"),
        Index("agents_files_user_id_idx", "user_id"),
    )

    agent_id: str = Field(foreign_key="agents.id", nullable=False)
    file_id: str = Field(foreign_key="files.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    enabled: Optional[bool] = Field(default=True, nullable=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
