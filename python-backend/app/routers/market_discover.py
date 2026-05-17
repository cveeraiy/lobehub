"""Market Discover router — proxy to the external LobeHub Market API.

Mirrors TS: src/server/routers/lambda/market/index.ts
The TS backend uses MarketSDK / DiscoverService to call the external market.
This Python router provides a thin proxy to the same external API, forwarding
requests from the frontend REST client to https://market.lobehub.com.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discover", tags=["Discover / Market"])

MARKET_BASE_URL = os.getenv("MARKET_BASE_URL", "https://market.lobehub.com")
MARKET_TIMEOUT = 30.0


# ── Helpers ──────────────────────────────────────────────────────────

async def _proxy_get(path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    """Forward a GET request to the external Market API."""
    url = f"{MARKET_BASE_URL}{path}"
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    async with httpx.AsyncClient(timeout=MARKET_TIMEOUT) as client:
        resp = await client.get(url, params=clean_params, headers=headers or {})
        if resp.status_code >= 400:
            logger.warning("Market API error: %s %s -> %d", "GET", url, resp.status_code)
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()


async def _proxy_post(path: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    """Forward a POST request to the external Market API."""
    url = f"{MARKET_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=MARKET_TIMEOUT) as client:
        resp = await client.post(url, json=body or {}, headers=headers or {})
        if resp.status_code >= 400:
            logger.warning("Market API error: %s %s -> %d", "POST", url, resp.status_code)
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()


def _auth_headers(request: Request) -> dict[str, str]:
    """Forward authorization headers from the incoming request."""
    headers: dict[str, str] = {}
    auth = request.headers.get("authorization")
    if auth:
        headers["Authorization"] = auth
    # Forward market-specific cookies if present
    cookie = request.headers.get("cookie")
    if cookie:
        headers["Cookie"] = cookie
    return headers


# ── Schemas ──────────────────────────────────────────────────────────

class PaginatedQuery(BaseModel):
    category: Optional[str] = None
    locale: Optional[str] = None
    order: Optional[str] = None
    page: int = 1
    pageSize: int = 20
    q: Optional[str] = None
    sort: Optional[str] = None
    source: Optional[str] = None

    model_config = {"populate_by_name": True}


class DetailQuery(BaseModel):
    identifier: str
    locale: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None

    model_config = {"populate_by_name": True}


class CategoryQuery(BaseModel):
    locale: Optional[str] = None
    q: Optional[str] = None
    source: Optional[str] = None

    model_config = {"populate_by_name": True}


class ReportBody(BaseModel):
    """Generic telemetry report body — forwarded as-is."""
    model_config = {"extra": "allow"}


class RegisterClientResult(BaseModel):
    clientId: str
    clientSecret: str


class RegisterM2MTokenBody(BaseModel):
    clientId: str
    clientSecret: str


# ── Assistant Market ─────────────────────────────────────────────────

@router.get("/assistant/categories")
async def get_assistant_categories(
    locale: Optional[str] = None,
    q: Optional[str] = None,
    source: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/assistants/categories",
        params={"locale": locale, "q": q, "source": source},
        headers=_auth_headers(request),
    )


@router.get("/assistant/detail")
async def get_assistant_detail(
    identifier: str,
    locale: Optional[str] = None,
    source: Optional[str] = None,
    version: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/assistants/detail",
        params={"identifier": identifier, "locale": locale, "source": source, "version": version},
        headers=_auth_headers(request),
    )


@router.get("/assistant/identifiers")
async def get_assistant_identifiers(
    source: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/assistants/identifiers",
        params={"source": source},
        headers=_auth_headers(request),
    )


@router.get("/assistant/list")
async def get_assistant_list(
    category: Optional[str] = None,
    locale: Optional[str] = None,
    order: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    source: Optional[str] = None,
    ownerId: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/assistants",
        params={
            "category": category, "locale": locale, "order": order,
            "page": page, "pageSize": pageSize, "q": q, "sort": sort,
            "source": source, "ownerId": ownerId,
        },
        headers=_auth_headers(request),
    )


@router.get("/assistant/by-plugin")
async def get_agents_by_plugin(
    pluginId: str,
    locale: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/assistants/by-plugin",
        params={"pluginId": pluginId, "locale": locale, "page": page, "pageSize": pageSize},
        headers=_auth_headers(request),
    )


# ── MCP Market ───────────────────────────────────────────────────────

@router.get("/mcp/categories")
async def get_mcp_categories(
    locale: Optional[str] = None,
    q: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/mcp/categories",
        params={"locale": locale, "q": q},
        headers=_auth_headers(request),
    )


@router.get("/mcp/detail")
async def get_mcp_detail(
    identifier: str,
    locale: Optional[str] = None,
    version: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/mcp/detail",
        params={"identifier": identifier, "locale": locale, "version": version},
        headers=_auth_headers(request),
    )


@router.get("/mcp/list")
async def get_mcp_list(
    category: Optional[str] = None,
    locale: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/mcp",
        params={
            "category": category, "locale": locale,
            "page": page, "pageSize": pageSize, "q": q, "sort": sort,
        },
        headers=_auth_headers(request),
    )


@router.get("/mcp/manifest")
async def get_mcp_manifest(
    identifier: str,
    locale: Optional[str] = None,
    version: Optional[str] = None,
    install: Optional[bool] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/mcp/manifest",
        params={"identifier": identifier, "locale": locale, "version": version, "install": install},
        headers=_auth_headers(request),
    )


# ── Model Market ─────────────────────────────────────────────────────

@router.get("/model/categories")
async def get_model_categories(
    locale: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/models/categories",
        params={"locale": locale},
        headers=_auth_headers(request),
    )


@router.get("/model/detail")
async def get_model_detail(
    identifier: str,
    locale: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/models/detail",
        params={"identifier": identifier, "locale": locale},
        headers=_auth_headers(request),
    )


@router.get("/model/identifiers")
async def get_model_identifiers(
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get("/api/models/identifiers", headers=_auth_headers(request))


@router.get("/model/list")
async def get_model_list(
    category: Optional[str] = None,
    locale: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/models",
        params={
            "category": category, "locale": locale,
            "page": page, "pageSize": pageSize, "q": q, "sort": sort,
        },
        headers=_auth_headers(request),
    )


# ── Plugin Market ────────────────────────────────────────────────────

@router.get("/plugin/categories")
async def get_plugin_categories(
    locale: Optional[str] = None,
    q: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/plugins/categories",
        params={"locale": locale, "q": q},
        headers=_auth_headers(request),
    )


@router.get("/plugin/detail")
async def get_plugin_detail(
    identifier: str,
    locale: Optional[str] = None,
    withManifest: Optional[bool] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/plugins/detail",
        params={"identifier": identifier, "locale": locale, "withManifest": withManifest},
        headers=_auth_headers(request),
    )


@router.get("/plugin/identifiers")
async def get_plugin_identifiers(
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get("/api/plugins/identifiers", headers=_auth_headers(request))


@router.get("/plugin/list")
async def get_plugin_list(
    category: Optional[str] = None,
    locale: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/plugins",
        params={
            "category": category, "locale": locale,
            "page": page, "pageSize": pageSize, "q": q, "sort": sort,
        },
        headers=_auth_headers(request),
    )


# ── Provider Market ──────────────────────────────────────────────────

@router.get("/provider/detail")
async def get_provider_detail(
    identifier: str,
    locale: Optional[str] = None,
    withReadme: Optional[bool] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/providers/detail",
        params={"identifier": identifier, "locale": locale, "withReadme": withReadme},
        headers=_auth_headers(request),
    )


@router.get("/provider/identifiers")
async def get_provider_identifiers(
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get("/api/providers/identifiers", headers=_auth_headers(request))


@router.get("/provider/list")
async def get_provider_list(
    category: Optional[str] = None,
    locale: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/providers",
        params={
            "category": category, "locale": locale,
            "page": page, "pageSize": pageSize, "q": q, "sort": sort,
        },
        headers=_auth_headers(request),
    )


# ── Skill Market ────────────────────────────────────────────────────

@router.get("/skill/categories")
async def get_skill_categories(
    locale: Optional[str] = None,
    q: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/skills/categories",
        params={"locale": locale, "q": q},
        headers=_auth_headers(request),
    )


@router.get("/skill/detail")
async def get_skill_detail(
    identifier: str,
    locale: Optional[str] = None,
    version: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/skills/detail",
        params={"identifier": identifier, "locale": locale, "version": version},
        headers=_auth_headers(request),
    )


@router.get("/skill/list")
async def get_skill_list(
    category: Optional[str] = None,
    locale: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/skills",
        params={
            "category": category, "locale": locale,
            "page": page, "pageSize": pageSize, "q": q, "sort": sort,
        },
        headers=_auth_headers(request),
    )


# ── Group Agent Market ───────────────────────────────────────────────

@router.get("/group-agent/categories")
async def get_group_agent_categories(
    locale: Optional[str] = None,
    q: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/agent-groups/categories",
        params={"locale": locale, "q": q},
        headers=_auth_headers(request),
    )


@router.get("/group-agent/detail")
async def get_group_agent_detail(
    identifier: str,
    locale: Optional[str] = None,
    version: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/agent-groups/detail",
        params={"identifier": identifier, "locale": locale, "version": version},
        headers=_auth_headers(request),
    )


@router.get("/group-agent/identifiers")
async def get_group_agent_identifiers(
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get("/api/agent-groups/identifiers", headers=_auth_headers(request))


@router.get("/group-agent/list")
async def get_group_agent_list(
    category: Optional[str] = None,
    locale: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/agent-groups",
        params={
            "category": category, "locale": locale,
            "page": page, "pageSize": pageSize, "q": q, "sort": sort,
        },
        headers=_auth_headers(request),
    )


# ── User Profile ─────────────────────────────────────────────────────

@router.get("/user/info")
async def get_user_info(
    username: str,
    locale: Optional[str] = None,
    request: Request = None,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/users/info",
        params={"username": username, "locale": locale},
        headers=_auth_headers(request),
    )


# ── Client Registration & Token ──────────────────────────────────────

@router.post("/register-client")
async def register_client(
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    """Register a client in the marketplace for M2M authentication."""
    return await _proxy_post(
        "/api/clients/register",
        headers=_auth_headers(request),
    )


@router.post("/register-m2m-token")
async def register_m2m_token(
    body: RegisterM2MTokenBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    """Get an M2M access token using client credentials."""
    return await _proxy_post(
        "/api/clients/token",
        body={"clientId": body.clientId, "clientSecret": body.clientSecret},
        headers=_auth_headers(request),
    )


# ── Telemetry / Reporting ────────────────────────────────────────────

@router.post("/report/agent-install")
async def report_agent_install(
    body: ReportBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/telemetry/agent-install",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.post("/report/agent-event")
async def report_agent_event(
    body: ReportBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/telemetry/agent-event",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.post("/report/call")
async def report_call(
    body: ReportBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/telemetry/call",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.post("/report/mcp-install")
async def report_mcp_install(
    body: ReportBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/telemetry/mcp-install",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.post("/report/mcp-event")
async def report_mcp_event(
    body: ReportBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/telemetry/mcp-event",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.post("/report/group-agent-event")
async def report_group_agent_event(
    body: ReportBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/telemetry/group-agent-event",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.post("/report/group-agent-install")
async def report_group_agent_install(
    body: ReportBody,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/telemetry/group-agent-install",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )
