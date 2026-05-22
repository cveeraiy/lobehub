"""Skills executor builtin tool — list, find, read resources, run commands, exec scripts."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)


# ── Context-aware implementations ────────────────────────────────────


async def skills_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Skills tool — list, get, read resource, run command, exec script."""
    from sqlalchemy import and_, desc, select

    from app.models.skill import AgentSkill
    from app.skills.builtin import BUILTIN_SKILLS, get_builtin_skill

    if api_name == "findAll":
        stmt = (
            select(AgentSkill)
            .where(AgentSkill.user_id == user_id)
            .order_by(desc(AgentSkill.updated_at))
        )
        rows = (await session.execute(stmt)).scalars().all()
        user_skills = [
            {
                "id": s.id,
                "identifier": s.identifier,
                "name": s.display_name,
                "description": s.description,
                "source": "user",
            }
            for s in rows
        ]
        builtin_ids = {s["identifier"] for s in user_skills}
        builtin_list = [
            {
                "id": None,
                "identifier": b["identifier"],
                "name": b["name"],
                "description": b["description"],
                "source": "builtin",
            }
            for b in BUILTIN_SKILLS
            if b["identifier"] not in builtin_ids
        ]
        all_skills = user_skills + builtin_list
        return json.dumps({"total": len(all_skills), "data": all_skills})

    if api_name == "findByName":
        name = arguments.get("name", "")
        if not name:
            return json.dumps({"error": "name is required"})

        # Search user skills by display_name
        stmt = select(AgentSkill).where(
            and_(AgentSkill.display_name == name, AgentSkill.user_id == user_id)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row:
            manifest = row.manifest or {}
            return json.dumps({
                "id": row.id,
                "identifier": row.identifier,
                "name": row.display_name,
                "description": row.description,
                "manifest": manifest,
                "tools": manifest.get("tools", []),
                "source": "user",
            })

        # Search by identifier
        stmt2 = select(AgentSkill).where(
            and_(AgentSkill.identifier == name, AgentSkill.user_id == user_id)
        )
        row2 = (await session.execute(stmt2)).scalar_one_or_none()
        if row2:
            manifest = row2.manifest or {}
            return json.dumps({
                "id": row2.id,
                "identifier": row2.identifier,
                "name": row2.display_name,
                "description": row2.description,
                "manifest": manifest,
                "tools": manifest.get("tools", []),
                "source": "user",
            })

        # Builtin fallback
        builtin = get_builtin_skill(name)
        if builtin:
            return json.dumps({
                "id": None,
                "identifier": builtin["identifier"],
                "name": builtin["name"],
                "description": builtin["description"],
                "tools": builtin.get("tools", []),
                "source": "builtin",
            })

        return json.dumps({"error": f"Skill not found: {name}"})

    if api_name == "readResource":
        skill_id = arguments.get("skill_id", "")
        path = arguments.get("path", "")
        if not skill_id or not path:
            return json.dumps({"error": "skill_id and path are required"})

        stmt = select(AgentSkill).where(
            and_(AgentSkill.id == skill_id, AgentSkill.user_id == user_id)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Skill not found: {skill_id}"})

        resources = row.resources or {}
        content = resources.get(path)
        if content is None:
            return json.dumps({
                "error": f"Resource not found: {path}",
                "available": list(resources.keys()),
            })
        return json.dumps({"path": path, "content": content})

    if api_name == "runCommand":
        command = arguments.get("command", "")
        if not command:
            return json.dumps({"error": "command is required"})

        # Delegate to code_interpreter sandbox for safety
        from app.tools.code_interpreter import code_interpreter

        code = f"""\
import subprocess, sys
proc = subprocess.run(
    {command!r},
    shell=True,
    capture_output=True,
    text=True,
    timeout=25,
)
print(proc.stdout, end='')
if proc.stderr:
    print(proc.stderr, end='', file=sys.stderr)
sys.exit(proc.returncode)
"""
        return await code_interpreter({"code": code})

    if api_name == "execScript":
        script = arguments.get("script", "")
        language = arguments.get("language", "python")
        if not script:
            return json.dumps({"error": "script is required"})

        from app.tools.code_interpreter import code_interpreter

        if language == "python":
            return await code_interpreter({"code": script})
        else:
            ext = {"javascript": ".js", "node": ".js", "bash": ".sh", "sh": ".sh"}.get(
                language, ".sh"
            )
            runtime = {"javascript": "node", "node": "node", "bash": "bash", "sh": "sh"}.get(
                language, "bash"
            )
            code = f"""\
import subprocess, sys, tempfile, os
script = {script!r}
ext = {ext!r}
runtime = {runtime!r}
with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
    f.write(script)
    f.flush()
    path = f.name
try:
    proc = subprocess.run([runtime, path], capture_output=True, text=True, timeout=25)
    print(proc.stdout, end='')
    if proc.stderr:
        print(proc.stderr, end='', file=sys.stderr)
    sys.exit(proc.returncode)
finally:
    os.unlink(path)
"""
            return await code_interpreter({"code": code})

    return json.dumps({"error": f"Unknown skills API: {api_name}"})


# ── Dispatcher for double-underscore routing ─────────────────────────


async def _skills_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    """Context handler dispatcher — called by tool_execution.py."""
    return await skills_with_context(api_name, arguments, session, user_id)


# ── Registered tools (context-backed) ───────────────────────────────


@register(
    "skills__findAll",
    description="List all installed skills (user and builtin).",
    parameters={"type": "object", "properties": {}},
)
async def _skills_find_all_context_required(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skills requires DB context"})


@register(
    "skills__findByName",
    description="Find a skill by name or identifier and return its manifest and tools.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name or identifier"},
        },
        "required": ["name"],
    },
)
async def _skills_find_by_name_context_required(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skills requires DB context"})


@register(
    "skills__readResource",
    description="Read a resource file from an installed skill.",
    parameters={
        "type": "object",
        "properties": {
            "skill_id": {"type": "string", "description": "Skill ID"},
            "path": {"type": "string", "description": "Resource path within the skill"},
        },
        "required": ["skill_id", "path"],
    },
)
async def _skills_read_resource_context_required(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skills requires DB context"})


@register(
    "skills__runCommand",
    description="Run a shell command in a sandboxed environment.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
        },
        "required": ["command"],
    },
)
async def _skills_run_command_context_required(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skills requires DB context"})


@register(
    "skills__execScript",
    description="Execute a script in a sandboxed environment.",
    parameters={
        "type": "object",
        "properties": {
            "script": {"type": "string", "description": "Script content to execute"},
            "language": {
                "type": "string",
                "description": "Script language",
                "enum": ["python", "javascript", "bash"],
                "default": "python",
            },
        },
        "required": ["script"],
    },
)
async def _skills_exec_script_context_required(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skills requires DB context"})


# Register context handlers for all skills__ tools
for _api in ("findAll", "findByName", "readResource", "runCommand", "execScript"):
    register_context_handler(f"skills__{_api}", _skills_context_dispatch)
