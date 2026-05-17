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
        Index("agent_skills_visibility_idx", "visibility"),
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

    # Access control: 'private' (owner only), 'public' (all users), 'restricted' (explicit shares)
    visibility: str = Field(default="private", max_length=20)

    manifest: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("manifest"))
    resources: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("resources"))
    file_id: Optional[str] = Field(default=None, foreign_key="global_files.hash_id")

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class AgentSkillShare(SQLModel, table=True):
    """Junction table for restricted skill sharing between users."""
    __tablename__ = "agent_skill_shares"
    __table_args__ = (
        UniqueConstraint("skill_id", "shared_with_user_id", name="agent_skill_shares_unique"),
        Index("agent_skill_shares_skill_idx", "skill_id"),
        Index("agent_skill_shares_user_idx", "shared_with_user_id"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("agentSkills"),
        primary_key=True,
        max_length=255,
    )
    skill_id: str = Field(
        foreign_key="agent_skills.id",
        max_length=255,
        nullable=False,
    )
    shared_with_user_id: str = Field(
        foreign_key="users.id",
        nullable=False,
    )
    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
