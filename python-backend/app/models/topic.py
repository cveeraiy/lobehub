"""Topics table.

Source: packages/database/src/schemas/topic.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class Topic(SQLModel, table=True):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="topics_client_id_user_id_unique"),
        Index("topics_user_id_idx", "user_id"),
        Index("topics_session_id_idx", "session_id"),
        Index("topics_agent_id_idx", "agent_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("topics"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    session_id: Optional[str] = Field(default=None, foreign_key="sessions.id")
    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")

    title: Optional[str] = None
    favorite: bool = Field(default=False)

    # 'normal' | 'archived'
    status: Optional[str] = Field(default=None, max_length=255)

    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))
    history_summary: Optional[str] = None

    client_id: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
