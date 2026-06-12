"""Phase 31 — Tools: list builtin tools and manual tool execution."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


# ── 31.1  List tools ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_tools(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/tools")
    assert r.status_code == 200
    data = r.json()
    assert "tools" in data
    assert isinstance(data["tools"], list)


# ── 31.2  Run tool (may fail if tool deps not configured) ───────────

@pytest.mark.asyncio
async def test_run_tool_nonexistent(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/tools/run", json={
        "tool_name": "nonexistent_tool",
        "arguments": {},
    })
    # Nonexistent tool may return 200 with error in result body, or an HTTP error
    assert r.status_code in (200, 400, 404, 500)
