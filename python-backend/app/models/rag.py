"""Chunks, Embeddings, DocumentChunks tables.

Source: packages/database/src/schemas/rag.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, Index, UniqueConstraint
from sqlalchemy import text as sa_text
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
        primary_key=True,
        max_length=255,
    )
    text: Optional[str] = None
    abstract: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    index: Optional[int] = None
    type: Optional[str] = Field(default=None, max_length=255)

    client_id: Optional[str] = None
    user_id: Optional[str] = Field(default=None, foreign_key="users.id")

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
        primary_key=True,
        max_length=255,
    )
    chunk_id: Optional[str] = Field(default=None, foreign_key="chunks.id", sa_column_kwargs={"unique": True})

    embeddings: Optional[list[float]] = Field(
        default=None,
        sa_column=Column("embeddings", VectorType(1024)),
    )
    model: Optional[str] = None
    client_id: Optional[str] = None
    user_id: Optional[str] = Field(default=None, foreign_key="users.id")


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
    chunk_id: str = Field(
        foreign_key="chunks.id",
        primary_key=True,
        nullable=False,
    )
    page_index: Optional[int] = None
    user_id: str = Field(foreign_key="users.id", nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})
