"""Social router — follow/favorite/like actions via external Market API proxy.

Frontend: src/services/social.rest.ts
Prefix: /api/social

The social features (follow, favorite, like) are managed by the external
LobeHub Market API. This router proxies requests from the frontend REST client
to that external API, forwarding auth headers.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/social", tags=["Social"])

MARKET_BASE_URL = os.getenv("MARKET_BASE_URL", "https://market.lobehub.com")
MARKET_TIMEOUT = 30.0


# ── Helpers ──────────────────────────────────────────────────────────

def _auth_headers(request: Request) -> dict[str, str]:
    """Forward authorization headers from the incoming request."""
    headers: dict[str, str] = {}
    auth = request.headers.get("authorization")
    if auth:
        headers["Authorization"] = auth
    cookie = request.headers.get("cookie")
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def _proxy_get(
    path: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    url = f"{MARKET_BASE_URL}{path}"
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    async with httpx.AsyncClient(timeout=MARKET_TIMEOUT) as client:
        resp = await client.get(url, params=clean_params, headers=headers or {})
        if resp.status_code >= 400:
            logger.warning("Market social API error: GET %s -> %d", url, resp.status_code)
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()


async def _proxy_post(
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    url = f"{MARKET_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=MARKET_TIMEOUT) as client:
        resp = await client.post(url, json=body or {}, headers=headers or {})
        if resp.status_code >= 400:
            logger.warning("Market social API error: POST %s -> %d", url, resp.status_code)
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()


# ── Schemas ──────────────────────────────────────────────────────────

class FollowBody(BaseModel):
    followingId: int


class TargetBody(BaseModel):
    targetId: Optional[int] = None
    identifier: Optional[str] = None
    targetType: str  # 'agent' | 'plugin' | 'agent-group'


# ── Follow endpoints ────────────────────────────────────────────────

@router.post("/follow")
async def follow(
    body: FollowBody,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/social/follow",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.post("/unfollow")
async def unfollow(
    body: FollowBody,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/social/unfollow",
        body=body.model_dump(),
        headers=_auth_headers(request),
    )


@router.get("/follow-status")
async def check_follow_status(
    targetUserId: int,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/follow-status",
        params={"targetUserId": targetUserId},
        headers=_auth_headers(request),
    )


@router.get("/follow-counts")
async def get_follow_counts(
    userId: int,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/follow-counts",
        params={"userId": userId},
        headers=_auth_headers(request),
    )


@router.get("/following")
async def get_following(
    userId: int,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/following",
        params={"userId": userId, "limit": limit, "offset": offset},
        headers=_auth_headers(request),
    )


@router.get("/followers")
async def get_followers(
    userId: int,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/followers",
        params={"userId": userId, "limit": limit, "offset": offset},
        headers=_auth_headers(request),
    )


# ── Favorite endpoints ──────────────────────────────────────────────

@router.post("/favorite")
async def add_favorite(
    body: TargetBody,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/social/favorite",
        body=body.model_dump(exclude_none=True),
        headers=_auth_headers(request),
    )


@router.post("/unfavorite")
async def remove_favorite(
    body: TargetBody,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/social/unfavorite",
        body=body.model_dump(exclude_none=True),
        headers=_auth_headers(request),
    )


@router.get("/favorite-status")
async def check_favorite_status(
    targetType: str,
    targetIdOrIdentifier: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/favorite-status",
        params={"targetType": targetType, "targetIdOrIdentifier": targetIdOrIdentifier},
        headers=_auth_headers(request),
    )


@router.get("/my-favorites")
async def get_my_favorites(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/my-favorites",
        params={"limit": limit, "offset": offset},
        headers=_auth_headers(request),
    )


@router.get("/favorite-agents")
async def get_user_favorite_agents(
    userId: int,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/favorite-agents",
        params={"userId": userId, "limit": limit, "offset": offset},
        headers=_auth_headers(request),
    )


@router.get("/favorite-plugins")
async def get_user_favorite_plugins(
    userId: int,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/favorite-plugins",
        params={"userId": userId, "limit": limit, "offset": offset},
        headers=_auth_headers(request),
    )


# ── Like endpoints ──────────────────────────────────────────────────

@router.post("/like")
async def like(
    body: TargetBody,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/social/like",
        body=body.model_dump(exclude_none=True),
        headers=_auth_headers(request),
    )


@router.post("/unlike")
async def unlike(
    body: TargetBody,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/social/unlike",
        body=body.model_dump(exclude_none=True),
        headers=_auth_headers(request),
    )


@router.get("/like-status")
async def check_like_status(
    targetType: str,
    targetIdOrIdentifier: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/like-status",
        params={"targetType": targetType, "targetIdOrIdentifier": targetIdOrIdentifier},
        headers=_auth_headers(request),
    )


@router.post("/toggle-like")
async def toggle_like(
    body: TargetBody,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_post(
        "/api/social/toggle-like",
        body=body.model_dump(exclude_none=True),
        headers=_auth_headers(request),
    )


@router.get("/liked-agents")
async def get_user_liked_agents(
    userId: int,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/liked-agents",
        params={"userId": userId, "limit": limit, "offset": offset},
        headers=_auth_headers(request),
    )


@router.get("/liked-plugins")
async def get_user_liked_plugins(
    userId: int,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
    user_id: str = Depends(get_current_user_id),
):
    return await _proxy_get(
        "/api/social/liked-plugins",
        params={"userId": userId, "limit": limit, "offset": offset},
        headers=_auth_headers(request),
    )
