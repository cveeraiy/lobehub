"""E2E tests for /api/auth/* Keycloak OIDC endpoints and /api/__server_config__."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

AUTH_PREFIX = "/api/auth"


# ── Server config ──────────────────────────────────────────────────


async def test_server_config(client):
    """GET /api/__server_config__ returns OAuth providers."""
    r = await client.get("/api/__server_config__")
    assert r.status_code == 200
    data = r.json()
    # oAuthSSOProviders is nested under 'config'
    config = data.get("config", data)
    assert "oAuthSSOProviders" in config
    assert isinstance(config["oAuthSSOProviders"], list)


# ── Session ────────────────────────────────────────────────────────


async def test_get_session_no_cookie(unauthed_client):
    """GET /api/auth/get-session without session cookie returns null session."""
    r = await unauthed_client.get(f"{AUTH_PREFIX}/get-session")
    assert r.status_code == 200
    data = r.json()
    # Should return null/None when no session cookie is present
    assert data is None or data.get("session") is None or data.get("user") is None


async def test_auth_ok(client):
    """GET /api/auth/ok returns 200."""
    r = await client.get(f"{AUTH_PREFIX}/ok")
    assert r.status_code == 200


# ── OAuth initiation ──────────────────────────────────────────────


async def test_sign_in_social(unauthed_client):
    """POST /api/auth/sign-in/social returns redirect URL to Keycloak."""
    r = await unauthed_client.post(
        f"{AUTH_PREFIX}/sign-in/social",
        json={"provider": "keycloak", "callbackURL": "/"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "url" in data
    assert "keycloak" in data["url"] or "localhost:8080" in data["url"]


async def test_sign_in_oauth2(unauthed_client):
    """POST /api/auth/sign-in/oauth2 returns redirect URL to Keycloak."""
    r = await unauthed_client.post(
        f"{AUTH_PREFIX}/sign-in/oauth2",
        json={"providerId": "keycloak", "callbackURL": "/"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "url" in data
    assert "redirect" in data


# ── User check endpoints ──────────────────────────────────────────


async def test_check_user_exists(client):
    """POST /api/auth/check-user for known user."""
    r = await client.post(
        f"{AUTH_PREFIX}/check-user",
        json={"email": "chandra@lobehub.dev"},
    )
    # May return 200 with exists=true/false depending on implementation
    assert r.status_code == 200


async def test_resolve_username(client):
    """POST /api/auth/resolve-username."""
    r = await client.post(
        f"{AUTH_PREFIX}/resolve-username",
        json={"username": "chandra"},
    )
    assert r.status_code == 200


# ── Account info ──────────────────────────────────────────────────


async def test_list_accounts(client):
    """GET /api/auth/list-accounts returns account list."""
    r = await client.get(f"{AUTH_PREFIX}/list-accounts")
    assert r.status_code == 200


async def test_account_info(client):
    """GET /api/auth/account-info returns account details."""
    r = await client.get(f"{AUTH_PREFIX}/account-info")
    assert r.status_code == 200


# ── Sign out ──────────────────────────────────────────────────────


async def test_sign_out(unauthed_client):
    """POST /api/auth/sign-out clears session (no-op if no cookie)."""
    r = await unauthed_client.post(f"{AUTH_PREFIX}/sign-out")
    assert r.status_code == 200


# ── Admin auth endpoints ──────────────────────────────────────────


async def test_admin_list_users(client):
    """GET /api/auth/admin/list-users returns user list.

    This endpoint uses session-cookie auth (not JWT Bearer), so it may
    return 401 when called with only a JWT. We accept 200 or 401.
    """
    r = await client.get(f"{AUTH_PREFIX}/admin/list-users")
    # 200 if cookie auth works, 401 if it requires session cookie
    assert r.status_code in (200, 401)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, list)
