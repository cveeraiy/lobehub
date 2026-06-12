"""Chunks, Embeddings, DocumentChunks tables.

Source: src/database/schemas/rag.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, ForeignKey, Index, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

from app.models._helpers import VectorType, _utcnow, json_column

# ── chunks ──────────────────────────────────────────────────────────────────


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="chunks_client_id_user_id_unique"),
        Index("chunks_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        sa_column=Column(PG_UUID(as_uuid=False), primary_key=True),
    )
    text: str | None = None
    abstract: str | None = None
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=json_column("metadata"))
    index: int | None = None
    type: str | None = Field(default=None, max_length=255)

    client_id: str | None = None
    user_id: str | None = Field(default=None, foreign_key="users.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})


# ── embeddings ──────────────────────────────────────────────────────────────


class Embedding(SQLModel, table=True):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="embeddings_client_id_user_id_unique"),
        Index("embeddings_chunk_id_idx", "chunk_id"),
        Index("embeddings_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        sa_column=Column(PG_UUID(as_uuid=False), primary_key=True),
    )
    chunk_id: str | None = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("chunks.id"), unique=True),
    )

    embeddings: list[float] | None = Field(
        default=None,
        sa_column=Column("embeddings", VectorType(1024)),
    )
    model: str | None = None
    client_id: str | None = None
    user_id: str | None = Field(default=None, foreign_key="users.id")


# ── document_chunks (junction) ──────────────────────────────────────────────


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("document_chunks_document_id_idx", "document_id"),
        Index("document_chunks_chunk_id_idx", "chunk_id"),
        Index("document_chunks_user_id_idx", "user_id"),
    )

    document_id: str = Field(
        foreign_key="documents.id",
        primary_key=True,
        nullable=False,
        max_length=30,
    )
    chunk_id: str = Field(sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("chunks.id"), primary_key=True))
    page_index: int | None = None
    user_id: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})


# ── file_chunks (junction) ─────────────────────────────────────────────────


class FileChunk(SQLModel, table=True):
    __tablename__ = "file_chunks"
    __table_args__ = (
        PrimaryKeyConstraint("file_id", "chunk_id", name="file_chunks_file_id_chunk_id_pk"),
        Index("file_chunks_user_id_idx", "user_id"),
        Index("file_chunks_file_id_idx", "file_id"),
        Index("file_chunks_chunk_id_idx", "chunk_id"),
    )

    file_id: str = Field(foreign_key="files.id", nullable=False)
    chunk_id: str = Field(
        sa_column=Column(PG_UUID(as_uuid=False), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False),
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})
