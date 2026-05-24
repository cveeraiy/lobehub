"""RBAC tables: roles, permissions, role_permissions, user_roles. (Non-MVP)

Source: src/database/schemas/rbac.ts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel

from app.models._helpers import _utcnow, create_nanoid, json_column


class RbacRole(SQLModel, table=True):
    __tablename__ = "rbac_roles"

    id: str = Field(default_factory=lambda: create_nanoid(16), primary_key=True, max_length=255)
    name: str = Field(nullable=False, unique=True)
    display_name: str = Field(nullable=False)
    description: Optional[str] = None
    is_system: bool = Field(default=False)
    is_active: bool = Field(default=True)
    metadata_: Optional[dict[str, Any]] = Field(default=None, sa_column=json_column("metadata"))

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class RbacPermission(SQLModel, table=True):
    __tablename__ = "rbac_permissions"

    id: str = Field(default_factory=lambda: create_nanoid(16), primary_key=True, max_length=255)
    code: str = Field(nullable=False, unique=True)
    name: str = Field(nullable=False)
    description: Optional[str] = None
    category: str = Field(nullable=False)
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    updated_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    accessed_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class RbacRolePermission(SQLModel, table=True):
    __tablename__ = "rbac_role_permissions"
    __table_args__ = (
        Index("rbac_role_permissions_role_id_idx", "role_id"),
        Index("rbac_role_permissions_permission_id_idx", "permission_id"),
    )

    role_id: str = Field(foreign_key="rbac_roles.id", primary_key=True, nullable=False)
    permission_id: str = Field(foreign_key="rbac_permissions.id", primary_key=True, nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})


class RbacUserRole(SQLModel, table=True):
    __tablename__ = "rbac_user_roles"
    __table_args__ = (
        Index("rbac_user_roles_user_id_idx", "user_id"),
        Index("rbac_user_roles_role_id_idx", "role_id"),
    )

    user_id: str = Field(foreign_key="users.id", primary_key=True, nullable=False)
    role_id: str = Field(foreign_key="rbac_roles.id", primary_key=True, nullable=False)

    created_at: datetime = Field(default_factory=_utcnow, sa_column_kwargs={"server_default": text("now()")})
    expires_at: Optional[datetime] = None
