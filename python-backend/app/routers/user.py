"""User router — SPA boot payload, settings, preferences, avatar, onboarding.

Mirrors the TS ``user.ts`` router. The ``getUserState`` endpoint is the SPA's
first call on boot to hydrate the client store.
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user_id
from app.feature_flags import get_feature_flags
from app.models.message import Message
from app.models.session import Session
from app.models.user import User, UserSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["User"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class UpdateSettingsBody(BaseModel):
    general: Optional[dict[str, Any]] = None
    default_agent: Optional[dict[str, Any]] = None
    key_vaults: Optional[dict[str, Any]] = None
    language_model: Optional[dict[str, Any]] = None
    system_agent: Optional[dict[str, Any]] = None
    tool: Optional[dict[str, Any]] = None
    tts: Optional[dict[str, Any]] = None


class UpdatePreferenceBody(BaseModel):
    """Partial preference merge."""
    # Accept arbitrary keys — the SPA controls the shape
    class Config:
        extra = "allow"


class UpdateGuideBody(BaseModel):
    class Config:
        extra = "allow"


class UpdateOnboardingBody(BaseModel):
    class Config:
        extra = "allow"


# ── getUserState (SPA boot) ──────────────────────────────────────────

@router.get("/state")
async def get_user_state(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Return the initial user state payload for the SPA.

    Includes: user profile, settings, preference, feature flags, onboarding status.
    """
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # Get settings
    user_settings = (
        await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none()

    # Count messages (for guide state)
    from sqlalchemy import func
    msg_count = (
        await session.execute(
            select(func.count()).select_from(Message).where(Message.user_id == user_id)
        )
    ).scalar_one()

    has_extra_session = (
        await session.execute(
            select(func.count()).select_from(Session).where(Session.user_id == user_id)
        )
    ).scalar_one() > 1

    # Update last active
    await session.execute(
        update(User).where(User.id == user_id).values(accessed_at=_now())
    )

    # Decrypt key vaults if present
    decrypted_key_vaults: Optional[dict[str, Any]] = None
    if user_settings and user_settings.key_vaults and settings.key_vaults_secret:
        try:
            from cryptography.fernet import Fernet
            f = Fernet(settings.key_vaults_secret.encode())
            import json
            decrypted_key_vaults = json.loads(f.decrypt(user_settings.key_vaults.encode()))
        except Exception:
            logger.warning("Failed to decrypt key_vaults for user %s", user_id)

    ff = get_feature_flags(user_id)

    return {
        "userId": user.id,
        "username": user.username,
        "email": user.email,
        "avatar": user.avatar,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "fullName": f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
        "isOnboard": user.is_onboarded,
        "preference": user.preference or {},
        "hasConversation": msg_count > 0 or has_extra_session,
        "canEnablePWAGuide": msg_count > 4,
        "canEnableTrace": msg_count > 4,
        "settings": _settings_dict(user_settings, decrypted_key_vaults) if user_settings else {},
        "featureFlags": ff.__dict__,
    }


# ── Settings CRUD ────────────────────────────────────────────────────

@router.put("/settings")
async def update_settings(
    body: UpdateSettingsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Upsert user settings (general, language_model, tts, etc.)."""
    existing = (
        await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none()

    values = body.model_dump(exclude_none=True)

    # Encrypt key_vaults if provided
    if "key_vaults" in values and values["key_vaults"] is not None:
        if settings.key_vaults_secret:
            import json
            from cryptography.fernet import Fernet
            f = Fernet(settings.key_vaults_secret.encode())
            values["key_vaults"] = f.encrypt(json.dumps(values["key_vaults"]).encode()).decode()
        else:
            # Store as plain JSON string if no encryption key configured
            import json
            values["key_vaults"] = json.dumps(values["key_vaults"])

    if existing:
        values["updated_at"] = _now()
        stmt = update(UserSettings).where(UserSettings.user_id == user_id).values(**values)
        await session.execute(stmt)
    else:
        us = UserSettings(user_id=user_id, **values)
        session.add(us)
        await session.flush()

    return {"ok": True}


@router.delete("/settings")
async def reset_settings(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Reset user settings to defaults (delete the row)."""
    from sqlalchemy import delete
    await session.execute(
        delete(UserSettings).where(UserSettings.user_id == user_id)
    )
    return {"ok": True}


# ── Avatar ───────────────────────────────────────────────────────────

@router.put("/avatar")
async def update_avatar(
    body: dict[str, str],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update user avatar — supports base64 data URL or external URL."""
    avatar_input = body.get("avatar", "")

    if not avatar_input:
        # Clear avatar
        await session.execute(update(User).where(User.id == user_id).values(avatar=None))
        return {"ok": True}

    if avatar_input.startswith("data:image"):
        # Upload base64 to S3
        try:
            from app.services.file_service import S3Client

            # Parse data URL
            semicolon_idx = avatar_input.index(";")
            mime_type = avatar_input[5:semicolon_idx]  # e.g. "image/png"
            file_type = mime_type.split("/")[1]

            comma_idx = avatar_input.index(",")
            b64_data = avatar_input[comma_idx + 1:]
            buffer = base64.b64decode(b64_data)

            # Get old avatar for deletion
            user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
            old_avatar = user.avatar

            file_name = f"{uuid.uuid4()}.{file_type}"
            file_path = f"user/avatar/{user_id}/{file_name}"

            s3 = S3Client()
            s3.upload_bytes(file_path, buffer, mime_type)

            # Delete old avatar from S3
            own_prefix = f"/webapi/user/avatar/{user_id}/"
            if old_avatar and old_avatar.startswith(own_prefix) and ".." not in old_avatar:
                old_key = old_avatar[len("/webapi/"):]
                try:
                    s3.delete_file(old_key)
                except Exception:
                    logger.warning("Failed to delete old avatar: %s", old_key)

            avatar_url = f"/webapi/{file_path}"
            await session.execute(update(User).where(User.id == user_id).values(avatar=avatar_url))
            return {"ok": True, "avatar": avatar_url}

        except Exception as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Avatar upload failed: {exc}")

    # External URL — validate
    if avatar_input.startswith("http://") or avatar_input.startswith("https://"):
        await session.execute(update(User).where(User.id == user_id).values(avatar=avatar_input))
        return {"ok": True, "avatar": avatar_input}

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid avatar input")


# ── Preference ───────────────────────────────────────────────────────

@router.put("/preference")
async def update_preference(
    body: UpdatePreferenceBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Merge partial preference into existing user preference."""
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    current = user.preference or {}
    current.update(body.model_dump(exclude_none=True))
    await session.execute(update(User).where(User.id == user_id).values(preference=current))
    return {"ok": True}


# ── Profile updates ──────────────────────────────────────────────────

@router.put("/username")
async def update_username(
    body: dict[str, str],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update username (unique check)."""
    username = (body.get("username") or "").strip()
    if not username or len(username) > 64:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid username")

    # Check uniqueness
    existing = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if existing and existing.id != user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "USERNAME_TAKEN")

    await session.execute(update(User).where(User.id == user_id).values(username=username))
    return {"ok": True}


@router.put("/fullname")
async def update_full_name(
    body: dict[str, str],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update first_name (used as display name / full name)."""
    full_name = (body.get("fullName") or "").strip()
    if len(full_name) > 64:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "FULLNAME_TOO_LONG")

    await session.execute(update(User).where(User.id == user_id).values(first_name=full_name))
    return {"ok": True}


@router.post("/onboarded")
async def make_user_onboarded(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(update(User).where(User.id == user_id).values(is_onboarded=True))
    return {"ok": True}


@router.put("/guide")
async def update_guide(
    body: UpdateGuideBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Merge guide state into user preference."""
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    current = user.preference or {}
    guide = current.get("guide", {})
    guide.update(body.model_dump(exclude_none=True))
    current["guide"] = guide
    await session.execute(update(User).where(User.id == user_id).values(preference=current))
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

def _settings_dict(us: Optional[UserSettings], decrypted_kv: Optional[dict] = None) -> dict[str, Any]:
    if not us:
        return {}
    d: dict[str, Any] = {}
    if us.general:
        d["general"] = us.general
    if us.default_agent:
        d["defaultAgent"] = us.default_agent
    if us.language_model:
        d["languageModel"] = us.language_model
    if us.system_agent:
        d["systemAgent"] = us.system_agent
    if us.tool:
        d["tool"] = us.tool
    if us.tts:
        d["tts"] = us.tts
    if decrypted_kv:
        d["keyVaults"] = decrypted_kv
    return d
