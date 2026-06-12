import json

import pytest

from app.routers import tools
from app.routers.tools import RunToolBody

pytestmark = pytest.mark.asyncio


async def test_run_tool_uses_context_dispatcher(monkeypatch):
    calls = {}

    async def fake_execute(tool_name, arguments, *, session, user_id):
        calls["tool_name"] = tool_name
        calls["arguments"] = arguments
        calls["session"] = session
        calls["user_id"] = user_id
        return "ok"

    monkeypatch.setattr(tools, "execute_tool_call_with_context", fake_execute)

    response = await tools.run_tool(
        RunToolBody(tool_name="memory_search", arguments={"query": "x"}),
        "user-1",
        object(),
    )

    assert response == {"result": "ok"}
    assert calls["tool_name"] == "memory_search"
    assert calls["arguments"] == {"query": "x"}
    assert calls["user_id"] == "user-1"


async def test_run_tool_dispatches_lobe_skills_context_tool():
    response = await tools.run_tool(
        RunToolBody(tool_name="lobe-skills__activateSkill", arguments={"name": "Artifacts"}),
        "user-1",
        object(),
    )

    result = json.loads(response["result"])
    assert result["success"] is True
    assert result["state"]["identifier"] == "lobe-artifacts"
