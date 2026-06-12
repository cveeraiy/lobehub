"""ChatGroups, ChatGroupAgents tables. (Non-MVP)

Source: src/database/schemas/chatGroup.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class ChatGroup(SQLModel, table=True):
    __tablename__ = "chat_groups"
    __table_args__ = (
        UniqueConstraint("client_id", "user_id", name="chat_groups_client_id_user_id_unique"),
        Index("chat_groups_user_id_idx", "user_id"),
        Index("chat_groups_group_id_idx", "group_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("chatGroups"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    group_id: Optional[str] = Field(default=None, foreign_key="session_groups.id")

    title: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    background_color: Optional[str] = None
    market_identifier: Optional[str] = None
    content: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("editor_data"))
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))
    client_id: Optional[str] = None
    pinned: Optional[bool] = Field(default=False, nullable=True)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class ChatGroupAgent(SQLModel, table=True):
    __tablename__ = "chat_groups_agents"
    __table_args__ = (
        Index("chat_groups_agents_user_id_idx", "user_id"),
    )

    chat_group_id: str = Field(foreign_key="chat_groups.id", primary_key=True, nullable=False)
    agent_id: str = Field(foreign_key="agents.id", primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    enabled: Optional[bool] = Field(default=True, nullable=True)
    order: Optional[int] = Field(default=0, nullable=True)
    role: Optional[str] = Field(default="participant", max_length=255)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
