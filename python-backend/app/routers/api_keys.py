"""API Keys router — personal API key CRUD."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.misc import ApiKey

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])


class CreateApiKeyBody(BaseModel):
    name: Optional[str] = None
    expires_at: Optional[datetime] = None


class UpdateApiKeyBody(BaseModel):
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
    raw_key = f"lh-{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    api_key = ApiKey(
        user_id=user_id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=body.expires_at,
    )
    session.add(api_key)
    await session.flush()
    return {"id": api_key.id, "key": raw_key, "prefix": key_prefix}


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
    values = body.model_dump(exclude_none=True)
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
    key_hash = hashlib.sha256(body.key.encode()).hexdigest()
    row = (await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )).scalar_one_or_none()
    if not row:
        return {"valid": False}
    # Check expiration
    if row.expires_at:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if now > row.expires_at:
            return {"valid": False, "reason": "expired"}
    # Update last_used_at and usage_count
    from sqlalchemy import update
    await session.execute(
        update(ApiKey)
        .where(ApiKey.id == row.id)
        .values(
            last_used_at=datetime.now(timezone.utc).replace(tzinfo=None),
            usage_count=ApiKey.usage_count + 1,
        )
    )
    return {"valid": True, "user_id": row.user_id, "key_id": row.id}


def _key_dict(k: ApiKey) -> dict[str, Any]:
    return {
        "id": k.id,
        "name": k.name,
        "prefix": k.key_prefix,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "usage_count": k.usage_count,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }
