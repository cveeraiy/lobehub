"""Config router — server config + feature flags for the SPA."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from app.config import settings
from app.dependencies import get_current_user_id
from app.feature_flags import get_feature_flags

router = APIRouter(tags=["Config"])


def _build_server_config() -> dict:
    """Build the GlobalServerConfig shape the SPA expects."""
    oAuthSSOProviders = []
    if getattr(settings, "auth_oidc_issuer", None):
        oAuthSSOProviders.append("keycloak")

    return {
        "aiProvider": {
            "openai": {
                "enabled": bool(settings.openai_api_key),
            },
        },
        "defaultAgent": {},
        "enableUploadFileToServer": True,
        "enableKlavis": bool(getattr(settings, "klavis_api_key", None)),
        "oAuthSSOProviders": oAuthSSOProviders,
        "telemetry": {},
    }


@router.get("/api/version")
async def get_version():
    """Return server version. SPA uses this to check compatibility."""
    return {"version": settings.version if hasattr(settings, 'version') else "0.1.0"}


@router.get("/api/config")
async def get_config():
    """Return server config consumed by the SPA on boot."""
    ff = get_feature_flags()
    return {
        "featureFlags": ff.to_camel_dict(),
        "languageModel": {
            "openai": {
                "enabled": bool(settings.openai_api_key),
            },
        },
        "serverConfig": _build_server_config(),
    }


@router.get("/api/config/global")
async def get_global_config():
    """Return GlobalRuntimeConfig — matches TRPC config.getGlobalConfig."""
    ff = get_feature_flags()
    return {
        "billboard": None,
        "serverConfig": _build_server_config(),
        "serverFeatureFlags": ff.to_camel_dict(),
    }


@router.get("/api/config/default-agent")
async def get_default_agent_config():
    """Return default agent config — matches TRPC config.getDefaultAgentConfig."""
    return {}
