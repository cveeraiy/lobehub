"""Phase 19 — Notifications."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_notifications(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/notifications", params={"limit": 20, "unreadOnly": True})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "content" in item
        assert "createdAt" in item
        assert "isRead" in item


@pytest.mark.asyncio
async def test_unread_count(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/notifications/unread-count")
    assert r.status_code == 200
    assert isinstance(r.json(), int)


@pytest.mark.asyncio
async def test_mark_as_read_batch(client: httpx.AsyncClient) -> None:
    r = await client.put("/api/notifications/read", json={"ids": ["00000000-0000-0000-0000-000000000000"]})
    assert r.status_code == 200
    assert r.json().get("ok") is True


@pytest.mark.asyncio
async def test_mark_all_read(client: httpx.AsyncClient) -> None:
    r = await client.put("/api/notifications/read-all")
    assert r.status_code == 200
