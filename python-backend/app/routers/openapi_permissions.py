"""OpenAPI v1 permission routes.

Compatibility layer for ``packages/openapi/src/routes/permissions.route.ts``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.rbac import RbacPermission, RbacRolePermission

router = APIRouter(prefix="/api/v1/permissions", tags=["OpenAPI Permissions"])


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _success(data: Any = None, message: str | None = None) -> dict[str, Any]:
    return {"data": data, "message": message, "success": True, "timestamp": _now().isoformat()}


class PermissionBody(BaseModel):
    category: str | None = None
    code: str | None = None
    description: str | None = None
    is_active: bool | None = Field(None, alias="isActive")
    name: str | None = None

    model_config = {"populate_by_name": True}


def _permission_dict(permission: RbacPermission) -> dict[str, Any]:
    return {
        "id": permission.id,
        "category": permission.category,
        "code": permission.code,
        "description": permission.description,
        "isActive": permission.is_active,
        "name": permission.name,
        "createdAt": permission.created_at.isoformat() if permission.created_at else None,
        "updatedAt": permission.updated_at.isoformat() if permission.updated_at else None,
    }


@router.get("")
async def list_permissions(
    active: bool | None = None,
    category: str | None = None,
    keyword: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    conditions = []
    if active is not None:
        conditions.append(RbacPermission.is_active == active)
    if category:
        conditions.append(RbacPermission.category == category)
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(
            or_(
                RbacPermission.code.ilike(pattern),
                RbacPermission.name.ilike(pattern),
                RbacPermission.description.ilike(pattern),
            )
        )
    where_expr = and_(*conditions) if conditions else None
    stmt = select(RbacPermission).order_by(RbacPermission.created_at.desc())
    count_stmt = select(func.count()).select_from(RbacPermission)
    if where_expr is not None:
        stmt = stmt.where(where_expr)
        count_stmt = count_stmt.where(where_expr)
    rows = (
        await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    total = (await session.execute(count_stmt)).scalar_one()
    return _success(
        {"permissions": [_permission_dict(row) for row in rows], "total": total},
        "Get permission list successfully",
    )


@router.get("/{permission_id}")
async def get_permission(
    permission_id: str,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    permission = await session.get(RbacPermission, permission_id)
    if not permission:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission not found")
    return _success(_permission_dict(permission), "Get permission successfully")


@router.post("")
async def create_permission(
    body: PermissionBody,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not body.code or not body.name or not body.category:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "code, name and category are required")
    existing = (
        await session.execute(select(RbacPermission).where(RbacPermission.code == body.code))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Permission code already exists")
    permission = RbacPermission(
        category=body.category,
        code=body.code,
        description=body.description,
        is_active=True if body.is_active is None else body.is_active,
        name=body.name,
    )
    session.add(permission)
    await session.flush()
    return _success(_permission_dict(permission), "Permission created successfully")


@router.patch("/{permission_id}")
async def update_permission(
    permission_id: str,
    body: PermissionBody,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    permission = await session.get(RbacPermission, permission_id)
    if not permission:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission not found")
    values = body.model_dump(exclude_none=True, by_alias=False)
    if "is_active" in values:
        values["is_active"] = values.pop("is_active")
    if "code" in values and values["code"] != permission.code:
        duplicate = (
            await session.execute(select(RbacPermission).where(RbacPermission.code == values["code"]))
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Permission code already exists")
    values["updated_at"] = _now()
    await session.execute(update(RbacPermission).where(RbacPermission.id == permission_id).values(**values))
    await session.flush()
    updated = await session.get(RbacPermission, permission_id)
    return _success(_permission_dict(updated), "Permission updated successfully")


@router.delete("/{permission_id}")
async def delete_permission(
    permission_id: str,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    permission = await session.get(RbacPermission, permission_id)
    if not permission:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permission not found")
    linked = (
        await session.execute(select(RbacRolePermission).where(RbacRolePermission.permission_id == permission_id))
    ).first()
    if linked:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Permission is assigned to roles and cannot be deleted")
    await session.execute(delete(RbacPermission).where(RbacPermission.id == permission_id))
    return _success({"deleted": True, "id": permission_id}, "Permission deleted successfully")
