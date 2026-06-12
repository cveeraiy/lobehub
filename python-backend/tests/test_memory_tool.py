from datetime import UTC, datetime

import pytest

from app.models.memory import UserMemory, UserMemoryIdentity
from app.tools.memory_tool import _resolve_time_intent, run_memory_api

pytestmark = pytest.mark.asyncio


class FakeSession:
    def __init__(self):
        self.memories: list[UserMemory] = []
        self.identities: list[UserMemoryIdentity] = []

    def add(self, obj):
        if isinstance(obj, UserMemory):
            self.memories.append(obj)
        elif isinstance(obj, UserMemoryIdentity):
            self.identities.append(obj)

    async def flush(self):
        return None


async def test_add_identity_memory_matches_runtime_shape(monkeypatch):
    from app.routers import user_memory

    async def fake_embed_single(_text):
        return None

    monkeypatch.setattr(user_memory, "_embed_single", fake_embed_single)
    session = FakeSession()

    result = await run_memory_api(
        "addIdentityMemory",
        {
            "details": "Details",
            "memoryCategory": "profile",
            "memoryType": "person",
            "summary": "Knows Ada",
            "tags": ["identity"],
            "title": "Ada",
            "withIdentity": {
                "description": "Ada is a collaborator",
                "relationship": "colleague",
                "role": "engineer",
                "type": "person",
            },
        },
        session=session,
        user_id="user-1",
    )

    assert result["success"] is True
    assert result["state"]["memoryId"] == session.memories[0].id
    assert result["state"]["identityId"] == session.identities[0].id
    assert result["content"] == (
        f'Identity memory "Ada" saved with memoryId: "{session.memories[0].id}" '
        f'and identityId: "{session.identities[0].id}"'
    )


async def test_read_only_blocks_memory_writes():
    result = await run_memory_api(
        "addPreferenceMemory",
        {
            "summary": "Likes terse answers",
            "title": "Style",
            "toolPermission": "read-only",
            "withPreference": {"conclusionDirectives": "Be terse"},
        },
        session=object(),
        user_id="user-1",
    )

    assert result == {"content": "Memory tool is in read-only mode for this chat", "success": False}


async def test_search_user_memory_returns_builtin_runtime_shape(monkeypatch):
    from app.routers import user_memory

    async def fake_search_memory(body, user_id, session):
        assert body.queries == ["Ada"]
        assert user_id == "user-1"
        assert session == "session"
        return {
            "activities": [],
            "contexts": [],
            "experiences": [],
            "identities": [{"description": "Ada is a collaborator", "id": "identity-1", "type": "person"}],
            "meta": {"ignored": True},
            "preferences": [],
        }

    monkeypatch.setattr(user_memory, "search_memory", fake_search_memory)

    result = await run_memory_api(
        "searchUserMemory",
        {"queries": ["Ada"]},
        session="session",
        user_id="user-1",
    )

    assert result["success"] is True
    assert result["state"] == {
        "activities": [],
        "contexts": [],
        "experiences": [],
        "identities": [{"description": "Ada is a collaborator", "id": "identity-1", "type": "person"}],
        "preferences": [],
    }
    assert result["content"] == (
        '<memories query="Ada" total="1">\n'
        '<identities count="1">\n'
        '  <identity id="identity-1" type="person">Ada is a collaborator</identity>\n'
        "</identities>\n"
        "</memories>"
    )


async def test_search_user_memory_applies_layer_and_type_filters(monkeypatch):
    from app.routers import user_memory

    async def fake_search_memory(body, user_id, session):
        assert body.topK["identities"] == 0
        assert body.topK["activities"] == 0
        assert body.topK["experiences"] == 0
        assert body.topK["contexts"] == 0
        assert user_id == "user-1"
        assert session == "session"
        return {
            "activities": [],
            "contexts": [],
            "experiences": [],
            "identities": [{"description": "Ada is a collaborator", "id": "identity-1", "type": "person"}],
            "meta": {},
            "preferences": [
                {
                    "conclusionDirectives": "Use concise answers",
                    "id": "preference-1",
                    "scorePriority": 7,
                    "tags": ["style"],
                    "type": "communication",
                },
                {
                    "conclusionDirectives": "Prefer Python",
                    "id": "preference-2",
                    "scorePriority": 3,
                    "tags": ["code"],
                    "type": "tooling",
                },
            ],
        }

    monkeypatch.setattr(user_memory, "search_memory", fake_search_memory)

    result = await run_memory_api(
        "searchUserMemory",
        {"layers": ["preference"], "queries": ["style"], "tags": ["style"], "types": ["communication"]},
        session="session",
        user_id="user-1",
    )

    assert result["success"] is True
    assert result["state"] == {
        "activities": [],
        "contexts": [],
        "experiences": [],
        "identities": [],
        "preferences": [
            {
                "conclusionDirectives": "Use concise answers",
                "id": "preference-1",
                "scorePriority": 7,
                "tags": ["style"],
                "type": "communication",
            }
        ],
    }
    assert result["content"] == (
        '<memories query="style" total="1">\n'
        '<preferences count="1">\n'
        '  <preference id="preference-1" type="communication" priority=7>Use concise answers</preference>\n'
        "</preferences>\n"
        "</memories>"
    )


async def test_search_user_memory_formats_empty_results_like_ts_runtime(monkeypatch):
    from app.routers import user_memory

    async def fake_search_memory(body, user_id, session):
        return {
            "activities": [],
            "contexts": [],
            "experiences": [],
            "identities": [],
            "meta": {},
            "preferences": [],
        }

    monkeypatch.setattr(user_memory, "search_memory", fake_search_memory)

    result = await run_memory_api(
        "searchUserMemory",
        {"queries": ["missing"]},
        session="session",
        user_id="user-1",
    )

    assert result["content"] == (
        '<memories query="missing">\n'
        "  <status>No memories found matching the query.</status>\n"
        "</memories>"
    )


async def test_resolve_time_intent_matches_utc_ts_semantics():
    resolved = _resolve_time_intent(
        {"selector": "lastWeekend"},
        now=datetime(2026, 5, 20, 12, tzinfo=UTC),
    )

    assert resolved is not None
    assert resolved["field"] == "createdAt"
    assert resolved["start"].isoformat() == "2026-05-16T00:00:00+00:00"
    assert resolved["end"].isoformat() == "2026-05-17T23:59:59.999000+00:00"
