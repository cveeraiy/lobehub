"""Sessions and SessionGroups tables.

Source: packages/database/src/schemas/session.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator


# ── session_groups ──────────────────────────────────────────────────────────


class SessionGroup(SQLModel, table=True):
    __tablename__ = "session_groups"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="session_groups_client_id_user_id_unique"),
        Index("session_groups_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("sessionGroups"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    name: str = Field(nullable=False)
    sort: Optional[int] = None
    client_id: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── sessions ────────────────────────────────────────────────────────────────


class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="sessions_client_id_user_id_unique"),
        Index("sessions_user_id_idx", "user_id"),
        Index("sessions_agent_id_idx", "agent_id"),
        Index("sessions_group_id_idx", "group_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("sessions"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")
    group_id: Optional[str] = Field(default=None, foreign_key="session_groups.id")

    # 'agent' | 'group' etc.
    type: Optional[str] = Field(default="agent", max_length=255)

    pinned: bool = Field(default=False)
    slug: Optional[str] = Field(default=None, max_length=255)
    client_id: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
