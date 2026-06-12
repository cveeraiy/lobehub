import json
from types import SimpleNamespace

import pytest

from app.tools import skills as skills_tool

pytestmark = pytest.mark.asyncio


def _decode(raw: str) -> dict:
    return json.loads(raw)


async def test_activate_builtin_skill_by_display_name():
    result = _decode(
        await skills_tool.skills_with_context("activateSkill", {"name": "Artifacts"}, object(), "user-1")
    )

    assert result["success"] is True
    assert "Artifacts" in result["content"]
    assert result["state"]["identifier"] == "lobe-artifacts"


async def test_read_reference_rejects_path_traversal():
    result = _decode(
        await skills_tool.skills_with_context(
            "readReference",
            {"id": "lobe-artifacts", "path": "../secret.txt"},
            object(),
            "user-1",
        )
    )

    assert result["success"] is False
    assert "path traversal" in result["content"]


async def test_read_reference_reads_user_skill_resource(monkeypatch):
    async def fake_find_user_skill(_session, _user_id, name):
        assert name == "my-skill"
        return SimpleNamespace(
            resources={
                "docs/guide.md": {
                    "content": "# Guide\nUse the thing.",
                    "size": 22,
                }
            }
        )

    monkeypatch.setattr(skills_tool, "_find_user_skill", fake_find_user_skill)

    result = _decode(
        await skills_tool.skills_with_context(
            "readReference",
            {"id": "my-skill", "path": "docs/guide.md"},
            object(),
            "user-1",
        )
    )

    assert result["success"] is True
    assert result["content"] == "# Guide\nUse the thing."
    assert result["state"] == {
        "encoding": "utf8",
        "fileType": "text/markdown",
        "fullPath": "docs/guide.md",
        "path": "docs/guide.md",
        "size": 22,
    }


async def test_exec_script_uses_command_alias(monkeypatch):
    async def fake_code_interpreter(_arguments):
        return json.dumps({"exit_code": 0, "stdout": "ok\n"})

    import app.tools.code_interpreter as code_interpreter_module

    monkeypatch.setattr(code_interpreter_module, "code_interpreter", fake_code_interpreter)

    result = _decode(
        await skills_tool.skills_with_context(
            "execScript",
            {"command": "print('ok')", "language": "python"},
            object(),
            "user-1",
        )
    )

    assert result["success"] is True
    assert "stdout:\nok" in result["content"]
    assert result["state"] == {"command": "print('ok')", "exitCode": 0, "success": True}


async def test_export_file_returns_file_metadata(tmp_path):
    export_path = tmp_path / "report.txt"
    export_path.write_text("hello", encoding="utf-8")

    result = _decode(
        await skills_tool.skills_with_context(
            "exportFile",
            {"filename": "report.txt", "path": str(export_path)},
            object(),
            "user-1",
        )
    )

    assert result["success"] is True
    assert result["state"]["filename"] == "report.txt"
    assert result["state"]["mimeType"] == "text/plain"
    assert result["state"]["size"] == 5
    assert result["state"]["url"] == str(export_path)
