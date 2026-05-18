"""AgentBotProviders, AgentCronJobs, AgentDocuments tables. (Non-MVP)

Source: packages/database/src/schemas/agentBotProvider.ts, agentCronJob.ts, agentDocuments.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, id_generator, json_column


class AgentBotProvider(SQLModel, table=True):
    __tablename__ = "agent_bot_providers"
    __table_args__ = (
        UniqueConstraint("platform", "application_id", name="agent_bot_providers_platform_app_id_unique"),
        Index("agent_bot_providers_platform_idx", "platform"),
        Index("agent_bot_providers_agent_id_idx", "agent_id"),
        Index("agent_bot_providers_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    agent_id: str = Field(foreign_key="agents.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    platform: str = Field(nullable=False, max_length=50)
    application_id: str = Field(nullable=False, max_length=255)

    credentials: str | None = None
    settings: dict[str, Any] | None = Field(default=None, sa_column=json_column("settings"))

    enabled: bool = Field(default=True)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class AgentCronJob(SQLModel, table=True):
    __tablename__ = "agent_cron_jobs"
    __table_args__ = (
        Index("agent_cron_jobs_agent_id_idx", "agent_id"),
        Index("agent_cron_jobs_user_id_idx", "user_id"),
        Index("agent_cron_jobs_enabled_idx", "enabled"),
    )

    id: str = Field(
        default_factory=lambda: id_generator("agentCronJobs"),
        primary_key=True,
        max_length=255,
    )
    agent_id: str = Field(foreign_key="agents.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    name: Optional[str] = None
    description: Optional[str] = None
    schedule: str = Field(nullable=False)  # cron expression
    timezone: Optional[str] = Field(default="UTC", max_length=255)

    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))
    condition: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("condition"))

    enabled: bool = Field(default=True)

    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    total_runs: int = Field(default=0)
    total_failures: int = Field(default=0)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class AgentDocument(SQLModel, table=True):
    __tablename__ = "agent_documents"
    __table_args__ = (
        UniqueConstraint("agent_id", "document_id", "user_id", name="agent_documents_agent_document_user_unique"),
        Index("agent_documents_agent_id_idx", "agent_id"),
        Index("agent_documents_document_id_idx", "document_id"),
        Index("agent_documents_user_id_idx", "user_id"),
        Index("agent_documents_access_self_idx", "access_self"),
        Index("agent_documents_access_shared_idx", "access_shared"),
        Index("agent_documents_access_public_idx", "access_public"),
        Index("agent_documents_policy_load_idx", "policy_load"),
        Index("agent_documents_template_id_idx", "template_id"),
        Index("agent_documents_policy_load_position_idx", "policy_load_position"),
        Index("agent_documents_policy_load_format_idx", "policy_load_format"),
        Index("agent_documents_policy_load_rule_idx", "policy_load_rule"),
        Index("agent_documents_deleted_at_idx", "deleted_at"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(16), primary_key=True, max_length=255)
    agent_id: str = Field(foreign_key="agents.id", nullable=False)
    document_id: str = Field(foreign_key="documents.id", nullable=False, max_length=255)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    template_id: Optional[str] = Field(default=None, max_length=100)

    # Access control bitmasks (5-bit: delete|list|write|read|execute)
    access_self: int = Field(default=31)
    access_shared: int = Field(default=0)
    access_public: int = Field(default=0)

    # Policy load — controls context injection participation
    policy_load: str = Field(default="always", max_length=30)
    policy: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("policy"))
    policy_load_position: str = Field(default="before-first-user", max_length=50)
    policy_load_format: str = Field(default="raw", max_length=20)
    policy_load_rule: str = Field(default="always", max_length=50)

    # Soft delete
    deleted_at: Optional[datetime] = None
    deleted_by_user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    deleted_by_agent_id: Optional[str] = Field(default=None, foreign_key="agents.id")
    delete_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
