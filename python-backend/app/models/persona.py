"""UserPersonaDocuments, UserPersonaDocumentHistories tables. (Non-MVP)

Canonical database model for user persona documents.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, json_column


class UserPersonaDocument(SQLModel, table=True):
    __tablename__ = "user_memory_persona_documents"
    __table_args__ = (
        UniqueConstraint("user_id", "profile", name="user_persona_documents_user_id_profile_unique"),
        Index("user_persona_documents_user_id_index", "user_id"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(18), primary_key=True, max_length=255)
    user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    profile: str = Field(default="default", max_length=255)

    tagline: Optional[str] = None
    persona: Optional[str] = None

    memory_ids: Optional[list[str]] = Field(default=None, sa_column=json_column("memory_ids"))
    source_ids: Optional[list[str]] = Field(default=None, sa_column=json_column("source_ids"))
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    version: int = Field(default=1)
    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class UserPersonaDocumentHistory(SQLModel, table=True):
    __tablename__ = "user_memory_persona_document_histories"
    __table_args__ = (
        Index("user_persona_document_histories_persona_id_index", "persona_id"),
        Index("user_persona_document_histories_user_id_index", "user_id"),
        Index("user_persona_document_histories_profile_index", "profile"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(18), primary_key=True, max_length=255)
    user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    persona_id: Optional[str] = Field(
        default=None,
        max_length=255,
        foreign_key="user_memory_persona_documents.id",
    )
    profile: str = Field(default="default", max_length=255)

    snapshot_persona: Optional[str] = None
    snapshot_tagline: Optional[str] = None
    reasoning: Optional[str] = None
    diff_persona: Optional[str] = None
    diff_tagline: Optional[str] = None
    snapshot: Optional[str] = None
    summary: Optional[str] = None
    # 'agent' | 'user'
    edited_by: Optional[str] = Field(default="agent", max_length=255)

    memory_ids: Optional[list[str]] = Field(default=None, sa_column=json_column("memory_ids"))
    source_ids: Optional[list[str]] = Field(default=None, sa_column=json_column("source_ids"))
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    previous_version: Optional[int] = None
    next_version: Optional[int] = None

    captured_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
