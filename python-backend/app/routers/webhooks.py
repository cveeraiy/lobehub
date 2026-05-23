"""Legacy webhook compatibility endpoints owned by the Python backend."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


async def _json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


@router.post("/casdoor")
@router.post("/logto")
async def retired_auth_provider_webhook(request: Request):
    await _json(request)
    return {
        "ok": True,
        "ignored": True,
        "reason": "Legacy auth provider webhook retired; Keycloak is the only auth provider",
    }


@router.post("/memory-extraction")
@router.post("/memory-extraction/benchmark-locomo")
@router.post("/memory-user-memory/persona/update-writing")
@router.post("/memory-user-memory/pipelines/extract/chat-topic/cancel")
async def retired_memory_webhook(request: Request):
    await _json(request)
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={
            "ok": False,
            "reason": "Legacy TS webhook transport retired; use /api/workflows routes",
        },
    )


@router.post("/video/{provider}")
async def retired_video_callback(provider: str, request: Request):
    await _json(request)
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={
            "ok": False,
            "provider": provider,
            "reason": "Legacy TS video callback transport retired",
        },
    )
