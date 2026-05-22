from __future__ import annotations

import pytest

from app.routers import cloud_sandbox
from app.routers.cloud_sandbox import ExecInSandboxBody, ExportAndUploadBody
from app.services.cloud_sandbox import SelfHostedSandboxService
from app.services.cloud_sandbox import service as sandbox_service

pytestmark = pytest.mark.asyncio


async def test_self_hosted_sandbox_runs_code_and_file_ops(tmp_path):
    sandbox = SelfHostedSandboxService("user-1", "topic-1", root=tmp_path)

    write_result = await sandbox.call_tool(
        "writeLocalFile",
        {"content": "alpha\nbeta\nalpha", "createDirectories": True, "path": "notes/a.txt"},
    )
    assert write_result["success"] is True

    read_result = await sandbox.call_tool("readLocalFile", {"endLine": 2, "path": "notes/a.txt", "startLine": 2})
    assert read_result["content"] == "beta"

    grep_result = await sandbox.call_tool("grepContent", {"directory": "notes", "pattern": "alpha"})
    assert [match["line"] for match in grep_result["matches"]] == [1, 3]

    code_result = await sandbox.call_tool(
        "executeCode",
        {"code": "print('sandbox-ok')", "language": "python"},
    )
    assert code_result["success"] is True
    assert code_result["output"] == "sandbox-ok\n"


async def test_self_hosted_sandbox_rejects_path_escape(tmp_path):
    sandbox = SelfHostedSandboxService("user-1", "topic-1", root=tmp_path)

    with pytest.raises(Exception, match="escapes"):
        sandbox.resolve_path("../outside.txt")


async def test_docker_mode_routes_execution_through_container(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_service.settings, "code_interpreter_sandbox", "docker")
    sandbox = SelfHostedSandboxService("user-1", "topic-1", root=tmp_path)
    calls = []

    async def fake_docker_shell(command, *, timeout_ms):
        calls.append((command, timeout_ms))
        return {"exitCode": 0, "output": "docker-ok\n", "stderr": "", "success": True}

    monkeypatch.setattr(sandbox, "_run_docker_shell", fake_docker_shell)

    result = await sandbox.call_tool("executeCode", {"code": "print('docker-ok')", "language": "python"})

    assert result["success"] is True
    assert result["output"] == "docker-ok\n"
    assert len(calls) == 1
    assert calls[0][0].startswith("python3 .tmp_")
    assert calls[0][1] == 120_000


async def test_docker_command_uses_restricted_runtime_flags(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_service.settings, "code_interpreter_sandbox", "docker")
    monkeypatch.setattr(sandbox_service.settings, "cloud_sandbox_docker_network", "none")
    monkeypatch.setattr(sandbox_service.settings, "code_interpreter_docker_image", "python:3.12-slim")
    monkeypatch.setattr(sandbox_service.settings, "code_interpreter_memory_limit", "256m")
    sandbox = SelfHostedSandboxService("user-1", "topic-1", root=tmp_path)

    command = sandbox._docker_command("python3 script.py")

    assert command[:3] == ["docker", "run", "--rm"]
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "--tmpfs" in command
    assert command[command.index("--tmpfs") + 1] == "/tmp:size=100m"
    assert "--cpus" in command
    assert command[command.index("--cpus") + 1] == "1"
    assert "--cap-drop" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in command
    assert "no-new-privileges" in command
    assert f"{sandbox.root.resolve()}:/workspace:rw" in command
    assert command[-4:] == ["python:3.12-slim", "sh", "-lc", "python3 script.py"]


async def test_exec_in_sandbox_returns_market_compatible_shape(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUD_SANDBOX_ROOT", str(tmp_path))

    response = await cloud_sandbox.exec_in_sandbox(
        ExecInSandboxBody(toolName="executeCode", params={"code": "print(3 + 4)", "language": "python"}, topicId="t1"),
        "u1",
    )

    assert response["success"] is True
    assert response["sessionExpiredAndRecreated"] is False
    assert response["result"]["output"] == "7\n"


async def test_export_and_upload_reads_self_hosted_sandbox_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUD_SANDBOX_ROOT", str(tmp_path))
    sandbox = SelfHostedSandboxService("u1", "t1", root=tmp_path)
    await sandbox.call_tool("writeLocalFile", {"content": "export me", "path": "result.txt"})

    uploads = {}

    class FakeS3:
        async def upload_bytes(self, key, data, content_type):
            uploads["key"] = key
            uploads["data"] = data
            uploads["content_type"] = content_type

        async def head(self, key):
            return {"content_length": len(uploads["data"]), "content_type": uploads["content_type"]}

    monkeypatch.setattr(cloud_sandbox.S3Client, "from_settings", lambda: FakeS3())

    async def fake_create_file_record(session, user_id, **kwargs):
        uploads["record"] = kwargs
        return {"file_id": "file-1", "url": "/f/file-1"}

    monkeypatch.setattr(cloud_sandbox, "create_file_record", fake_create_file_record)

    response = await cloud_sandbox.export_and_upload_file(
        ExportAndUploadBody(path="result.txt", filename="download.txt", topicId="t1"),
        "u1",
        object(),
    )

    assert response["success"] is True
    assert response["fileId"] == "file-1"
    assert response["url"] == "/f/file-1"
    assert uploads["data"] == b"export me"
    assert uploads["key"].endswith("/t1/download.txt")
    assert uploads["record"]["name"] == "download.txt"
