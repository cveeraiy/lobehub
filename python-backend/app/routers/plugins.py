"""MCP plugin install / uninstall / list router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.user import UserInstalledPlugin

router = APIRouter(prefix="/api/plugins", tags=["Plugins"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class InstallPluginBody(BaseModel):
    identifier: str
    type: str = "plugin"  # plugin | customPlugin
    manifest: Optional[dict[str, Any]] = None
    settings: Optional[dict[str, Any]] = None
    custom_params: Optional[dict[str, Any]] = None


class UpdatePluginBody(BaseModel):
    settings: Optional[dict[str, Any]] = None
    manifest: Optional[dict[str, Any]] = None
    custom_params: Optional[dict[str, Any]] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_plugins(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserInstalledPlugin)
        .where(UserInstalledPlugin.user_id == user_id)
        .order_by(desc(UserInstalledPlugin.created_at))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_plugin_dict(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/install", status_code=status.HTTP_201_CREATED)
async def install_plugin(
    body: InstallPluginBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    plugin = UserInstalledPlugin(
        user_id=user_id,
        identifier=body.identifier,
        type=body.type,
        manifest=body.manifest,
        settings=body.settings,
        custom_params=body.custom_params,
    )
    session.add(plugin)
    await session.flush()
    return {"id": plugin.id}


@router.put("/{identifier}")
async def update_plugin(
    identifier: str,
    body: UpdatePluginBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    values["updated_at"] = _now()
    stmt = (
        update(UserInstalledPlugin)
        .where(
            and_(
                UserInstalledPlugin.identifier == identifier,
                UserInstalledPlugin.user_id == user_id,
            )
        )
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{identifier}")
async def uninstall_plugin(
    identifier: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(UserInstalledPlugin).where(
            and_(
                UserInstalledPlugin.identifier == identifier,
                UserInstalledPlugin.user_id == user_id,
            )
        )
    )
    return {"ok": True}


@router.delete("")
async def remove_all_plugins(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove all installed plugins for the user."""
    await session.execute(
        delete(UserInstalledPlugin).where(UserInstalledPlugin.user_id == user_id)
    )
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

def _plugin_dict(p: UserInstalledPlugin) -> dict[str, Any]:
    return {
        "id": p.id,
        "identifier": p.identifier,
        "type": p.type,
        "manifest": p.manifest,
        "settings": p.settings,
        "custom_params": p.custom_params,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
