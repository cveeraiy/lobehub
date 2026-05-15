"""Code interpreter builtin tool — sandboxed Python execution.

Supports two sandbox modes (configured via ``CODE_INTERPRETER_SANDBOX``):

- **docker** (recommended for production): Runs code in a disposable Docker
  container with ``--network=none``, ``--read-only``, memory limits, and
  ``--user=nobody``.
- **subprocess** (dev-only fallback): Runs in a local subprocess with
  restricted env vars.  **Not secure** — no filesystem or network isolation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from typing import Any

from app.config import settings
from app.tools.registry import register

logger = logging.getLogger(__name__)

# Max output bytes returned to the LLM
_MAX_OUTPUT_CHARS = 5000


# ── Docker sandbox ───────────────────────────────────────────────────


async def _run_in_docker(code: str, timeout: int) -> dict[str, Any]:
    """Run *code* inside a disposable Docker container.

    Security layers:
    - ``--network=none`` — no network access
    - ``--read-only`` — immutable root filesystem
    - ``--tmpfs /tmp:size=50m`` — limited writable scratch space
    - ``--memory`` / ``--pids-limit`` — resource caps
    - ``--user=nobody`` — unprivileged user
    - ``--rm`` — auto-remove container on exit
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="lobe_exec_"
    ) as f:
        f.write(code)
        f.flush()
        script_path = f.name

    try:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return {"error": "Docker not found — set CODE_INTERPRETER_SANDBOX=subprocess for dev mode"}

        cmd = [
            docker_bin, "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--tmpfs", "/tmp:size=50m",
            f"--memory={settings.code_interpreter_memory_limit}",
            "--pids-limit=64",
            "--user=nobody",
            "--cpus=1",
            "-v", f"{script_path}:/sandbox/script.py:ro",
            "-w", "/sandbox",
            settings.code_interpreter_docker_image,
            "python3", "/sandbox/script.py",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {"error": f"Execution timed out ({timeout}s limit)"}

        return _format_output(proc.returncode or 0, stdout, stderr)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


# ── Subprocess fallback (dev only) ───────────────────────────────────


async def _run_in_subprocess(code: str, timeout: int) -> dict[str, Any]:
    """Run *code* in a local subprocess (insecure — dev only)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="lobe_exec_"
    ) as f:
        f.write(code)
        f.flush()
        script_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "PATH": "/usr/bin:/usr/local/bin",
                "HOME": "/tmp",
                "LANG": "en_US.UTF-8",
            },
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {"error": f"Execution timed out ({timeout}s limit)"}

        return _format_output(proc.returncode or 0, stdout, stderr)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


# ── Helpers ──────────────────────────────────────────────────────────


def _format_output(returncode: int, stdout: bytes, stderr: bytes) -> dict[str, Any]:
    stdout_str = stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_CHARS]
    stderr_str = stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_CHARS]

    result: dict[str, Any] = {"exit_code": returncode}
    if stdout_str.strip():
        result["stdout"] = stdout_str
    if stderr_str.strip():
        result["stderr"] = stderr_str
    if returncode != 0:
        result["error"] = f"Process exited with code {returncode}"
    return result


# ── Registered tool ──────────────────────────────────────────────────


@register(
    "code_interpreter",
    description="Execute Python code and return stdout/stderr. Use for calculations, data processing, or generating files.",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
        },
        "required": ["code"],
    },
)
async def code_interpreter(arguments: dict[str, Any]) -> str:
    code = arguments.get("code", "")
    if not code:
        return json.dumps({"error": "code is required"})

    if not settings.code_interpreter_enabled:
        return json.dumps({"error": "Code interpreter is disabled by configuration"})

    timeout = settings.code_interpreter_timeout
    sandbox = settings.code_interpreter_sandbox

    try:
        if sandbox == "docker":
            result = await _run_in_docker(code, timeout)
        elif sandbox == "subprocess":
            logger.warning(
                "Code interpreter using insecure subprocess sandbox — "
                "set CODE_INTERPRETER_SANDBOX=docker for production"
            )
            result = await _run_in_subprocess(code, timeout)
        else:
            return json.dumps({"error": f"Unknown sandbox mode: {sandbox}"})

        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"error": f"Code execution failed: {exc}"})
