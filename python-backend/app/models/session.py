"""Sessions and SessionGroups tables.

Source: src/database/schemas/session.ts
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, id_generator


def _random_slug() -> str:
    return "-".join(create_nanoid(4) for _ in range(3))


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
    sort: int | None = None
    client_id: str | None = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── sessions ────────────────────────────────────────────────────────────────


class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="sessions_client_id_user_id_unique"),
        UniqueConstraint("slug", "user_id", name="slug_user_id_unique"),
        Index("sessions_user_id_idx", "user_id"),
        Index("sessions_id_user_id_idx", "id", "user_id"),
        Index("sessions_user_id_updated_at_idx", "user_id", "updated_at"),
        Index("sessions_agent_id_idx", "agent_id"),
        Index("sessions_group_id_idx", "group_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("sessions"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    slug: str = Field(default_factory=_random_slug, nullable=False, max_length=100)
    title: str | None = None
    description: str | None = None
    avatar: str | None = None
    background_color: str | None = None

    agent_id: str | None = Field(default=None, foreign_key="agents.id")
    group_id: str | None = Field(default=None, foreign_key="session_groups.id")

    # 'agent' | 'group' etc.
    type: str | None = Field(default="agent", max_length=255)

    pinned: bool | None = Field(default=False)
    client_id: str | None = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
