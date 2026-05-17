"""E2E tests for /api/market — local market agent install/list/uninstall.

Does NOT test /api/discover or /api/social (external proxy endpoints).
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

MARKET_PREFIX = "/api/market"

# Module-level state
_AGENT_IDENTIFIER: str = "test-market-agent-e2e"


# ── Install agent ──────────────────────────────────────────────────


async def test_install_agent(client):
    """POST /api/market/agents/install installs an agent from marketplace."""
    r = await client.post(
        f"{MARKET_PREFIX}/agents/install",
        json={
            "identifier": _AGENT_IDENTIFIER,
            "title": "Market Test Agent",
            "description": "An agent installed from the test marketplace.",
            "avatar": "https://example.com/avatar.png",
            "system_role": "You are a helpful assistant.",
            "model": "gpt-4o",
            "tags": ["test", "e2e"],
        },
    )
    assert r.status_code == 201, f"Install failed: {r.text}"
    data = r.json()
    assert data.get("identifier") == _AGENT_IDENTIFIER or "id" in data


# ── List market agents ─────────────────────────────────────────────


async def test_list_market_agents(client):
    """GET /api/market/agents lists installed market agents."""
    r = await client.get(f"{MARKET_PREFIX}/agents")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(
        a.get("identifier") == _AGENT_IDENTIFIER or a.get("slug") == _AGENT_IDENTIFIER
        for a in data
    )


# ── Uninstall agent ────────────────────────────────────────────────


async def test_uninstall_agent(client):
    """DELETE /api/market/agents/{identifier} removes installed agent."""
    r = await client.delete(f"{MARKET_PREFIX}/agents/{_AGENT_IDENTIFIER}")
    assert r.status_code == 200


async def test_uninstall_nonexistent(client):
    """DELETE /api/market/agents/{identifier} for nonexistent is idempotent."""
    r = await client.delete(f"{MARKET_PREFIX}/agents/nonexistent-agent-xxx")
    assert r.status_code in (200, 404)
