"""Reusable FastAPI dependencies.

``get_current_user_id``
    Combines JWT validation with auto-provisioning: if the Keycloak user
    does not yet exist in the ``users`` table, a row is created
    automatically from JWT claims.  Returns the user's primary-key ``id``.

``require_admin``
    Same as above but raises ``403`` unless the JWT carries the ``admin``
    realm role.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TokenPayload, get_current_user
from app.db import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# Cache: user_id -> monotonic timestamp of last DB access-update.
# Prevents a SELECT+UPDATE on *every* authenticated request.
_user_seen: dict[str, float] = {}
_ACCESS_UPDATE_INTERVAL_S = 60  # update accessed_at at most once per minute


async def get_or_create_user(
    session: AsyncSession,
    token: TokenPayload,
) -> User:
    """Return existing ``User`` row or create one from JWT claims.

    Uses an in-memory cache to avoid a DB round-trip on every request.
    ``accessed_at`` is updated at most once per ``_ACCESS_UPDATE_INTERVAL_S``.
    """
    now_mono = time.monotonic()
    last_seen = _user_seen.get(token.sub)

    # Fast path: user was seen recently — skip DB entirely
    if last_seen is not None and (now_mono - last_seen) < _ACCESS_UPDATE_INTERVAL_S:
        # Return a lightweight stub; callers only use user.id
        return User(id=token.sub)  # type: ignore[call-arg]

    result = await session.execute(select(User).where(User.id == token.sub))
    user = result.scalar_one_or_none()

    if user is not None:
        # Refresh last-access timestamp (debounced)
        if last_seen is None or (now_mono - last_seen) >= _ACCESS_UPDATE_INTERVAL_S:
            user.accessed_at = datetime.now(timezone.utc)
            session.add(user)
        _user_seen[token.sub] = now_mono
        return user

    # Auto-provision new user from Keycloak claims
    user = User(
        id=token.sub,
        email=token.email,
        username=token.preferred_username,
        first_name=token.name,  # Keycloak "name" = display name
    )
    session.add(user)
    await session.flush()  # ensure PK is available to callers
    _user_seen[token.sub] = now_mono
    logger.info("Auto-provisioned user %s (%s)", user.id, user.email)
    return user


async def get_current_user_id(
    token: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> str:
    """FastAPI dependency — returns the authenticated & provisioned user ID."""
    user = await get_or_create_user(session, token)
    return user.id


async def require_admin(
    token: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> str:
    """FastAPI dependency — like ``get_current_user_id`` but requires ``admin`` role."""
    if not token.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    user = await get_or_create_user(session, token)
    return user.id
