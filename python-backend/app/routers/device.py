"""Self-hosted device gateway proxy endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.dependencies import get_current_user_id

router = APIRouter(prefix="/api/device", tags=["Device Gateway"])


@router.get("/status")
async def device_gateway_status(_user_id: str = Depends(get_current_user_id)):
    return {
        "capabilities": ["status", "proxy"] if settings.device_gateway_url else ["status"],
        "configured": bool(settings.device_gateway_url),
        "url": settings.device_gateway_url,
    }


@router.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_device_gateway(
    path: str,
    request: Request,
    _user_id: str = Depends(get_current_user_id),
):
    if not settings.device_gateway_url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "DEVICE_GATEWAY_URL is not configured")
    base = settings.device_gateway_url.rstrip("/")
    target = f"{base}/{path.lstrip('/')}"
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length", "authorization"}
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.request(
            request.method,
            target,
            content=body,
            headers=headers,
            params=dict(request.query_params),
        )
    try:
        payload: Any = response.json()
    except ValueError:
        payload = {"text": response.text}
    if response.status_code >= 400:
        raise HTTPException(response.status_code, payload)
    return payload
