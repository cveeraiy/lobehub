"""Reusable FastAPI dependencies.

``get_current_user_id``
    Combines JWT validation with auto-provisioning: if the Keycloak user
    does not yet exist in the ``users`` table, a row is created
    automatically from JWT claims.  Returns the user's primary-key ``id``.

    Also supports **internal service token auth**: when the request carries
    ``X-Service-Token`` matching ``PYTHON_BACKEND_SERVICE_TOKEN``, the
    ``X-Internal-User-Id`` header is trusted directly (no JWT required).
    This enables the TS backend to proxy requests on behalf of users.

``require_admin``
    Same as above but raises ``403`` unless the JWT carries the ``admin``
    realm role.
"""

from __future__ import annotations

import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TokenPayload, get_current_user
from app.config import settings
from app.db import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# Cache: user_id -> monotonic timestamp of last DB access-update.
# Prevents a SELECT+UPDATE on *every* authenticated request.
_user_seen: dict[str, float] = {}
_ACCESS_UPDATE_INTERVAL_S = 60  # update accessed_at at most once per minute


def _validate_service_token(request: Request) -> Optional[str]:
    """Check for internal service token auth.

    Returns the user ID from ``X-Internal-User-Id`` if the service token
    is valid, or ``None`` if no service token headers are present.
    Raises 401 if a service token is provided but invalid.
    """
    service_token = request.headers.get("x-service-token")
    if not service_token:
        return None

    expected = settings.python_backend_service_token
    if not expected:
        # Service token auth is not configured — fall through to JWT
        return None

    if not hmac.compare_digest(service_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )

    user_id = request.headers.get("x-internal-user-id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Internal-User-Id header required with service token auth",
        )
    return user_id


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
            user.accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
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


async def _ensure_user_exists(session: AsyncSession, user_id: str) -> str:
    """Ensure the user row exists (for service-token auth where we only have an ID)."""
    now_mono = time.monotonic()
    last_seen = _user_seen.get(user_id)

    if last_seen is not None and (now_mono - last_seen) < _ACCESS_UPDATE_INTERVAL_S:
        return user_id

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is not None:
        if last_seen is None or (now_mono - last_seen) >= _ACCESS_UPDATE_INTERVAL_S:
            user.accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(user)
        _user_seen[user_id] = now_mono
        return user_id

    # Auto-provision with minimal info (TS backend already validated)
    user = User(id=user_id)
    session.add(user)
    await session.flush()
    _user_seen[user_id] = now_mono
    logger.info("Auto-provisioned user %s (via service token)", user_id)
    return user_id


async def get_current_user_id(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> str:
    """FastAPI dependency — returns the authenticated & provisioned user ID.

    Supports three auth methods (tried in order):
    1. **Internal service token** — ``X-Service-Token`` + ``X-Internal-User-Id``
       headers from the TS backend proxy.
    2. **Session cookie** — signed ``lobehub_session`` cookie set by the
       Keycloak OIDC callback in ``app.routers.auth``.
    3. **OIDC JWT** — standard ``Authorization: Bearer <token>``.
    """
    # Try internal service token first
    proxied_user_id = _validate_service_token(request)
    if proxied_user_id is not None:
        return await _ensure_user_exists(session, proxied_user_id)

    # Try session cookie (set by Keycloak login flow)
    cookie_user_id = _validate_session_cookie(request)
    if cookie_user_id is not None:
        return await _ensure_user_exists(session, cookie_user_id)

    # Fall back to OIDC JWT
    token = await get_current_user(
        credentials=await _extract_bearer(request),
    )
    user = await get_or_create_user(session, token)
    return user.id


def _validate_session_cookie(request: Request) -> Optional[str]:
    """Check the signed ``lobehub_session`` cookie and return the user_id if valid."""
    from app.routers.auth import _get_session_from_request

    session_data = _get_session_from_request(request)
    if session_data is None:
        return None
    user_id = session_data.get("user_id")
    if not user_id or not isinstance(user_id, str):
        return None
    return user_id


async def _extract_bearer(request: Request):
    """Extract bearer credentials from request (reuses the HTTPBearer scheme)."""
    from app.auth import _bearer_scheme
    return await _bearer_scheme(request)


async def require_admin(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> str:
    """FastAPI dependency — like ``get_current_user_id`` but requires ``admin`` role.

    Note: service-token auth does not carry role info, so admin endpoints
    always require a real JWT.
    """
    token = await get_current_user(
        credentials=await _extract_bearer(request),
    )
    if not token.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    user = await get_or_create_user(session, token)
    return user.id
