"""GlobalFiles, Files, Documents tables.

Source: packages/database/src/schemas/file.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, create_nanoid, json_column


# ── global_files ────────────────────────────────────────────────────────────


class GlobalFile(SQLModel, table=True):
    __tablename__ = "global_files"
    __table_args__ = (
        Index("global_files_creator_idx", "creator"),
    )

    hash_id: str = Field(primary_key=True, max_length=64)
    file_type: str = Field(nullable=False, max_length=255)
    size: int = Field(nullable=False)
    url: str = Field(nullable=False)
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
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
    file_hash: Optional[str] = Field(default=None, max_length=64, foreign_key="global_files.hash_id")
    name: str = Field(nullable=False)
    size: int = Field(nullable=False)
    url: str = Field(nullable=False)
    source: Optional[str] = None

    parent_id: Optional[str] = Field(default=None, max_length=255, foreign_key="documents.id")
    client_id: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    chunk_task_id: Optional[str] = Field(default=None, foreign_key="async_tasks.id")
    embedding_task_id: Optional[str] = Field(default=None, foreign_key="async_tasks.id")

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

    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None

    file_type: str = Field(nullable=False, max_length=255)
    filename: Optional[str] = None

    total_char_count: int = Field(nullable=False, default=0)
    total_line_count: int = Field(nullable=False, default=0)

    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    pages: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=json_column("pages"))

    # 'file' | 'web' | 'api' | 'topic'
    source_type: str = Field(nullable=False, max_length=255)
    source: str = Field(nullable=False)

    file_id: Optional[str] = Field(default=None, foreign_key="files.id")
    knowledge_base_id: Optional[str] = Field(default=None, foreign_key="knowledge_bases.id")
    parent_id: Optional[str] = Field(default=None, max_length=255, foreign_key="documents.id")

    user_id: str = Field(foreign_key="users.id", nullable=False)
    client_id: Optional[str] = None

    editor_data: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("editor_data"))
    slug: Optional[str] = Field(default_factory=_random_slug, max_length=255)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
