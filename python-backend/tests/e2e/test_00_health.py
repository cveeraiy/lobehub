"""Phase 1 — Health, Auth & Config: Keycloak JWT auth, health check."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


# ── 1.1  Health check (no auth required) ─────────────────────────────

@pytest.mark.asyncio
async def test_health_check(unauthed_client: httpx.AsyncClient) -> None:
    r = await unauthed_client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


# ── 1.2  Keycloak JWT auth succeeds on /api/user/state ───────────────

@pytest.mark.asyncio
async def test_jwt_auth_succeeds(client: httpx.AsyncClient, user_id: str) -> None:
    r = await client.get("/api/user/state")
    assert r.status_code == 200
    data = r.json()
    assert data["userId"] == user_id


# ── 1.3  Missing auth → 401 / 403 ───────────────────────────────────

@pytest.mark.asyncio
async def test_missing_auth_returns_401(unauthed_client: httpx.AsyncClient) -> None:
    r = await unauthed_client.get("/api/user/state")
    assert r.status_code in (401, 403)


# ── 1.4  Invalid JWT → 401 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_jwt_returns_401(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as c:
        r = await c.get(
            "/api/user/state",
            headers={"Authorization": "Bearer totally-bogus-jwt-token"},
        )
        assert r.status_code == 401


# ── 1.5  Server version (no auth required) ──────────────────────────

@pytest.mark.asyncio
async def test_server_version(unauthed_client: httpx.AsyncClient) -> None:
    r = await unauthed_client.get("/api/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data


# ── 1.6  Server config (no auth required) ────────────────────────────

@pytest.mark.asyncio
async def test_server_config(unauthed_client: httpx.AsyncClient) -> None:
    r = await unauthed_client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "featureFlags" in data or "serverConfig" in data
