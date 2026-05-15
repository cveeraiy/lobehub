"""User, UserSettings, UserInstalledPlugins tables.

Source: packages/database/src/schemas/user.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, json_column


# ── users ───────────────────────────────────────────────────────────────────


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        Index("users_created_at_idx", "created_at"),
    )

    id: str = Field(primary_key=True, max_length=255)
    username: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)

    avatar: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    is_onboarded: bool = Field(default=False)
    # 'user' | 'admin'
    clerk_created_at: Optional[datetime] = None
    key: Optional[str] = Field(default=None, max_length=255)
    terminal_color: Optional[str] = None

    preference: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("preference"))

    # Organization fields
    org_id: Optional[str] = None
    org_role: Optional[str] = None
    org_slug: Optional[str] = None

    # Ban info
    is_banned: bool = Field(default=False)
    ban_expires_at: Optional[datetime] = None
    ban_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── user_settings ───────────────────────────────────────────────────────────


class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="user_settings_user_id_unique"),
    )

    id: str = Field(
        default_factory=lambda: create_nanoid(8),
        primary_key=True,
        max_length=255,
    )
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)

    general: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("general"))
    default_agent: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("default_agent"))
    key_vaults: Optional[str] = None  # encrypted JSON string
    language_model: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("language_model"))
    system_agent: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("system_agent"))
    tool: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("tool"))
    tts: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("tts"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── user_installed_plugins ──────────────────────────────────────────────────


class UserInstalledPlugin(SQLModel, table=True):
    __tablename__ = "user_installed_plugins"
    __table_args__ = (
        UniqueConstraint("user_id", "identifier", name="user_installed_plugins_user_id_identifier_unique"),
        Index("user_installed_plugins_user_id_idx", "user_id"),
    )

    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    identifier: str = Field(nullable=False, max_length=255)
    type: Optional[str] = Field(default="plugin", max_length=255)
    manifest: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("manifest"))
    settings: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("settings"))
    custom_params: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("custom_params"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
