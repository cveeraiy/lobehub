"""Phase 2 — User CRUD: state, settings, avatar, username, preference."""

from __future__ import annotations

import httpx
import pytest

from .conftest import SharedState

pytestmark = pytest.mark.e2e


# ── 2.1  Get user state (auto-creates user) ─────────────────────────

@pytest.mark.asyncio
async def test_get_user_state(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/user/state")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


# ── 2.2  Update user settings ────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_settings(client: httpx.AsyncClient) -> None:
    r = await client.put(
        "/api/user/settings",
        json={"language": "en-US", "themeMode": "dark"},
    )
    assert r.status_code == 200


# ── 2.3  Update avatar ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_avatar(client: httpx.AsyncClient) -> None:
    r = await client.put(
        "/api/user/avatar",
        json={"avatar": "https://example.com/avatar.png"},
    )
    assert r.status_code == 200


# ── 2.4  Update username ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_username(client: httpx.AsyncClient) -> None:
    r = await client.put(
        "/api/user/username",
        json={"username": "e2e-test-user"},
    )
    assert r.status_code == 200


# ── 2.5  Update fullname ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_fullname(client: httpx.AsyncClient) -> None:
    r = await client.put(
        "/api/user/fullname",
        json={"fullName": "E2E Test User"},
    )
    assert r.status_code == 200


# ── 2.6  Update preference ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_preference(client: httpx.AsyncClient) -> None:
    r = await client.put(
        "/api/user/preference",
        json={"useCmdEnterToSend": True},
    )
    assert r.status_code == 200


# ── 2.7  Mark user onboarded ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_onboarded(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/user/onboarded")
    assert r.status_code == 200


# ── 2.8  Reset settings ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_settings(client: httpx.AsyncClient) -> None:
    r = await client.delete("/api/user/settings")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_patch_onboarding_document_applies_line_hunk(client: httpx.AsyncClient) -> None:
    await client.put(
        "/api/user/onboarding/document",
        json={"content": "one\ntwo\nthree\n", "type": "persona"},
    )

    r = await client.patch(
        "/api/user/onboarding/document",
        json={
            "hunks": [{"content": "TWO", "endLine": 2, "mode": "replaceLines", "startLine": 2}],
            "type": "persona",
        },
    )

    assert r.status_code == 200
    data = r.json()
    assert data["applied"] == 1
    assert data["type"] == "persona"

    read = await client.get("/api/user/onboarding/document", params={"type": "persona"})
    assert read.status_code == 200
    assert read.json()["content"] == "one\nTWO\nthree\n"


@pytest.mark.asyncio
async def test_patch_onboarding_document_returns_structured_error(
    client: httpx.AsyncClient,
) -> None:
    await client.put(
        "/api/user/onboarding/document",
        json={"content": "same\nsame\n", "type": "persona"},
    )

    r = await client.patch(
        "/api/user/onboarding/document",
        json={"hunks": [{"replace": "other", "search": "same"}], "type": "persona"},
    )

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["success"] is False
    assert detail["error"]["code"] == "HUNK_AMBIGUOUS"
