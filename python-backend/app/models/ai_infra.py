"""AiProviders, AiModels tables.

Source: src/database/schemas/aiInfra.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, json_column

# ── ai_providers ────────────────────────────────────────────────────────────


class AiProvider(SQLModel, table=True):
    __tablename__ = "ai_providers"
    __table_args__ = (
        Index("ai_providers_user_id_idx", "user_id"),
    )

    id: str = Field(primary_key=True, max_length=255)
    user_id: str = Field(foreign_key="users.id", primary_key=True, nullable=False)

    name: Optional[str] = None
    description: Optional[str] = None
    logo: Optional[str] = None

    enabled: Optional[bool] = Field(default=True, nullable=True)
    sort: Optional[int] = None

    # 'builtin' | 'custom'
    source: Optional[str] = Field(default="builtin", max_length=255)

    # Encrypted JSON: API keys, base URLs, etc.
    key_vaults: Optional[str] = None
    settings: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("settings"))
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))

    check_model: Optional[str] = None
    fetch_on_client: Optional[bool] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── ai_models ───────────────────────────────────────────────────────────────


class AiModel(SQLModel, table=True):
    __tablename__ = "ai_models"
    __table_args__ = (
        Index("ai_models_user_id_idx", "user_id"),
        Index("ai_models_provider_id_idx", "provider_id"),
        Index("ai_models_enabled_idx", "enabled"),
    )

    id: str = Field(primary_key=True, max_length=255)
    provider_id: str = Field(primary_key=True, max_length=255)
    user_id: str = Field(foreign_key="users.id", primary_key=True, nullable=False)

    display_name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = Field(default=None, max_length=100)
    enabled: Optional[bool] = Field(default=True, nullable=True)
    sort: Optional[int] = None

    # 'chat' | 'embedding' | 'tts' | 'stt' | 'image' | 'video'
    type: str = Field(default="chat", nullable=False, max_length=20)
    # 'builtin' | 'custom' | 'remote'
    source: Optional[str] = Field(default="builtin", max_length=255)

    abilities: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("abilities"))  # { vision, functionCall, reasoning, search, files }
    parameters: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("parameters"))  # { temperature, top_p, ... }
    config: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("config"))
    settings: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("settings"))
    pricing: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("pricing"))

    context_window_tokens: Optional[int] = None
    released_at: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
