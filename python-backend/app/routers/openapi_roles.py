"""OpenAPI v1 role routes.

Compatibility layer for ``packages/openapi/src/routes/roles.route.ts``.
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
from app.models.rbac import RbacPermission, RbacRole, RbacRolePermission

router = APIRouter(prefix="/api/v1/roles", tags=["OpenAPI Roles"])


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _success(data: Any = None, message: str | None = None) -> dict[str, Any]:
    return {"data": data, "message": message, "success": True, "timestamp": _now().isoformat()}


class RoleBody(BaseModel):
    description: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    is_active: bool | None = Field(None, alias="isActive")
    is_system: bool | None = Field(None, alias="isSystem")
    metadata: dict[str, Any] | None = None
    name: str | None = None

    model_config = {"populate_by_name": True}


class RolePermissionsBody(BaseModel):
    grant: list[str] | None = None
    revoke: list[str] | None = None


def _role_dict(role: RbacRole) -> dict[str, Any]:
    return {
        "id": role.id,
        "description": role.description,
        "displayName": role.display_name,
        "isActive": role.is_active,
        "isSystem": role.is_system,
        "metadata": role.metadata_,
        "name": role.name,
        "createdAt": role.created_at.isoformat() if role.created_at else None,
        "updatedAt": role.updated_at.isoformat() if role.updated_at else None,
    }


def _permission_dict(permission: RbacPermission) -> dict[str, Any]:
    return {
        "id": permission.id,
        "category": permission.category,
        "code": permission.code,
        "description": permission.description,
        "isActive": permission.is_active,
        "name": permission.name,
    }


@router.get("")
async def list_roles(
    active: bool | None = None,
    system: bool | None = None,
    keyword: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    conditions = []
    if active is not None:
        conditions.append(RbacRole.is_active == active)
    if system is not None:
        conditions.append(RbacRole.is_system == system)
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(or_(RbacRole.name.ilike(pattern), RbacRole.display_name.ilike(pattern)))
    where_expr = and_(*conditions) if conditions else None
    stmt = select(RbacRole).order_by(RbacRole.is_system.desc(), RbacRole.created_at.asc())
    count_stmt = select(func.count()).select_from(RbacRole)
    if where_expr is not None:
        stmt = stmt.where(where_expr)
        count_stmt = count_stmt.where(where_expr)
    rows = (
        await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    total = (await session.execute(count_stmt)).scalar_one()
    return _success({"roles": [_role_dict(row) for row in rows], "total": total}, "Get roles list successfully")


@router.post("")
async def create_role(
    body: RoleBody,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not body.name or not body.display_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "name and displayName are required")
    existing = (await session.execute(select(RbacRole).where(RbacRole.name == body.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Role name already exists")
    role = RbacRole(
        description=body.description,
        display_name=body.display_name,
        is_active=True if body.is_active is None else body.is_active,
        is_system=False if body.is_system is None else body.is_system,
        metadata_=body.metadata,
        name=body.name,
    )
    session.add(role)
    await session.flush()
    return _success(_role_dict(role), "角色创建成功")


@router.get("/{role_id}")
async def get_role(
    role_id: str,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    role = await session.get(RbacRole, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    return _success(_role_dict(role), "Get role details successfully")


@router.patch("/{role_id}")
async def update_role(
    role_id: str,
    body: RoleBody,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    role = await session.get(RbacRole, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    values = body.model_dump(exclude_none=True, by_alias=False)
    if "metadata" in values:
        values["metadata_"] = values.pop("metadata")
    values["updated_at"] = _now()
    await session.execute(update(RbacRole).where(RbacRole.id == role_id).values(**values))
    await session.flush()
    updated = await session.get(RbacRole, role_id)
    return _success(_role_dict(updated), "角色更新成功")


@router.delete("/{role_id}")
async def delete_role(
    role_id: str,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    role = await session.get(RbacRole, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if role.is_system:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "System roles cannot be deleted")
    await session.execute(delete(RbacRolePermission).where(RbacRolePermission.role_id == role_id))
    await session.execute(delete(RbacRole).where(RbacRole.id == role_id))
    return _success({"deleted": True, "id": role_id}, "角色删除成功")


@router.get("/{role_id}/permissions")
async def get_role_permissions(
    role_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    role = await session.get(RbacRole, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    stmt = (
        select(RbacPermission)
        .join(RbacRolePermission, RbacRolePermission.permission_id == RbacPermission.id)
        .where(RbacRolePermission.role_id == role_id)
        .order_by(RbacPermission.category.asc(), RbacPermission.code.asc())
    )
    count_stmt = select(func.count()).select_from(RbacRolePermission).where(RbacRolePermission.role_id == role_id)
    rows = (
        await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    total = (await session.execute(count_stmt)).scalar_one()
    return _success(
        {"permissions": [_permission_dict(row) for row in rows], "total": total},
        "Get role permissions successfully",
    )


@router.patch("/{role_id}/permissions")
async def update_role_permissions(
    role_id: str,
    body: RolePermissionsBody,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    role = await session.get(RbacRole, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    grant = set(body.grant or [])
    revoke = set(body.revoke or [])
    if not grant and not revoke:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "grant or revoke is required")
    for permission_id in grant:
        if not await session.get(RbacPermission, permission_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Permission not found: {permission_id}")
        exists = (
            await session.execute(
                select(RbacRolePermission).where(
                    and_(RbacRolePermission.role_id == role_id, RbacRolePermission.permission_id == permission_id)
                )
            )
        ).scalar_one_or_none()
        if not exists:
            session.add(RbacRolePermission(role_id=role_id, permission_id=permission_id))
    if revoke:
        await session.execute(
            delete(RbacRolePermission).where(
                and_(RbacRolePermission.role_id == role_id, RbacRolePermission.permission_id.in_(revoke))
            )
        )
    return _success({"granted": len(grant), "revoked": len(revoke), "roleId": role_id}, "角色权限更新成功")


@router.delete("/{role_id}/permissions")
async def clear_role_permissions(
    role_id: str,
    _user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    role = await session.get(RbacRole, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    await session.execute(delete(RbacRolePermission).where(RbacRolePermission.role_id == role_id))
    return _success({"cleared": True, "roleId": role_id}, "角色权限已清空")
