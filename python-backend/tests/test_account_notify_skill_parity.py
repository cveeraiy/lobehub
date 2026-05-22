from types import SimpleNamespace

import pytest

from app.routers import account_deletion, agent_notify, skill_maintainer
from app.routers.agent_notify import NotifyBody, notify
from app.services.skill_maintainer import assert_package_relative_path


def _paths(router):
    return {(route.path, ",".join(sorted(route.methods or []))) for route in router.router.routes}


def test_account_deletion_routes_are_registered():
    paths = _paths(account_deletion)

    assert ("/api/account-deletion/status", "GET") in paths
    assert ("/api/account-deletion/request", "POST") in paths
    assert ("/api/account-deletion/cancel", "POST") in paths
    assert ("/api/account-deletion/confirm", "DELETE") in paths


def test_agent_notify_route_is_registered():
    assert ("/api/agent-notify/notify", "POST") in _paths(agent_notify)


def test_skill_maintainer_routes_are_registered():
    paths = _paths(skill_maintainer)

    assert ("/api/skill-maintainer/read", "POST") in paths
    assert ("/api/skill-maintainer/update", "POST") in paths
    assert ("/api/skill-maintainer/write", "POST") in paths
    assert ("/api/skill-maintainer/remove", "POST") in paths


def test_skill_maintainer_rejects_unsafe_paths():
    assert assert_package_relative_path("references/guide.md") == "references/guide.md"

    with pytest.raises(ValueError, match="absolute paths"):
        assert_package_relative_path("/SKILL.md")

    with pytest.raises(ValueError, match="path traversal"):
        assert_package_relative_path("references/../SKILL.md")


@pytest.mark.asyncio
async def test_agent_notify_triggers_ai_agent(monkeypatch):
    calls = []

    class FakeSession:
        async def execute(self, _stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(agent_id="agent_1"))

    async def fake_exec_agent_notify(user_id, agent_id, topic_id, thread_id, content):
        calls.append(
            {
                "agent_id": agent_id,
                "content": content,
                "thread_id": thread_id,
                "topic_id": topic_id,
                "user_id": user_id,
            }
        )
        return SimpleNamespace(operation_id="op_1")

    monkeypatch.setattr("app.routers.agent_notify._exec_agent_notify", fake_exec_agent_notify)

    result = await notify(NotifyBody(content="hello", topic_id="topic_1"), user_id="user_1", session=FakeSession())

    assert result == {"operationId": "op_1", "topicId": "topic_1"}
    assert calls[0]["user_id"] == "user_1"
    assert calls[0]["agent_id"] == "agent_1"
    assert calls[0]["topic_id"] == "topic_1"
