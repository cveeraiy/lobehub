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


async def test_get_onboarding_agents(client):
    """GET /api/market/agent/onboarding-full supports REST onboarding clients."""
    r = await client.get(f"{MARKET_PREFIX}/agent/onboarding-full")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


async def test_market_publish_and_fork_endpoints(client):
    """Market publish/fork endpoints used by the REST frontend service are available."""
    identifier = "rest-market-agent-extra"
    create = await client.post(
        f"{MARKET_PREFIX}/agent",
        json={"identifier": identifier, "name": "REST Market Agent"},
    )
    assert create.status_code == 200, create.text
    assert create.json()["identifier"] == identifier

    detail = await client.get(f"{MARKET_PREFIX}/agent/detail", params={"identifier": identifier})
    assert detail.status_code == 200, detail.text
    assert detail.json()["identifier"] == identifier

    version = await client.post(
        f"{MARKET_PREFIX}/agent/version",
        json={"identifier": identifier, "version": "1.0.0"},
    )
    assert version.status_code == 200, version.text
    assert version.json()["success"] is True

    for action in ("publish", "unpublish", "deprecate"):
        r = await client.post(f"{MARKET_PREFIX}/agent/{action}", json={"identifier": identifier})
        assert r.status_code == 200, f"{action} failed: {r.text}"
        assert r.json()["success"] is True

    own = await client.get(f"{MARKET_PREFIX}/agent/own")
    assert own.status_code == 200, own.text
    assert isinstance(own.json().get("items"), list)

    fork = await client.post(
        f"{MARKET_PREFIX}/agent/fork",
        json={"sourceIdentifier": identifier, "name": "Forked REST Market Agent"},
    )
    assert fork.status_code == 200, fork.text
    assert fork.json()["success"] is True

    forks = await client.get(f"{MARKET_PREFIX}/agent/forks", params={"identifier": identifier})
    assert forks.status_code == 200, forks.text

    source = await client.get(
        f"{MARKET_PREFIX}/agent/fork-source",
        params={"identifier": identifier},
    )
    assert source.status_code == 200, source.text


async def test_market_agent_group_and_skill_endpoints(client):
    """Agent group and skill endpoints used by the REST frontend service are available."""
    identifier = "rest-market-group-extra"
    detail = await client.get(
        f"{MARKET_PREFIX}/agent-group/detail",
        params={"identifier": identifier},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["identifier"] == identifier

    publish_or_create = await client.post(
        f"{MARKET_PREFIX}/agent-group/publish-or-create",
        json={"description": "Group", "identifier": identifier, "member_agents": [], "name": "Group"},
    )
    assert publish_or_create.status_code == 200, publish_or_create.text
    assert publish_or_create.json()["success"] is True

    for action in ("publish", "unpublish", "deprecate"):
        r = await client.post(
            f"{MARKET_PREFIX}/agent-group/{action}",
            json={"identifier": identifier},
        )
        assert r.status_code == 200, f"{action} failed: {r.text}"
        assert r.json()["success"] is True

    fork = await client.post(
        f"{MARKET_PREFIX}/agent-group/fork",
        json={"sourceIdentifier": identifier},
    )
    assert fork.status_code == 200, fork.text
    assert fork.json()["success"] is True

    forks = await client.get(
        f"{MARKET_PREFIX}/agent-group/forks",
        params={"identifier": identifier},
    )
    assert forks.status_code == 200, forks.text

    source = await client.get(
        f"{MARKET_PREFIX}/agent-group/fork-source",
        params={"identifier": identifier},
    )
    assert source.status_code == 200, source.text

    skills = await client.get(f"{MARKET_PREFIX}/skill/list")
    assert skills.status_code == 200, skills.text
    assert isinstance(skills.json().get("items"), list)


# ── Uninstall agent ────────────────────────────────────────────────


async def test_uninstall_agent(client):
    """DELETE /api/market/agents/{identifier} removes installed agent."""
    r = await client.delete(f"{MARKET_PREFIX}/agents/{_AGENT_IDENTIFIER}")
    assert r.status_code == 200


async def test_uninstall_nonexistent(client):
    """DELETE /api/market/agents/{identifier} for nonexistent is idempotent."""
    r = await client.delete(f"{MARKET_PREFIX}/agents/nonexistent-agent-xxx")
    assert r.status_code in (200, 404)


async def test_submit_feedback(client):
    """POST /api/market/feedback accepts user feedback through REST."""
    r = await client.post(
        f"{MARKET_PREFIX}/feedback",
        json={
            "client_info": {
                "language": "en-US",
                "timezone": "America/Chicago",
                "url": "https://example.com/settings",
                "user_agent": "pytest",
            },
            "email": "tester@example.com",
            "message": "REST feedback body",
            "screenshot_url": "https://example.com/screenshot.png",
            "title": "REST feedback",
        },
    )
    assert r.status_code == 200, f"Feedback failed: {r.text}"
    assert r.json() == {"success": True}
