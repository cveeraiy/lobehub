"""Phase 19 — Notifications."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_notifications(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/notifications")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_mark_all_read(client: httpx.AsyncClient) -> None:
    r = await client.put("/api/notifications/read-all")
    assert r.status_code == 200
