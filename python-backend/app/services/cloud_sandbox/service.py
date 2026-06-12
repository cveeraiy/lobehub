"""Self-hosted Cloud Sandbox service.

This replaces the LobeHub Market-hosted ``run-buildin-tools`` dependency for the
Python backend.  Each user/topic pair gets a filesystem workspace under the
configured sandbox root, and tools execute relative to that workspace.

The default execution backend is ``subprocess`` because it works in local dev and
tests.  It is not a security boundary.  Production deployments should run the
backend itself in an isolated environment or switch to a containerized executor.
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import mimetypes
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings


class SandboxError(Exception):
    """Raised for user-facing sandbox execution errors."""


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:120] or "default"


def _default_root() -> Path:
    return Path(tempfile.gettempdir()) / "lobehub-cloud-sandbox"


@dataclass
class BackgroundCommand:
    process: asyncio.subprocess.Process
    stdout_path: Path
    stderr_path: Path
    stdout_offset: int = 0
    stderr_offset: int = 0
    created_at: datetime = field(default_factory=_utcnow)


class SelfHostedSandboxService:
    """Filesystem-isolated sandbox runner for built-in cloud sandbox tools."""

    def __init__(
        self,
        user_id: str,
        topic_id: str,
        *,
        root: Path | None = None,
    ) -> None:
        self.user_id = user_id
        self.topic_id = topic_id
        self.root = (root or _default_root()) / _safe_segment(user_id) / _safe_segment(topic_id)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / ".commands").mkdir(parents=True, exist_ok=True)

    async def call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "editLocalFile": self._edit_local_file,
            "executeCode": self._execute_code,
            "getCommandOutput": self._get_command_output,
            "globLocalFiles": self._glob_local_files,
            "grepContent": self._grep_content,
            "killCommand": self._kill_command,
            "listLocalFiles": self._list_local_files,
            "moveLocalFiles": self._move_local_files,
            "readLocalFile": self._read_local_file,
            "renameLocalFile": self._rename_local_file,
            "runCommand": self._run_command,
            "searchLocalFiles": self._search_local_files,
            "writeLocalFile": self._write_local_file,
        }
        handler = handlers.get(tool_name)
        if not handler:
            raise SandboxError(f"Unsupported self-hosted sandbox tool: {tool_name}")
        return await handler(params)

    def resolve_path(self, raw_path: str | None, *, create_parent: bool = False) -> Path:
        if not raw_path:
            raw_path = "."
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            candidate = Path(str(candidate).lstrip("/"))
        full_path = (self.root / candidate).resolve()
        root = self.root.resolve()
        if full_path != root and root not in full_path.parents:
            raise SandboxError("Path escapes the sandbox workspace")
        if create_parent:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        return full_path

    def display_path(self, path: Path) -> str:
        rel = path.resolve().relative_to(self.root.resolve())
        return "." if str(rel) == "." else str(rel)

    async def _execute_code(self, params: dict[str, Any]) -> dict[str, Any]:
        language = str(params.get("language") or "python").lower()
        code = str(params.get("code") or "")
        if not code:
            raise SandboxError("code is required")

        suffix_by_language = {
            "javascript": ".mjs",
            "js": ".mjs",
            "python": ".py",
            "typescript": ".ts",
            "ts": ".ts",
        }
        suffix = suffix_by_language.get(language)
        if not suffix:
            raise SandboxError(f"Unsupported language: {language}")

        script_path = self.root / f".tmp_{uuid.uuid4().hex}{suffix}"
        script_path.write_text(code, encoding="utf-8")
        try:
            if suffix == ".py":
                command = f"python3 {script_path.name}"
            elif suffix == ".mjs":
                command = f"node {script_path.name}"
            else:
                command = f"npx --yes tsx {script_path.name}"
            result = await self._run_shell(command, timeout_ms=int(params.get("timeout") or 120_000))
            return {
                "error": None if result["exitCode"] == 0 else result["stderr"] or result["output"],
                "exitCode": result["exitCode"],
                "output": result["output"],
                "stderr": result["stderr"],
                "success": result["exitCode"] == 0,
            }
        finally:
            script_path.unlink(missing_ok=True)

    async def _run_command(self, params: dict[str, Any]) -> dict[str, Any]:
        command = str(params.get("command") or "")
        if not command:
            raise SandboxError("command is required")
        if params.get("background"):
            return await self._start_background_command(command)
        return await self._run_shell(command, timeout_ms=int(params.get("timeout") or 120_000))

    async def _run_shell(self, command: str, *, timeout_ms: int) -> dict[str, Any]:
        if self._use_docker():
            return await self._run_docker_shell(command, timeout_ms=timeout_ms)
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=self.root,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_ms / 1000)
            timed_out = False
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            timed_out = True
        return {
            "exitCode": process.returncode if not timed_out else -1,
            "output": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "success": process.returncode == 0 and not timed_out,
            **({"error": "Command timed out"} if timed_out else {}),
        }

    async def _start_background_command(self, command: str) -> dict[str, Any]:
        if self._use_docker():
            return await self._start_background_docker_command(command)
        command_id = uuid.uuid4().hex
        stdout_path = self.root / ".commands" / f"{command_id}.out"
        stderr_path = self.root / ".commands" / f"{command_id}.err"
        stdout_handle = stdout_path.open("wb")
        stderr_handle = stderr_path.open("wb")
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=self.root,
            stderr=stderr_handle,
            stdout=stdout_handle,
        )
        stdout_handle.close()
        stderr_handle.close()
        _BACKGROUND_COMMANDS[command_id] = BackgroundCommand(
            process=process,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        return {"commandId": command_id, "running": True, "success": True}

    def _use_docker(self) -> bool:
        return settings.code_interpreter_sandbox.lower() == "docker"

    def _docker_command(self, command: str) -> list[str]:
        docker_args = [
            "docker",
            "run",
            "--rm",
            "--network",
            settings.cloud_sandbox_docker_network,
            "--read-only",
            "--tmpfs",
            "/tmp:size=100m",
            "--memory",
            settings.code_interpreter_memory_limit,
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{self.root.resolve()}:/workspace:rw",
            "-w",
            "/workspace",
            settings.code_interpreter_docker_image,
            "sh",
            "-lc",
            command,
        ]
        return docker_args

    async def _run_docker_shell(self, command: str, *, timeout_ms: int) -> dict[str, Any]:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._docker_command(command),
                stderr=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise SandboxError("Docker is not installed or not available on PATH") from exc

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_ms / 1000)
            timed_out = False
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            timed_out = True

        return {
            "exitCode": process.returncode if not timed_out else -1,
            "output": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "success": process.returncode == 0 and not timed_out,
            **({"error": "Command timed out"} if timed_out else {}),
        }

    async def _start_background_docker_command(self, command: str) -> dict[str, Any]:
        command_id = uuid.uuid4().hex
        stdout_path = self.root / ".commands" / f"{command_id}.out"
        stderr_path = self.root / ".commands" / f"{command_id}.err"
        stdout_handle = stdout_path.open("wb")
        stderr_handle = stderr_path.open("wb")
        try:
            process = await asyncio.create_subprocess_exec(
                *self._docker_command(command),
                stderr=stderr_handle,
                stdout=stdout_handle,
            )
        except FileNotFoundError as exc:
            raise SandboxError("Docker is not installed or not available on PATH") from exc
        finally:
            stdout_handle.close()
            stderr_handle.close()

        _BACKGROUND_COMMANDS[command_id] = BackgroundCommand(
            process=process,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        return {"commandId": command_id, "running": True, "success": True}

    async def _get_command_output(self, params: dict[str, Any]) -> dict[str, Any]:
        command_id = str(params.get("commandId") or "")
        command = _BACKGROUND_COMMANDS.get(command_id)
        if not command:
            raise SandboxError("Unknown or expired commandId")
        output, command.stdout_offset = self._read_since(command.stdout_path, command.stdout_offset)
        stderr, command.stderr_offset = self._read_since(command.stderr_path, command.stderr_offset)
        running = command.process.returncode is None
        return {
            "commandId": command_id,
            "exitCode": command.process.returncode,
            "output": output,
            "running": running,
            "stderr": stderr,
            "success": True if running else command.process.returncode == 0,
        }

    async def _kill_command(self, params: dict[str, Any]) -> dict[str, Any]:
        command_id = str(params.get("commandId") or "")
        command = _BACKGROUND_COMMANDS.get(command_id)
        if not command:
            raise SandboxError("Unknown or expired commandId")
        if command.process.returncode is None:
            command.process.kill()
            await command.process.wait()
        return {"commandId": command_id, "killed": True, "success": True}

    def _read_since(self, path: Path, offset: int) -> tuple[str, int]:
        with path.open("rb") as file:
            file.seek(offset)
            data = file.read()
            return data.decode(errors="replace"), file.tell()

    async def _list_local_files(self, params: dict[str, Any]) -> dict[str, Any]:
        directory = self.resolve_path(str(params.get("directoryPath") or "."))
        if not directory.exists():
            raise SandboxError("Directory does not exist")
        if not directory.is_dir():
            raise SandboxError("Path is not a directory")
        items = []
        for child in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            stat = child.stat()
            items.append(
                {
                    "isDirectory": child.is_dir(),
                    "name": child.name,
                    "path": self.display_path(child),
                    "size": stat.st_size,
                    "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        return {"files": items}

    async def _read_local_file(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self.resolve_path(str(params.get("path") or ""))
        if not path.is_file():
            raise SandboxError("File does not exist")
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start_line = params.get("startLine")
        end_line = params.get("endLine")
        if start_line or end_line:
            start = max(int(start_line or 1), 1) - 1
            end = int(end_line) if end_line else len(lines)
            text = "\n".join(lines[start:end])
        return {"content": text, "path": self.display_path(path)}

    async def _write_local_file(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self.resolve_path(str(params.get("path") or ""), create_parent=bool(params.get("createDirectories")))
        if not path.parent.exists():
            raise SandboxError("Parent directory does not exist")
        content = str(params.get("content") or "")
        path.write_text(content, encoding="utf-8")
        return {"bytesWritten": len(content.encode()), "path": self.display_path(path), "success": True}

    async def _edit_local_file(self, params: dict[str, Any]) -> dict[str, Any]:
        path = self.resolve_path(str(params.get("path") or ""))
        if not path.is_file():
            raise SandboxError("File does not exist")
        search = str(params.get("search") or "")
        replace = str(params.get("replace") or "")
        if not search:
            raise SandboxError("search is required")
        if search == replace:
            raise SandboxError("replace must differ from search")
        text = path.read_text(encoding="utf-8", errors="replace")
        count = text.count(search)
        if count == 0:
            raise SandboxError("search text was not found")
        new_text = text.replace(search, replace) if params.get("all") else text.replace(search, replace, 1)
        path.write_text(new_text, encoding="utf-8")
        return {"path": self.display_path(path), "replacements": count if params.get("all") else 1, "success": True}

    async def _move_local_files(self, params: dict[str, Any]) -> dict[str, Any]:
        operations = params.get("operations") or []
        moved = []
        for operation in operations:
            source = self.resolve_path(str(operation.get("source") or ""))
            destination = self.resolve_path(str(operation.get("destination") or ""), create_parent=True)
            if not source.exists():
                raise SandboxError(f"Source does not exist: {operation.get('source')}")
            shutil.move(str(source), str(destination))
            moved.append({"destination": self.display_path(destination), "source": str(operation.get("source") or "")})
        return {"operations": moved, "success": True}

    async def _rename_local_file(self, params: dict[str, Any]) -> dict[str, Any]:
        old_path = self.resolve_path(str(params.get("oldPath") or ""))
        new_name = str(params.get("newName") or "")
        if not new_name or "/" in new_name or "\\" in new_name:
            raise SandboxError("newName must be a filename")
        destination = old_path.with_name(new_name)
        if self.root.resolve() not in destination.resolve().parents:
            raise SandboxError("Path escapes the sandbox workspace")
        old_path.rename(destination)
        return {"path": self.display_path(destination), "success": True}

    async def _search_local_files(self, params: dict[str, Any]) -> dict[str, Any]:
        directory = self.resolve_path(str(params.get("directory") or "."))
        keyword = str(params.get("keyword") or "").lower()
        file_type = str(params.get("fileType") or "").lower().lstrip(".")
        results = []
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            if keyword and keyword not in path.name.lower():
                continue
            if file_type and path.suffix.lower().lstrip(".") != file_type:
                continue
            stat = path.stat()
            results.append({"path": self.display_path(path), "size": stat.st_size})
        return {"files": results}

    async def _glob_local_files(self, params: dict[str, Any]) -> dict[str, Any]:
        directory = self.resolve_path(str(params.get("directory") or "."))
        pattern = str(params.get("pattern") or "*")
        files = [
            {"path": self.display_path(path), "size": path.stat().st_size}
            for path in directory.rglob("*")
            if path.is_file() and fnmatch.fnmatch(str(path.relative_to(directory)), pattern)
        ]
        return {"files": files}

    async def _grep_content(self, params: dict[str, Any]) -> dict[str, Any]:
        directory = self.resolve_path(str(params.get("directory") or "."))
        pattern = str(params.get("pattern") or "")
        if not pattern:
            raise SandboxError("pattern is required")
        file_pattern = str(params.get("filePattern") or "*")
        recursive = params.get("recursive", True)
        regex = re.compile(pattern)
        candidates = directory.rglob("*") if recursive else directory.glob("*")
        matches = []
        for path in candidates:
            if not path.is_file() or not fnmatch.fnmatch(path.name, file_pattern):
                continue
            for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                if regex.search(line):
                    matches.append({"line": index, "path": self.display_path(path), "text": line})
        return {"matches": matches}


_BACKGROUND_COMMANDS: dict[str, BackgroundCommand] = {}


def get_sandbox_service(user_id: str, topic_id: str) -> SelfHostedSandboxService:
    root = Path(settings.cloud_sandbox_root or os.environ.get("CLOUD_SANDBOX_ROOT") or _default_root())
    return SelfHostedSandboxService(user_id=user_id, topic_id=topic_id, root=root)


def sandbox_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def guess_mime_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
