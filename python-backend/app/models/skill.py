"""AgentSkills table.

Source: packages/database/src/schemas/agentSkill.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, id_generator, json_column


class AgentSkill(SQLModel, table=True):
    __tablename__ = "agent_skills"
    __table_args__ = (
        UniqueConstraint("identifier", "user_id", name="agent_skills_identifier_user_id_unique"),
        Index("agent_skills_user_id_idx", "user_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("agentSkills"),
        primary_key=True,
        max_length=255,
    )
    identifier: str = Field(nullable=False, max_length=255)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    display_name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None

    manifest: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("manifest"))
    resources: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("resources"))
    file_id: Optional[str] = Field(default=None, foreign_key="global_files.hash_id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
