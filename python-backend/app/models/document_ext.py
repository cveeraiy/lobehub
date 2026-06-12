"""DocumentHistories table. (Non-MVP)

Source: src/database/schemas/documentHistory.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, json_column


class DocumentHistory(SQLModel, table=True):
    __tablename__ = "document_histories"
    __table_args__ = (
        Index("document_histories_document_id_idx", "document_id"),
        Index("document_histories_user_id_idx", "user_id"),
        Index("document_histories_saved_at_idx", "saved_at"),
    )

    id: str = Field(
        default_factory=lambda: create_nanoid(18),
        primary_key=True,
        max_length=255,
    )
    document_id: str = Field(foreign_key="documents.id", nullable=False, max_length=255)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    editor_data: dict[str, Any] = Field(sa_column=json_column("editor_data", nullable=False))
    # 'autosave' | 'manual' | 'restore' | 'system' | 'llm_call'
    save_source: str = Field(nullable=False)
    saved_at: datetime = Field(nullable=False)
