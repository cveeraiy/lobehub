"""Keycloak OIDC authentication endpoints for the SPA frontend.

Implements the subset of Better Auth API that the SPA client SDK expects:
- GET  /api/auth/get-session  — session check (cookie-based)
- POST /api/auth/sign-in/social — initiate Keycloak OAuth redirect
- GET  /api/auth/callback/keycloak — OAuth callback (code exchange)
- POST /api/auth/sign-out — destroy session
- POST /api/auth/check-user — check if email exists in DB
- POST /api/auth/resolve-username — resolve username to email

Session management uses signed cookies (itsdangerous) to store the
user ID and session metadata. The session cookie is HttpOnly and
Lax-sameSite for CSRF protection.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# ── Session cookie management ─────────────────────────────────────────

SESSION_COOKIE_NAME = "lobehub_session"
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 days

_serializer = URLSafeTimedSerializer(settings.session_secret)

# In-memory OIDC state store (nonce → {callback_url, created_at})
# In production, use Redis or DB. Fine for single-process dev.
_oidc_states: dict[str, dict[str, Any]] = {}


def _create_session_cookie(user_data: dict[str, Any]) -> str:
    """Create a signed session cookie value."""
    return _serializer.dumps(user_data)


def _read_session_cookie(cookie_value: str) -> Optional[dict[str, Any]]:
    """Read and validate a signed session cookie. Returns None if invalid/expired."""
    try:
        return _serializer.loads(cookie_value, max_age=SESSION_MAX_AGE)
    except (BadSignature, Exception):
        return None


def _set_session_cookie(response: Response, user_data: dict[str, Any]) -> None:
    """Set the session cookie on a response."""
    cookie_value = _create_session_cookie(user_data)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,  # secure=False for localhost dev
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    """Remove the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _get_session_from_request(request: Request) -> Optional[dict[str, Any]]:
    """Extract session data from the request cookie."""
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_value:
        return None
    return _read_session_cookie(cookie_value)


# ── Keycloak OIDC helpers ─────────────────────────────────────────────

def _get_oidc_config() -> dict[str, str]:
    """Build OIDC endpoint URLs from the issuer."""
    issuer = settings.auth_oidc_issuer
    if not issuer:
        raise ValueError("AUTH_OIDC_ISSUER is not configured")
    issuer = issuer.rstrip("/")
    return {
        "authorization_endpoint": f"{issuer}/protocol/openid-connect/auth",
        "token_endpoint": f"{issuer}/protocol/openid-connect/token",
        "userinfo_endpoint": f"{issuer}/protocol/openid-connect/userinfo",
        "end_session_endpoint": f"{issuer}/protocol/openid-connect/logout",
        "jwks_uri": f"{issuer}/protocol/openid-connect/certs",
    }


async def _exchange_code_for_tokens(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for tokens at Keycloak's token endpoint."""
    oidc = _get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            oidc["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.auth_oidc_client_id,
                "client_secret": settings.auth_oidc_client_secret or "",
            },
        )
        resp.raise_for_status()
        return resp.json()


def _decode_id_token_unverified(id_token: str) -> dict[str, Any]:
    """Decode the ID token payload without signature verification.
    We already trust Keycloak since we just exchanged the code over a direct HTTPS call."""
    # Use jose to decode without verification
    return jwt.get_unverified_claims(id_token)


async def _get_or_create_user(
    session: AsyncSession, claims: dict[str, Any]
) -> User:
    """Find or create user from OIDC claims."""
    sub = claims.get("sub")
    if not sub:
        raise ValueError("Token missing 'sub' claim")

    result = await session.execute(select(User).where(User.id == sub))
    user = result.scalar_one_or_none()

    if user is not None:
        # Update fields from latest token
        user.email = claims.get("email", user.email)
        user.first_name = claims.get("name", user.first_name)
        user.username = claims.get("preferred_username", user.username)
        user.accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(user)
        await session.flush()
        return user

    # Auto-provision new user
    user = User(
        id=sub,
        email=claims.get("email"),
        username=claims.get("preferred_username"),
        first_name=claims.get("name"),
    )
    session.add(user)
    await session.flush()
    logger.info("Auto-provisioned user %s (%s) via OIDC login", user.id, user.email)
    return user


