"""E2E tests for /api/follow-up — follow-up action extraction via LLM.

Requires a working LLM backend (Bedrock) and an existing topic with messages.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

FOLLOW_UP_PREFIX = "/api/follow-up"

# Module-level state
_SESSION_ID: str | None = None
_TOPIC_ID: str | None = None
_MESSAGE_ID: str | None = None


# ── Setup ──────────────────────────────────────────────────────────


async def test_setup_session(client):
    """Create a session for follow-up tests."""
    global _SESSION_ID
    r = await client.post("/api/sessions", json={"type": "agent"})
    assert r.status_code in (200, 201)
    _SESSION_ID = r.json()["id"]


async def test_setup_topic(client):
    """Create a topic."""
    global _TOPIC_ID
    assert _SESSION_ID
    r = await client.post("/api/topics", json={"sessionId": _SESSION_ID, "title": "Follow Up Test"})
    assert r.status_code in (200, 201)
    _TOPIC_ID = r.json()["id"]


async def test_setup_messages(client):
    """Create messages to extract follow-ups from."""
    global _MESSAGE_ID
    assert _TOPIC_ID
    r1 = await client.post("/api/messages", json={
        "topic_id": _TOPIC_ID,
        "role": "user",
        "content": "How do I implement authentication in a Python web app?",
    })
    assert r1.status_code in (200, 201)
    _MESSAGE_ID = r1.json()["id"]

    r2 = await client.post("/api/messages", json={
        "topic_id": _TOPIC_ID,
        "role": "assistant",
        "content": "You can use OAuth2 with FastAPI. First install python-jose and passlib. Then create a JWT token endpoint with password hashing.",
    })
    assert r2.status_code in (200, 201)


# ── Follow-up extraction ──────────────────────────────────────────


async def test_extract_follow_up(client):
    """POST /api/follow-up/extract returns suggested actions.

    The endpoint hardcodes openai/gpt-4o-mini. If that model isn't
    configured, it gracefully returns empty actions. We verify the
    endpoint works and the response structure is correct.
    """
    assert _TOPIC_ID
    r = await client.post(
        f"{FOLLOW_UP_PREFIX}/extract",
        json={"topicId": _TOPIC_ID},
        timeout=30.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["messageId"]
    assert "chips" in data
    chips = data["chips"]
    assert isinstance(chips, list)
    # If LLM was reachable, validate action structure
    for chip in chips:
        assert "label" in chip
        assert "message" in chip


async def test_extract_follow_up_empty_topic(client):
    """POST /api/follow-up/extract with nonexistent topic returns empty actions."""
    r = await client.post(
        f"{FOLLOW_UP_PREFIX}/extract",
        json={"topicId": "nonexistent-topic-id"},
    )
    assert r.status_code == 200
    assert r.json() == {"chips": [], "messageId": ""}


# ── Cleanup ────────────────────────────────────────────────────────


async def test_cleanup(client):
    """Delete test data."""
    if _MESSAGE_ID:
        await client.delete(f"/api/messages/{_MESSAGE_ID}")
    if _TOPIC_ID:
        await client.delete(f"/api/topics/{_TOPIC_ID}")
    if _SESSION_ID:
        await client.delete(f"/api/sessions/{_SESSION_ID}")
