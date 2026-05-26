"""AsyncTasks, ApiKeys, Notifications, NotificationDeliveries tables. (Non-MVP)

Source: src/database/schemas/asyncTask.ts, apiKey.ts, notification.ts
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, Index, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, json_column

# ── async_tasks ─────────────────────────────────────────────────────────────


class AsyncTask(SQLModel, table=True):
    __tablename__ = "async_tasks"
    __table_args__ = (
        Index("async_tasks_user_id_idx", "user_id"),
        Index("async_tasks_parent_id_idx", "parent_id"),
        Index("async_tasks_type_status_idx", "type", "status"),
        Index("async_tasks_inference_id_idx", "inference_id"),
    )

    id: str = Field(
        default_factory=lambda: str(_uuid.uuid4()),
        sa_column=Column(PG_UUID(as_uuid=False), primary_key=True),
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)

    # 'pending' | 'processing' | 'success' | 'error'
    status: Optional[str] = Field(default="pending", nullable=True, max_length=255)
    error: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("error"))
    inference_id: Optional[str] = None
    # 'chunk' | 'embedding' | 'other'
    type: Optional[str] = Field(default=None, max_length=255)
    parent_id: Optional[str] = Field(
        default=None,
        sa_column=Column(PG_UUID(as_uuid=False)),
    )
    duration: Optional[int] = None
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_column=json_column("metadata", nullable=False))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── api_keys ────────────────────────────────────────────────────────────────


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("api_keys_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(16), primary_key=True, max_length=255)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    name: str = Field(nullable=False, max_length=256)
    key: str = Field(nullable=False, max_length=256)
    key_hash: Optional[str] = Field(default=None, max_length=128)
    enabled: bool = Field(default=True)

    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── notifications ───────────────────────────────────────────────────────────


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("notifications_user_id_idx", "user_id"),
        Index("notifications_category_idx", "category"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(16), primary_key=True, max_length=255)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    title: str = Field(nullable=False)
    body: Optional[str] = None
    # 'system' | 'agent' | 'social' | 'billing'
    category: Optional[str] = Field(default=None, max_length=255)
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    # Deduplication
    dedup_key: Optional[str] = Field(default=None, max_length=255)

    read_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


# ── notification_deliveries ─────────────────────────────────────────────────


class NotificationDelivery(SQLModel, table=True):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        Index("notification_deliveries_notification_id_idx", "notification_id"),
        Index("notification_deliveries_user_id_idx", "user_id"),
    )

    id: str = Field(default_factory=lambda: create_nanoid(16), primary_key=True, max_length=255)
    notification_id: str = Field(foreign_key="notifications.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)

    # 'email' | 'push' | 'in_app' | 'sms'
    channel: str = Field(nullable=False, max_length=255)
    # 'pending' | 'sent' | 'failed' | 'delivered'
    status: str = Field(default="pending", max_length=255)
    error: Optional[str] = None

    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
