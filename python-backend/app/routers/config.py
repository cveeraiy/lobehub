"""Config router — server config + feature flags for the SPA."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.feature_flags import get_feature_flags

router = APIRouter(prefix="/api/config", tags=["Config"])


@router.get("")
async def get_config():
    """Return server config consumed by the SPA on boot."""
    ff = get_feature_flags()
    return {
        "featureFlags": ff.__dict__,
        "languageModel": {
            "openai": {
                "enabled": bool(settings.openai_api_key),
            },
        },
        "serverConfig": {
            "telemetry": {},
            "defaultAgent": {},
        },
    }
