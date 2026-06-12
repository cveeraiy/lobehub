"""API Keys router — personal API key CRUD."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.misc import ApiKey
from app.services.key_vault.service import KeyVaultService

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])


class CreateApiKeyBody(BaseModel):
    name: str
    expires_at: Optional[datetime] = None


class UpdateApiKeyBody(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    expires_at: Optional[datetime] = None


class ValidateApiKeyBody(BaseModel):
    key: str


@router.get("")
async def list_api_keys(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(desc(ApiKey.created_at))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_key_dict(k) for k in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateApiKeyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a new API key. The raw key is returned only once."""
    raw_key = _generate_api_key()
    key_hash = _hash_api_key(raw_key)
    encrypted_key = KeyVaultService.from_env().encrypt(raw_key)

    api_key = ApiKey(
        user_id=user_id,
        name=body.name,
        key=encrypted_key,
        key_hash=key_hash,
        expires_at=body.expires_at,
    )
    session.add(api_key)
    await session.flush()
    return _key_dict(api_key, decrypted_key=raw_key)


@router.get("/{key_id}")
async def get_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    row = (await session.execute(
        select(ApiKey).where(and_(ApiKey.id == key_id, ApiKey.user_id == user_id))
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    return _key_dict(row)


@router.put("/{key_id}")
async def update_api_key(
    key_id: str,
    body: UpdateApiKeyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_unset=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    from sqlalchemy import update
    await session.execute(
        update(ApiKey)
        .where(and_(ApiKey.id == key_id, ApiKey.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(ApiKey).where(and_(ApiKey.id == key_id, ApiKey.user_id == user_id))
    )
    return {"ok": True}


@router.delete("")
async def delete_all_api_keys(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(ApiKey).where(ApiKey.user_id == user_id)
    )
    return {"ok": True}


@router.post("/validate")
async def validate_api_key(
    body: ValidateApiKeyBody,
    session: AsyncSession = Depends(get_db),
):
    """Validate an API key and return the associated user."""
    if not _validate_api_key_format(body.key):
        return {"valid": False}

    key_hash = _hash_api_key(body.key)
    row = (await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )).scalar_one_or_none()
    if not row:
        return {"valid": False}
    if not row.enabled:
        return {"valid": False, "reason": "disabled"}
    # Check expiration
    if row.expires_at:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if now > row.expires_at:
            return {"valid": False, "reason": "expired"}
    # Update last_used_at.
    from sqlalchemy import update
    await session.execute(
        update(ApiKey)
        .where(ApiKey.id == row.id)
        .values(
            last_used_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    return {"valid": True, "user_id": row.user_id, "key_id": row.id}


def _generate_api_key() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "sk-lh-" + "".join(secrets.choice(alphabet) for _ in range(16))


def _validate_api_key_format(api_key: str) -> bool:
    if not api_key.startswith("sk-lh-") or len(api_key) != 22:
        return False
    allowed = string.ascii_lowercase + string.digits
    return all(char in allowed for char in api_key.removeprefix("sk-lh-"))


def _hash_api_key(api_key: str) -> str:
    if not settings.key_vaults_secret:
        raise RuntimeError(
            "`KEY_VAULTS_SECRET` is required for API key hash calculation. "
            "Run `openssl rand -base64 32` and add it to your .env."
        )
    return hmac.new(settings.key_vaults_secret.encode(), api_key.encode(), hashlib.sha256).hexdigest()


def _decrypt_api_key(encrypted_key: str) -> str:
    plaintext, ok = KeyVaultService.from_env().decrypt(encrypted_key)
    if not ok:
        raise RuntimeError(
            "Failed to decrypt API key. Please check whether KEY_VAULTS_SECRET is correct.",
        )
    return plaintext


def _key_dict(k: ApiKey, decrypted_key: str | None = None) -> dict[str, Any]:
    key = decrypted_key if decrypted_key is not None else _decrypt_api_key(k.key)

    return {
        "id": k.id,
        "name": k.name,
        "key": key,
        "enabled": k.enabled,
        "lastUsedAt": k.last_used_at.isoformat() if k.last_used_at else None,
        "expiresAt": k.expires_at.isoformat() if k.expires_at else None,
        "createdAt": k.created_at.isoformat() if k.created_at else None,
        "updatedAt": k.updated_at.isoformat() if k.updated_at else None,
        "userId": k.user_id,
    }
