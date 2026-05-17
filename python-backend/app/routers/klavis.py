"""Klavis MCP plugin integration router.

Mirrors TS ``klavisRouter`` — manages Klavis MCP server instances
and installed plugins via the ``user_installed_plugins`` table.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.user import UserInstalledPlugin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/klavis", tags=["klavis"])

KLAVIS_API_BASE = os.getenv("KLAVIS_API_BASE_URL", "https://api.klavis.ai")
KLAVIS_API_KEY = os.getenv("KLAVIS_API_KEY", "")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CreateServerInstanceBody(BaseModel):
    identifier: str
    server_name: str
    user_id: str


class DeleteServerInstanceBody(BaseModel):
    identifier: str
    instance_id: str


class UpdateKlavisPluginBody(BaseModel):
    identifier: str
    instance_id: str
    is_authenticated: bool
    oauth_url: Optional[str] = None
    server_name: str
    server_url: str
    tools: list[dict[str, Any]]


class RemoveKlavisPluginBody(BaseModel):
    identifier: str


# ---------------------------------------------------------------------------
# Helper — call Klavis API
# ---------------------------------------------------------------------------

async def _klavis_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Make a request to the Klavis API."""
    if not KLAVIS_API_KEY:
        raise HTTPException(status_code=503, detail="Klavis API key not configured")

    headers = {"Authorization": f"Bearer {KLAVIS_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, f"{KLAVIS_API_BASE}{path}", headers=headers, **kwargs)
        if resp.status_code >= 400:
            logger.warning("Klavis API %s %s returned %d", method, path, resp.status_code)
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create-server-instance")
async def create_server_instance(
    body: CreateServerInstanceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a single MCP server instance and save to database."""
    # 1. Create instance via Klavis API
    create_resp = await _klavis_request(
        "POST",
        "/mcp/create-server-instance",
        json={"serverName": body.server_name, "userId": body.user_id},
    )
    server_url = create_resp.get("serverUrl")
    instance_id = create_resp.get("instanceId")
    oauth_url = create_resp.get("oauthUrl")

    # 2. Get tools
    tools_resp = await _klavis_request("GET", f"/mcp/tools?serverName={body.server_name}")
    tools = tools_resp.get("tools", [])

    # 3. Build manifest
    manifest = {
        "api": [
            {
                "description": t.get("description", ""),
                "name": t["name"],
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
            }
            for t in tools
        ],
        "identifier": body.identifier,
        "meta": {"avatar": "🔌", "description": f"Ethos Mcp Server: {body.server_name}", "title": body.server_name},
        "type": "default",
    }

    is_authenticated = not oauth_url

    # 4. Save to DB
    plugin = UserInstalledPlugin(
        user_id=user_id,
        identifier=body.identifier,
        type="plugin",
        manifest=manifest,
        custom_params={
            "klavis": {
                "instanceId": instance_id,
                "isAuthenticated": is_authenticated,
                "oauthUrl": oauth_url,
                "serverName": body.server_name,
                "serverUrl": server_url,
            }
        },
    )
    session.add(plugin)
    await session.flush()

    return {
        "identifier": body.identifier,
        "instanceId": instance_id,
        "isAuthenticated": is_authenticated,
        "oauthUrl": oauth_url,
        "serverName": body.server_name,
        "serverUrl": server_url,
    }


@router.post("/delete-server-instance")
async def delete_server_instance(
    body: DeleteServerInstanceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a server instance."""
    try:
        await _klavis_request("DELETE", f"/mcp/server-instance/{body.instance_id}")
    except Exception:
        logger.warning("Failed to delete Klavis instance %s", body.instance_id)

    await session.execute(
        delete(UserInstalledPlugin).where(
            and_(UserInstalledPlugin.user_id == user_id, UserInstalledPlugin.identifier == body.identifier)
        )
    )
    return {"success": True}


@router.get("/plugins")
async def get_klavis_plugins(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get Klavis plugins from database."""
    rows = (await session.execute(
        select(UserInstalledPlugin).where(UserInstalledPlugin.user_id == user_id)
    )).scalars().all()

    result = []
    for p in rows:
        cp = p.custom_params or {}
        if cp.get("klavis"):
            result.append({
                "id": p.id,
                "identifier": p.identifier,
                "type": p.type,
                "manifest": p.manifest,
                "customParams": p.custom_params,
                "createdAt": p.created_at.isoformat() if p.created_at else None,
                "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
            })
    return result


@router.get("/server-instance")
async def get_server_instance(
    instanceId: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get server instance status from Klavis API."""
    try:
        resp = await _klavis_request("GET", f"/mcp/server-instance/{instanceId}")
        return {
            "authNeeded": resp.get("authNeeded"),
            "error": None,
            "externalUserId": resp.get("externalUserId"),
            "instanceId": resp.get("instanceId"),
            "isAuthenticated": resp.get("isAuthenticated"),
            "oauthUrl": resp.get("oauthUrl"),
            "platform": resp.get("platform"),
            "serverName": resp.get("serverName"),
        }
    except HTTPException as exc:
        if exc.status_code == 401 or "Invalid API key" in str(exc.detail):
            return {
                "authNeeded": True,
                "error": "AUTH_ERROR",
                "externalUserId": None,
                "instanceId": instanceId,
                "isAuthenticated": False,
                "oauthUrl": None,
                "platform": None,
                "serverName": None,
            }
        raise


@router.get("/user-integrations")
async def get_user_integrations(
    userId: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get user integrations from Klavis API."""
    resp = await _klavis_request("GET", f"/user/{userId}/integrations")
    return {"integrations": resp.get("integrations", [])}


@router.post("/update-plugin")
async def update_klavis_plugin(
    body: UpdateKlavisPluginBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update Klavis plugin with tools and auth status in database."""
    manifest = {
        "api": [
            {
                "description": t.get("description", ""),
                "name": t["name"],
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
            }
            for t in body.tools
        ],
        "identifier": body.identifier,
        "meta": {"avatar": "🔌", "description": f"Ethos Mcp Server: {body.server_name}", "title": body.server_name},
        "type": "default",
    }

    custom_params = {
        "klavis": {
            "instanceId": body.instance_id,
            "isAuthenticated": body.is_authenticated,
            "oauthUrl": body.oauth_url,
            "serverName": body.server_name,
            "serverUrl": body.server_url,
        }
    }

    existing = (await session.execute(
        select(UserInstalledPlugin).where(
            and_(UserInstalledPlugin.user_id == user_id, UserInstalledPlugin.identifier == body.identifier)
        )
    )).scalar_one_or_none()

    if existing:
        existing.manifest = manifest
        existing.custom_params = custom_params
        session.add(existing)
    else:
        plugin = UserInstalledPlugin(
            user_id=user_id,
            identifier=body.identifier,
            type="plugin",
            manifest=manifest,
            custom_params=custom_params,
        )
        session.add(plugin)

    await session.flush()
    return {"savedCount": len(body.tools)}


@router.post("/remove-plugin")
async def remove_klavis_plugin(
    body: RemoveKlavisPluginBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove Klavis plugin from database by identifier."""
    await session.execute(
        delete(UserInstalledPlugin).where(
            and_(UserInstalledPlugin.user_id == user_id, UserInstalledPlugin.identifier == body.identifier)
        )
    )
    return {"success": True}
