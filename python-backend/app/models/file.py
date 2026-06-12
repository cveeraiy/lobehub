"""GlobalFiles, Files, Documents tables.

Source: src/database/schemas/file.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, ForeignKey, Index, PrimaryKeyConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, id_generator, json_column

# ── global_files ────────────────────────────────────────────────────────────


class GlobalFile(SQLModel, table=True):
    __tablename__ = "global_files"
    __table_args__ = (Index("global_files_creator_idx", "creator"),)

    hash_id: str = Field(primary_key=True, max_length=64)
    file_type: str = Field(nullable=False, max_length=255)
    size: int = Field(nullable=False)
    url: str = Field(nullable=False)
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=json_column("metadata"))
    creator: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── files ───────────────────────────────────────────────────────────────────


class File(SQLModel, table=True):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="files_client_id_user_id_unique"),
        Index("file_hash_idx", "file_hash"),
        Index("files_user_id_idx", "user_id"),
        Index("files_parent_id_idx", "parent_id"),
        Index("files_chunk_task_id_idx", "chunk_task_id"),
        Index("files_embedding_task_id_idx", "embedding_task_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("files"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    file_type: str = Field(nullable=False, max_length=255)
    file_hash: str | None = Field(default=None, max_length=64, foreign_key="global_files.hash_id")
    name: str = Field(nullable=False)
    size: int = Field(nullable=False)
    url: str = Field(nullable=False)
    source: str | None = None

    parent_id: str | None = Field(default=None, max_length=255, foreign_key="documents.id")
    client_id: str | None = None
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=json_column("metadata"))
    chunk_task_id: str | None = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("async_tasks.id")),
    )
    embedding_task_id: str | None = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("async_tasks.id")),
    )

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── documents ───────────────────────────────────────────────────────────────


def _random_slug() -> str:
    return "-".join(create_nanoid(4) for _ in range(3))


class Document(SQLModel, table=True):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="documents_client_id_user_id_unique"),
        Index("documents_slug_user_id_unique", "slug", "user_id", unique=True, postgresql_where=text("slug IS NOT NULL")),
        Index("documents_source_idx", "source"),
        Index("documents_file_type_idx", "file_type"),
        Index("documents_source_type_idx", "source_type"),
        Index("documents_user_id_idx", "user_id"),
        Index("documents_file_id_idx", "file_id"),
        Index("documents_parent_id_idx", "parent_id"),
        Index("documents_knowledge_base_id_idx", "knowledge_base_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("documents", 16),
        primary_key=True,
        max_length=255,
    )

    title: str | None = None
    description: str | None = None
    content: str | None = None

    file_type: str = Field(nullable=False, max_length=255)
    filename: str | None = None

    total_char_count: int = Field(nullable=False, default=0)
    total_line_count: int = Field(nullable=False, default=0)

    metadata_: dict[str, Any] | None = Field(default=None, sa_column=json_column("metadata"))
    pages: list[dict[str, Any]] | None = Field(default=None, sa_column=json_column("pages"))

    # 'file' | 'web' | 'api' | 'topic'
    source_type: str = Field(nullable=False, max_length=255)
    source: str = Field(nullable=False)

    file_id: str | None = Field(default=None, foreign_key="files.id")
    knowledge_base_id: str | None = Field(default=None, foreign_key="knowledge_bases.id")
    parent_id: str | None = Field(default=None, max_length=255, foreign_key="documents.id")

    user_id: str = Field(foreign_key="users.id", nullable=False)
    client_id: str | None = None

    editor_data: dict[str, Any] | None = Field(default=None, sa_column=json_column("editor_data"))
    slug: str | None = Field(default_factory=_random_slug, max_length=255)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── files_to_sessions (junction) ───────────────────────────────────────────


class FileSession(SQLModel, table=True):
    __tablename__ = "files_to_sessions"
    __table_args__ = (
        PrimaryKeyConstraint("file_id", "session_id", name="files_to_sessions_file_id_session_id_pk"),
        Index("files_to_sessions_user_id_idx", "user_id"),
        Index("files_to_sessions_file_id_idx", "file_id"),
        Index("files_to_sessions_session_id_idx", "session_id"),
    )

    file_id: str = Field(foreign_key="files.id", nullable=False)
    session_id: str = Field(foreign_key="sessions.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)
