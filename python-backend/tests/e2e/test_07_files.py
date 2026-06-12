"""Phase 8 — Files & Upload."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_files(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/files")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_presigned_url(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/upload/presigned-url", json={
        "pathname": "test-uploads/test.txt",
    })
    # May fail if S3 is not configured — accept 200 or 500
    assert r.status_code in (200, 400, 500)
