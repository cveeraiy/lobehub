"""E2E tests for /api/admin endpoints — user management, stats, settings, permissions.

The test user 'chandra' must have admin role in Keycloak for these tests to work.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

PREFIX = "/api/admin"

# Module-level state (user_id_b from conftest — second user)
_TARGET_USER_ID: str | None = None


# ── System stats ────────────────────────────────────────────────────


async def test_system_stats(client):
    """GET /api/admin/system/stats returns global counters."""
    r = await client.get(f"{PREFIX}/system/stats")
    assert r.status_code == 200
    data = r.json()
    assert "users" in data
    assert "sessions" in data
    assert "messages" in data
    assert "topics" in data


# ── User listing ────────────────────────────────────────────────────


async def test_list_users(client):
    """GET /api/admin/users returns paginated user list."""
    r = await client.get(f"{PREFIX}/users", params={"limit": 10, "offset": 0})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_user_count(client):
    """GET /api/admin/users/count returns total count."""
    r = await client.get(f"{PREFIX}/users/count")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1


# ── User detail ─────────────────────────────────────────────────────


async def test_get_user(client, user_id):
    """GET /api/admin/users/{id} returns admin's own user."""
    r = await client.get(f"{PREFIX}/users/{user_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == user_id


async def test_get_user_nonexistent(client):
    """GET /api/admin/users/{id} for missing user returns 404."""
    r = await client.get(f"{PREFIX}/users/nonexistent-user-xxx")
    assert r.status_code == 404


async def test_get_user_stats(client, user_id):
    """GET /api/admin/users/{id}/stats returns user stats."""
    r = await client.get(f"{PREFIX}/users/{user_id}/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == user_id
    assert "messages" in data
    assert "sessions" in data
    assert "topics" in data


# ── User settings (admin view) ──────────────────────────────────────


async def test_get_user_settings(client, user_id):
    """GET /api/admin/users/{id}/settings"""
    r = await client.get(f"{PREFIX}/users/{user_id}/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["userId"] == user_id
    assert "settings" in data


async def test_update_user_settings(client, user_id):
    """PUT /api/admin/users/{id}/settings updates settings."""
    r = await client.put(
        f"{PREFIX}/users/{user_id}/settings",
        json={"general": {"language": "en-US"}},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── User permissions ────────────────────────────────────────────────


async def test_update_user_permissions(client, user_id):
    """PUT /api/admin/users/{id}/permissions"""
    r = await client.put(
        f"{PREFIX}/users/{user_id}/permissions",
        json={"permissions": {"canUseChat": True, "canUploadFiles": True}},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── User update ─────────────────────────────────────────────────────


async def test_update_user(client, user_id_b):
    """PUT /api/admin/users/{id} updates user fields."""
    global _TARGET_USER_ID
    _TARGET_USER_ID = user_id_b
    r = await client.put(
        f"{PREFIX}/users/{user_id_b}",
        json={"first_name": "AdminUpdated"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── Non-admin access ────────────────────────────────────────────────


async def test_non_admin_forbidden(client_b):
    """Non-admin user gets 403 on admin endpoints."""
    r = await client_b.get(f"{PREFIX}/users")
    assert r.status_code == 403
