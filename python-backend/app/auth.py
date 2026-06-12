"""Keycloak / Generic OIDC JWT authentication.

Provides ``get_current_user`` — a FastAPI dependency that:
1. Extracts the ``Authorization: Bearer <token>`` header.
2. Fetches the OIDC provider's JWKS (cached).
3. Validates the JWT signature, expiry, issuer, and audience.
4. Returns a ``TokenPayload`` with the authenticated user's claims.

Usage in a router::

    @router.get("/me")
    async def me(user: TokenPayload = Depends(get_current_user)):
        return {"user_id": user.sub}
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

# ── Bearer scheme (auto-populates OpenAPI "Authorize" button) ───────
_bearer_scheme = HTTPBearer(auto_error=True)


# ── Token payload ───────────────────────────────────────────────────
@dataclass(frozen=True)
class TokenPayload:
    """Validated claims extracted from the JWT."""

    sub: str  # Keycloak user ID
    email: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    realm_access: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def roles(self) -> list[str]:
        """Realm-level roles assigned in Keycloak."""
        return self.realm_access.get("roles", [])

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


# ── JWKS cache ──────────────────────────────────────────────────────
class _JWKSCache:
    """In-memory JWKS cache with TTL and lock to prevent thundering herd.

    Uses stale-while-revalidate: if keys exist but are expired, the first
    caller acquires the lock and refreshes while others continue using
    the stale keys.  Only blocks when no keys have ever been fetched.
    """

    def __init__(self, ttl: int = 3600) -> None:
        self._keys: dict[str, Any] | None = None
        self._fetched_at: float = 0
        self._ttl = ttl
        self._lock = asyncio.Lock()

    async def get_keys(self) -> dict[str, Any]:
        now = time.monotonic()
        expired = (now - self._fetched_at) > self._ttl

        if self._keys is not None and not expired:
            return self._keys

        # Stale-while-revalidate: if keys exist, serve stale while one
        # caller refreshes.  If no keys yet, all callers must wait.
        if self._keys is not None and expired:
            # Non-blocking attempt: only one caller refreshes
            if self._lock.locked():
                return self._keys  # another coroutine is already refreshing
            asyncio.create_task(self._locked_refresh())
            return self._keys

        # First fetch ever — must block until keys are available
        await self._locked_refresh()
        assert self._keys is not None
        return self._keys

    async def _locked_refresh(self) -> None:
        async with self._lock:
            # Double-check after acquiring lock
            if self._keys is not None and (time.monotonic() - self._fetched_at) < self._ttl:
                return
            await self._refresh()

    async def _refresh(self) -> None:
        jwks_uri = settings.auth_oidc_jwks_uri
        if not jwks_uri:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OIDC JWKS URI not configured (set AUTH_OIDC_ISSUER)",
            )
        from app.tools._http import get_client
        client = get_client()
        resp = await client.get(jwks_uri)
        resp.raise_for_status()
        self._keys = resp.json()
        self._fetched_at = time.monotonic()


_jwks_cache = _JWKSCache()


# ── Dependency ──────────────────────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> TokenPayload:
    """FastAPI dependency — validates the Bearer JWT and returns claims."""
    token = credentials.credentials
    try:
        jwks = await _jwks_cache.get_keys()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=[settings.auth_oidc_algorithms],
            audience=settings.auth_oidc_audience,
            issuer=settings.auth_oidc_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )

    return TokenPayload(
        sub=sub,
        email=payload.get("email"),
        name=payload.get("name"),
        preferred_username=payload.get("preferred_username"),
        realm_access=payload.get("realm_access", {}),
        raw=payload,
    )
