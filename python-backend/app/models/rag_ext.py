"""UnstructuredChunks table. (Non-MVP)

Source: packages/database/src/schemas/rag.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, json_column


class UnstructuredChunk(SQLModel, table=True):
    __tablename__ = "unstructured_chunks"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="unstructured_chunks_client_id_user_id_unique"),
        Index("unstructured_chunks_user_id_idx", "user_id"),
        Index("unstructured_chunks_composite_id_idx", "composite_id"),
        Index("unstructured_chunks_file_id_idx", "file_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        primary_key=True,
        max_length=255,
    )
    text: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    index: Optional[int] = None
    type: Optional[str] = Field(default=None, max_length=255)

    parent_id: Optional[str] = Field(default=None, max_length=255)
    composite_id: Optional[str] = Field(default=None, foreign_key="chunks.id")
    client_id: Optional[str] = None
    user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    file_id: Optional[str] = Field(default=None, foreign_key="files.id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": sa_text("now()")})
