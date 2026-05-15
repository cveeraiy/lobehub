"""ChatGroups, ChatGroupAgents tables. (Non-MVP)

Source: packages/database/src/schemas/chatGroup.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class ChatGroup(SQLModel, table=True):
    __tablename__ = "chat_groups"
    __table_args__ = (
        Index("chat_groups_user_id_idx", "user_id"),
        Index("chat_groups_session_id_idx", "session_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("chatGroups"),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    session_id: Optional[str] = Field(default=None, foreign_key="sessions.id")

    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class ChatGroupAgent(SQLModel, table=True):
    __tablename__ = "chat_groups_agents"
    __table_args__ = (
        Index("chat_groups_agents_group_id_idx", "group_id"),
        Index("chat_groups_agents_agent_id_idx", "agent_id"),
    )

    group_id: str = Field(foreign_key="chat_groups.id", primary_key=True, nullable=False)
    agent_id: str = Field(foreign_key="agents.id", primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    # 'main' | 'participant'
    role: Optional[str] = Field(default="participant", max_length=255)
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
