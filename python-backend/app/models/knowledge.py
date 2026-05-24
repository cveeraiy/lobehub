"""KnowledgeBases, KnowledgeBaseFiles tables.

Source: src/database/schemas/file.ts (knowledge_bases, knowledge_base_files)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column

# ── knowledge_bases ─────────────────────────────────────────────────────────


class KnowledgeBase(SQLModel, table=True):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="knowledge_bases_client_id_user_id_unique"),
        Index("knowledge_bases_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("knowledgeBases"),
        primary_key=True,
        max_length=255,
    )
    name: str = Field(nullable=False)
    description: Optional[str] = None
    avatar: Optional[str] = None
    type: Optional[str] = None

    user_id: str = Field(foreign_key="users.id", nullable=False)
    client_id: Optional[str] = None

    is_public: Optional[bool] = Field(default=False, nullable=True)
    settings: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("settings"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── knowledge_base_files (junction) ─────────────────────────────────────────


class KnowledgeBaseFile(SQLModel, table=True):
    __tablename__ = "knowledge_base_files"
    __table_args__ = (
        Index("knowledge_base_files_kb_id_idx", "knowledge_base_id"),
        Index("knowledge_base_files_user_id_idx", "user_id"),
        Index("knowledge_base_files_file_id_idx", "file_id"),
    )

    knowledge_base_id: str = Field(
        foreign_key="knowledge_bases.id",
        primary_key=True,
        nullable=False,
    )
    file_id: str = Field(
        foreign_key="files.id",
        primary_key=True,
        nullable=False,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