def _user_to_session_data(user: User, claims: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert a User model to session data for the cookie."""
    # Extract roles from Keycloak realm_access
    roles: list[str] = []
    if claims:
        realm_access = claims.get("realm_access", {})
        roles = realm_access.get("roles", [])

    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.first_name,
        "username": user.username,
        "roles": roles,
        "created_at": int(time.time()),
    }


def _resolve_role(keycloak_roles: list[str]) -> str:
    """Map Keycloak realm roles to a Better Auth role string.

    The SPA checks ``session.user.role === 'admin' || session.user.role === 'super_admin'``
    to show admin-only features (admin panel, agent/system settings for all users).
    """
    if "super_admin" in keycloak_roles:
        return "super_admin"
    if "admin" in keycloak_roles:
        return "admin"
    return "user"


def _session_to_better_auth_response(session_data: dict[str, Any]) -> dict[str, Any]:
    """Format session data as a Better Auth compatible response.
    This is what the SPA's useSession() hook expects."""
    session_id = hashlib.sha256(
        f"{session_data['user_id']}:{session_data.get('created_at', '')}".encode()
    ).hexdigest()[:24]

    return {
        "session": {
            "id": session_id,
            "userId": session_data["user_id"],
            "token": session_id,  # Better Auth uses this as a session token
            "expiresAt": int(time.time()) + SESSION_MAX_AGE,
        },
        "user": {
            "id": session_data["user_id"],
            "name": session_data.get("name") or session_data.get("username", ""),
            "email": session_data.get("email", ""),
            "username": session_data.get("username"),
            "image": None,
            "emailVerified": True,
            "role": _resolve_role(session_data.get("roles", [])),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    }


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/api/auth/get-session")
async def get_session(request: Request):
    """Check if the user has a valid session. Called by useSession() on every page load."""
    session_data = _get_session_from_request(request)
    if not session_data:
        return JSONResponse(content=None, status_code=200)

    return _session_to_better_auth_response(session_data)


async def _initiate_oidc_login(request: Request) -> JSONResponse:
    """Shared logic for initiating a Keycloak OIDC redirect.

    Works for both /api/auth/sign-in/social and /api/auth/sign-in/oauth2.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    callback_url = body.get("callbackURL", "/")
    oidc = _get_oidc_config()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(16)

    # The SPA frontend URL where the user came from
    redirect_uri = f"{settings.app_url}/api/auth/callback/keycloak"

    # Store state for validation in callback
    _oidc_states[state] = {
        "callback_url": callback_url,
        "nonce": nonce,
        "created_at": time.time(),
    }

    # Clean up old states (older than 10 minutes)
    cutoff = time.time() - 600
    expired = [k for k, v in _oidc_states.items() if v["created_at"] < cutoff]
    for k in expired:
        del _oidc_states[k]

    params = {
        "client_id": settings.auth_oidc_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": settings.auth_oidc_scopes,
        "state": state,
        "nonce": nonce,
    }

    auth_url = f"{oidc['authorization_endpoint']}?{urlencode(params)}"

    return JSONResponse(content={
        "url": auth_url,
        "redirect": True,
    })


@router.post("/api/auth/sign-in/social")
async def sign_in_social(request: Request):
    """Initiate Keycloak OIDC login. Called by signIn.social({provider: 'keycloak'})."""
    return await _initiate_oidc_login(request)


@router.post("/api/auth/sign-in/oauth2")
async def sign_in_oauth2(request: Request):
    """Initiate Keycloak OIDC login. Called by signIn.oauth2({providerId: 'keycloak'}).

    The SPA uses this endpoint for non-builtin (generic OIDC) providers.
    """
    return await _initiate_oidc_login(request)


@router.get("/api/auth/callback/keycloak")
async def oauth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Handle Keycloak OAuth callback. Exchanges code for tokens, creates session."""
    if error:
        logger.error("OIDC callback error: %s", error)
        return RedirectResponse(url="/signin?error=oauth_error")

    if not code or not state:
        return RedirectResponse(url="/signin?error=missing_params")

    # Validate state
    state_data = _oidc_states.pop(state, None)
    if state_data is None:
        logger.warning("Invalid OIDC state parameter")
        return RedirectResponse(url="/signin?error=invalid_state")

    callback_url = state_data.get("callback_url", "/")
    redirect_uri = f"{settings.app_url}/api/auth/callback/keycloak"

    try:
        # Exchange code for tokens
        tokens = await _exchange_code_for_tokens(code, redirect_uri)
        id_token = tokens.get("id_token")
        if not id_token:
            logger.error("No id_token in token response")
            return RedirectResponse(url="/signin?error=no_id_token")

        # Decode claims from the ID token
        claims = _decode_id_token_unverified(id_token)

        # Get or create user in the database
        user = await _get_or_create_user(db, claims)
        await db.commit()

        # Create session
        session_data = _user_to_session_data(user, claims)

        # Redirect to the callback URL with session cookie set
        response = RedirectResponse(url=callback_url, status_code=302)
        _set_session_cookie(response, session_data)
        return response

    except httpx.HTTPStatusError as exc:
        logger.error("OIDC token exchange failed: %s %s", exc.response.status_code, exc.response.text)
        return RedirectResponse(url="/signin?error=token_exchange_failed")
    except Exception as exc:
        logger.exception("OIDC callback error: %s", exc)
        return RedirectResponse(url="/signin?error=internal_error")


@router.post("/api/auth/sign-out")
async def sign_out(request: Request):
    """Destroy session and optionally redirect to Keycloak logout."""
    response = JSONResponse(content={"success": True})
    _clear_session_cookie(response)
    return response


@router.post("/oidc/clear-session")
async def oidc_clear_session():
    """Called by the SPA before sign-out to clear the OIDC provider session.

    For Keycloak, we could redirect to the end_session_endpoint, but since
    this is a background fetch (not a navigation), we just acknowledge it.
    """
    return JSONResponse(content={"ok": True, "cleared": True})


@router.post("/api/auth/check-user")
async def check_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Check if a user with the given email exists in the database."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(content={"exists": False, "error": "Invalid body"}, status_code=400)

    email = body.get("email")
    if not email or not isinstance(email, str):
        return JSONResponse(content={"exists": False, "error": "Email is required"}, status_code=400)

    result = await db.execute(
        select(User.id).where(User.email == email.lower().strip())
    )
    user = result.scalar_one_or_none()

    if not user:
        return JSONResponse(content={"exists": False})

    # With Keycloak auth, users don't have local passwords — they always use SSO
    return JSONResponse(content={"exists": True, "hasPassword": False})


@router.post("/api/auth/resolve-username")
async def resolve_username(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resolve a username to an email address."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(content={"exists": False, "error": "Invalid body"}, status_code=400)

    username = body.get("username")
    if not username or not isinstance(username, str):
        return JSONResponse(content={"exists": False, "error": "Username is required"}, status_code=400)

    result = await db.execute(
        select(User.email).where(User.username == username.strip())
    )
    email = result.scalar_one_or_none()

    if not email:
        return JSONResponse(content={"exists": False})

    return JSONResponse(content={"exists": True, "email": email})


@router.get("/api/auth/list-accounts")
async def list_accounts(request: Request):
    """List linked accounts for the current user.

    Returns the Keycloak account if the user is signed in.
    """
    session_data = _get_session_from_request(request)
    if not session_data:
        return JSONResponse(content=[])

    # Return the Keycloak account as the only linked account
    return JSONResponse(content=[
        {
            "id": f"keycloak-{session_data['user_id']}",
            "accountId": session_data["user_id"],
            "providerId": "keycloak",
            "userId": session_data["user_id"],
        }
    ])


@router.get("/api/auth/account-info")
async def account_info(request: Request):
    """Get account info for a specific account. Used by the auth providers list."""
    session_data = _get_session_from_request(request)
    if not session_data:
        return JSONResponse(content={"data": None})

    return JSONResponse(content={
        "data": {
            "user": {
                "id": session_data["user_id"],
                "email": session_data.get("email"),
                "name": session_data.get("name"),
            }
        }
    })


@router.post("/api/auth/change-email")
async def change_email(request: Request, db: AsyncSession = Depends(get_db)):
    """Better Auth compatible: change user email."""
    session_data = _get_session_from_request(request)
    if not session_data:
        return JSONResponse(content={"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    new_email = body.get("newEmail", "").strip()
    if not new_email:
        return JSONResponse(content={"error": "newEmail required"}, status_code=400)
    user_id = session_data["user_id"]
    from sqlalchemy import update as sql_update
    await db.execute(sql_update(User).where(User.id == user_id).values(email=new_email))
    await db.commit()
    return {"status": True}


@router.get("/api/auth/ok")
async def auth_health():
    """Health check for auth subsystem."""
    return {"status": "ok", "provider": "keycloak"}


# ── Better Auth admin-compatible endpoints ────────────────────────────

def _require_admin_session(request: Request) -> dict[str, Any]:
    """Extract session and verify admin role. Raises 403 if not admin."""
    session_data = _get_session_from_request(request)
    if not session_data:
        raise _http_error(401, "Not authenticated")
    role = _resolve_role(session_data.get("roles", []))
    if role not in ("admin", "super_admin"):
        raise _http_error(403, "Admin access required")
    return session_data


def _http_error(status: int, message: str):
    from fastapi import HTTPException
    return HTTPException(status_code=status, detail=message)


def _user_to_admin_response(user: User) -> dict[str, Any]:
    """Map a User row to the Better Auth admin user shape."""
    return {
        "id": user.id,
        "name": user.first_name or user.username or "",
        "email": user.email or "",
        "image": user.avatar,
        "role": "user",
        "banned": user.is_banned or False,
        "banReason": user.ban_reason,
        "banExpires": user.ban_expires_at.isoformat() if user.ban_expires_at else None,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.get("/api/auth/admin/list-users")
async def admin_list_users(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Better Auth compatible: list users for admin panel."""
    _require_admin_session(request)
    from sqlalchemy import func
    stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    total_result = await db.execute(select(func.count()).select_from(User))
    total = total_result.scalar() or 0
    return {"users": [_user_to_admin_response(u) for u in users], "total": total}


@router.post("/api/auth/admin/set-role")
async def admin_set_role(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Better Auth compatible: set user role (no-op — roles come from Keycloak)."""
    _require_admin_session(request)
    return {"success": True}


@router.post("/api/auth/admin/ban-user")
async def admin_ban_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Better Auth compatible: ban a user."""
    _require_admin_session(request)
    body = await request.json()
    user_id = body.get("userId")
    if not user_id:
        raise _http_error(400, "userId required")
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(User).where(User.id == user_id).values(
            is_banned=True,
            ban_reason=body.get("banReason"),
        )
    )
    await db.commit()
    return {"success": True}


@router.post("/api/auth/admin/unban-user")
async def admin_unban_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Better Auth compatible: unban a user."""
    _require_admin_session(request)
    body = await request.json()
    user_id = body.get("userId")
    if not user_id:
        raise _http_error(400, "userId required")
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(User).where(User.id == user_id).values(
            is_banned=False, ban_reason=None, ban_expires_at=None,
        )
    )
    await db.commit()
    return {"success": True}


@router.post("/api/auth/admin/remove-user")
async def admin_remove_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Better Auth compatible: delete a user."""
    _require_admin_session(request)
    body = await request.json()
    user_id = body.get("userId")
    if not user_id:
        raise _http_error(400, "userId required")
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(User).where(User.id == user_id))
    await db.commit()
    return {"success": True}


@router.get("/api/__server_config__")
async def server_config():
    """Provide SPAServerConfig for the auth layout.

    The SPA auth pages fetch this to get oAuthSSOProviders and feature flags
    so the sign-in page can render the correct SSO buttons.
    """
    from app.feature_flags import get_feature_flags

    oauth_sso_providers: list[str] = []
    if settings.auth_oidc_issuer:
        oauth_sso_providers.append("keycloak")

    ff = get_feature_flags()

    return {
        "analyticsConfig": {},
        "clientEnv": {},
        "config": {
            "telemetry": {},
            "defaultAgent": {},
            "languageModel": {},
            "oAuthSSOProviders": oauth_sso_providers,
            "disableEmailPassword": settings.auth_disable_email_password,
        },
        "featureFlags": ff.to_camel_dict(),
        "isMobile": False,
    }
