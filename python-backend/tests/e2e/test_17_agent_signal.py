"""Phase 18 — Agent Signal: policies, emit, cleanup."""

from __future__ import annotations
import time

import httpx
import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_list_policies(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/agent-signal/policies")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_policy(client: httpx.AsyncClient) -> None:
    policy_id = f"e2e-policy-{int(time.time())}"
    r = await client.post("/api/agent-signal/policies", json={
        "id": policy_id,
        "name": policy_id,
        "signal_type": "agent.user.message",
        "action_type": "log",
        "config": {},
    })
    assert r.status_code in (200, 201)


@pytest.mark.asyncio
async def test_emit_signal(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/agent-signal/emit", json={
        "source": "e2e-test",
        "type": "agent.user.message",
        "payload": {"test": True},
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_signals(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/agent-signal/cleanup")
    assert r.status_code == 200
