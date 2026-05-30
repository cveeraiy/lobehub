"""User, UserSettings, UserInstalledPlugins tables.

Source: src/database/schemas/user.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, PrimaryKeyConstraint, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, json_column

# ── users ───────────────────────────────────────────────────────────────────


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="users_username_unique"),
        UniqueConstraint("email", name="users_email_unique"),
        UniqueConstraint("normalized_email", name="users_normalized_email_unique"),
        UniqueConstraint("phone", name="users_phone_unique"),
        Index("users_email_idx", "email"),
        Index("users_username_idx", "username"),
        Index("users_created_at_idx", "created_at"),
        Index("users_banned_true_created_at_idx", "created_at", postgresql_where=text("banned = true")),
    )

    id: str = Field(primary_key=True, max_length=255)
    username: str | None = None
    email: str | None = None
    normalized_email: str | None = None

    avatar: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    interests: list[str] | None = Field(default=None, sa_column=json_column("interests"))

    is_onboarded: bool | None = Field(default=False)
    agent_onboarding: dict[str, Any] | None = Field(default=None, sa_column=json_column("agent_onboarding"))
    onboarding: dict[str, Any] | None = Field(default=None, sa_column=json_column("onboarding"))
    clerk_created_at: datetime | None = None

    email_verified: bool = Field(default=False, nullable=False)
    email_verified_at: datetime | None = None

    preference: dict[str, Any] | None = Field(default=None, sa_column=json_column("preference"))
    role: str | None = None
    organization: str | None = None

    banned: bool | None = Field(default=False)
    ban_reason: str | None = None
    ban_expires: datetime | None = None
    two_factor_enabled: bool | None = Field(default=False)
    phone_number_verified: bool | None = None
    last_active_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    def __init__(self, **data: Any) -> None:
        if "is_banned" in data and "banned" not in data:
            data["banned"] = data.pop("is_banned")
        if "ban_expires_at" in data and "ban_expires" not in data:
            data["ban_expires"] = data.pop("ban_expires_at")
        if "org_id" in data and "organization" not in data:
            data["organization"] = data.pop("org_id")
        data.pop("org_role", None)
        data.pop("org_slug", None)
        super().__init__(**data)

    @property
    def is_banned(self) -> bool:
        return bool(self.banned)

    @is_banned.setter
    def is_banned(self, value: bool) -> None:
        self.banned = value

    @property
    def ban_expires_at(self) -> datetime | None:
        return self.ban_expires

    @ban_expires_at.setter
    def ban_expires_at(self, value: datetime | None) -> None:
        self.ban_expires = value

    @property
    def org_id(self) -> str | None:
        return self.organization

    @org_id.setter
    def org_id(self, value: str | None) -> None:
        self.organization = value

    @property
    def org_role(self) -> str | None:
        return None

    @property
    def org_slug(self) -> str | None:
        return self.organization


# ── user_settings ───────────────────────────────────────────────────────────


class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"
    id: str = Field(foreign_key="users.id", primary_key=True)

    tts: dict[str, Any] | None = Field(default=None, sa_column=json_column("tts"))
    hotkey: dict[str, Any] | None = Field(default=None, sa_column=json_column("hotkey"))
    key_vaults: str | None = None  # encrypted JSON string
    general: dict[str, Any] | None = Field(default=None, sa_column=json_column("general"))
    language_model: dict[str, Any] | None = Field(default=None, sa_column=json_column("language_model"))
    system_agent: dict[str, Any] | None = Field(default=None, sa_column=json_column("system_agent"))
    default_agent: dict[str, Any] | None = Field(default=None, sa_column=json_column("default_agent"))
    market: dict[str, Any] | None = Field(default=None, sa_column=json_column("market"))
    memory: dict[str, Any] | None = Field(default=None, sa_column=json_column("memory"))
    tool: dict[str, Any] | None = Field(default=None, sa_column=json_column("tool"))
    image: dict[str, Any] | None = Field(default=None, sa_column=json_column("image"))
    notification: dict[str, Any] | None = Field(default=None, sa_column=json_column("notification"))
    settings_permissions: dict[str, Any] | None = Field(default=None, sa_column=json_column("settings_permissions"))


# ── nextauth_accounts ─────────────────────────────────────────────────────


class NextAuthAccount(SQLModel, table=True):
    __tablename__ = "nextauth_accounts"
    __table_args__ = (Index("nextauth_accounts_user_id_idx", "user_id"),)

    provider: str = Field(primary_key=True, nullable=False)
    provider_account_id: str = Field(
        primary_key=True,
        nullable=False,
        sa_column_kwargs={"name": "providerAccountId"},
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    type: str = Field(nullable=False)  # 'oauth' | 'oidc' | 'email' | 'credentials' | 'webauthn'
    access_token: str | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    expires_at: int | None = None
    token_type: str | None = None
    scope: str | None = None
    session_state: str | None = None


# ── user_installed_plugins ──────────────────────────────────────────────────


class UserInstalledPlugin(SQLModel, table=True):
    __tablename__ = "user_installed_plugins"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "identifier", name="user_installed_plugins_user_id_identifier_pk"),
    )

    user_id: str = Field(foreign_key="users.id", nullable=False, primary_key=True)

    identifier: str = Field(nullable=False, primary_key=True)
    type: str = Field(default="plugin", nullable=False)
    manifest: dict[str, Any] | None = Field(default=None, sa_column=json_column("manifest"))
    settings: dict[str, Any] | None = Field(default=None, sa_column=json_column("settings"))
    custom_params: dict[str, Any] | None = Field(default=None, sa_column=json_column("custom_params"))
    source: str | None = Field(default=None, max_length=255)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})

    @property
    def id(self) -> str:
        return f"{self.user_id}:{self.identifier}"
