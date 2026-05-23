"""Skills executor builtin tool — activate/read resources/run/export skills."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)


def _tool_success(content: str, state: dict[str, Any] | None = None) -> str:
    result: dict[str, Any] = {"content": content, "success": True}
    if state is not None:
        result["state"] = state
    return json.dumps(result)


def _tool_failure(content: str) -> str:
    return json.dumps({"content": content, "success": False})


def _resource_content(meta: Any) -> str | None:
    if isinstance(meta, str):
        return meta
    if isinstance(meta, dict):
        content = meta.get("content")
        return content if isinstance(content, str) else None
    return None


def _resource_size(meta: Any, content: str) -> int:
    if isinstance(meta, dict) and isinstance(meta.get("size"), int):
        return meta["size"]
    return len(content.encode("utf-8"))


def _resources_tree_prompt(skill_name: str, resources: dict[str, Any]) -> str:
    if not resources:
        return ""
    lines = [f"Resources available for skill \"{skill_name}\":"]
    for path in sorted(resources.keys()):
        lines.append(f"- {path}")
    return "\n".join(lines)


def _get_builtin_skill(skills: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    normalized = name.lower()
    for skill in skills:
        if skill.get("identifier") == name or str(skill.get("name", "")).lower() == normalized:
            return skill
    return None


def _format_command_result(result: dict[str, Any]) -> str:
    exit_code = result.get("exit_code", result.get("exitCode", 0 if not result.get("error") else 1))
    stdout = result.get("stdout") or result.get("output") or ""
    stderr = result.get("stderr") or result.get("error") or ""
    parts = [f"Exit code: {exit_code}"]
    if stdout:
        parts.append(f"stdout:\n{stdout}")
    if stderr:
        parts.append(f"stderr:\n{stderr}")
    return "\n\n".join(parts)


def _command_result_output(command: str, result: dict[str, Any]) -> str:
    exit_code = result.get("exit_code", result.get("exitCode", 1 if result.get("error") else 0))
    success = not result.get("error") and exit_code == 0
    return json.dumps({
        "content": _format_command_result(result),
        "state": {"command": command, "exitCode": exit_code, "success": success},
        "success": success,
    })


def _command_output(command: str, raw: str) -> str:
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"exit_code": 0, "stdout": raw}
    return _command_result_output(command, result)


async def _find_user_skill(session: Any, user_id: str, name: str):
    from sqlalchemy import and_, select

    from app.models.skill import AgentSkill

    stmt = select(AgentSkill).where(
        and_(AgentSkill.display_name == name, AgentSkill.user_id == user_id)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        return row

    stmt = select(AgentSkill).where(
        and_(AgentSkill.identifier == name, AgentSkill.user_id == user_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _list_user_skills(session: Any, user_id: str):
    from sqlalchemy import desc, select

    from app.models.skill import AgentSkill

    stmt = select(AgentSkill).where(AgentSkill.user_id == user_id).order_by(desc(AgentSkill.updated_at))
    return (await session.execute(stmt)).scalars().all()


async def skills_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Skills tool — list, activate, read resource, run command, exec script, export file."""
    from app.skills.builtin import BUILTIN_SKILLS

    if api_name == "findAll":
        rows = await _list_user_skills(session, user_id)
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

        row = await _find_user_skill(session, user_id, name)
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

        builtin = _get_builtin_skill(BUILTIN_SKILLS, name)
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

    if api_name == "activateSkill":
        name = arguments.get("name", "")
        builtin = _get_builtin_skill(BUILTIN_SKILLS, name)
        if builtin:
            resources = builtin.get("resources") or {}
            content = builtin.get("content") or builtin.get("prompt") or ""
            if resources:
                content += "\n\n" + _resources_tree_prompt(builtin["name"], resources)
            return _tool_success(content, {
                "description": builtin.get("description"),
                "hasResources": bool(resources),
                "identifier": builtin.get("identifier"),
                "name": builtin.get("name"),
            })

        row = await _find_user_skill(session, user_id, name)
        if not row:
            available = [
                {"description": s.description, "name": s.display_name or s.identifier}
                for s in await _list_user_skills(session, user_id)
            ] + [
                {"description": b["description"], "name": b["name"]}
                for b in BUILTIN_SKILLS
            ]
            return _tool_failure(f"Skill not found: \"{name}\". Available skills: {json.dumps(available)}")

        resources = row.resources or {}
        content = getattr(row, "content", None) or (row.manifest or {}).get("content") or ""
        if resources:
            content += "\n\n" + _resources_tree_prompt(row.display_name or row.identifier, resources)
        return _tool_success(content, {
            "description": row.description or None,
            "hasResources": bool(resources),
            "id": row.id,
            "name": row.display_name or row.identifier,
        })

    if api_name in {"readReference", "readResource"}:
        skill_id = arguments.get("id") or arguments.get("skill_id", "")
        path = arguments.get("path", "")
        if not skill_id or not path:
            return _tool_failure("Skill and path are required")
        if ".." in path:
            return _tool_failure("Invalid path: path traversal is not allowed")

        builtin = _get_builtin_skill(BUILTIN_SKILLS, skill_id)
        if builtin and builtin.get("resources"):
            resources = builtin["resources"]
            meta = resources.get(path)
            content = _resource_content(meta)
            if content is None:
                return _tool_failure(f"Resource not found: \"{path}\" in builtin skill \"{skill_id}\"")
            return _tool_success(content, {
                "encoding": "utf8",
                "fileType": "text/plain",
                "path": path,
                "size": _resource_size(meta, content),
            })

        row = await _find_user_skill(session, user_id, skill_id)
        if not row:
            return _tool_failure(f"Skill not found: \"{skill_id}\"")

        resources = row.resources or {}
        meta = resources.get(path)
        content = _resource_content(meta)
        if content is None:
            return _tool_failure(f"Resource not found: \"{path}\"")
        return _tool_success(content, {
            "encoding": "utf8",
            "fileType": mimetypes.guess_type(path)[0] or "text/plain",
            "fullPath": path,
            "path": path,
            "size": _resource_size(meta, content),
        })

    if api_name == "runCommand":
        command = arguments.get("command", "")
        if not command:
            return _tool_failure("command is required")

        topic_id = arguments.get("topicId") or arguments.get("topic_id")
        if topic_id:
            from app.services.cloud_sandbox import get_sandbox_service

            sandbox = get_sandbox_service(user_id, str(topic_id))
            result = await sandbox.call_tool(
                "runCommand",
                {"command": command, "timeout": arguments.get("timeout")},
            )
            return _command_result_output(command, result)

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
        return _command_output(command, await code_interpreter({"code": code}))

    if api_name == "execScript":
        script = arguments.get("script") or arguments.get("command", "")
        language = arguments.get("language", "python")
        if not script:
            return _tool_failure("script is required")

        topic_id = arguments.get("topicId") or arguments.get("topic_id")
        if topic_id:
            from app.services.cloud_sandbox import get_sandbox_service

            sandbox = get_sandbox_service(user_id, str(topic_id))
            normalized_language = str(language).lower()
            if normalized_language in {"python", "javascript", "js", "typescript", "ts"}:
                result = await sandbox.call_tool(
                    "executeCode",
                    {"code": script, "language": normalized_language, "timeout": arguments.get("timeout")},
                )
            else:
                import shlex

                result = await sandbox.call_tool(
                    "runCommand",
                    {"command": f"bash -lc {shlex.quote(script)}", "timeout": arguments.get("timeout")},
                )
            return _command_result_output(script, result)

        from app.tools.code_interpreter import code_interpreter

        if language == "python":
            return _command_output(script, await code_interpreter({"code": script}))

        ext = {"javascript": ".js", "node": ".js", "bash": ".sh", "sh": ".sh"}.get(language, ".sh")
        runtime = {"javascript": "node", "node": "node", "bash": "bash", "sh": "sh"}.get(language, "bash")
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
        return _command_output(script, await code_interpreter({"code": code}))

    if api_name == "exportFile":
        path = arguments.get("path", "")
        filename = arguments.get("filename") or os.path.basename(path)
        if not path or ".." in path:
            return _tool_failure("Invalid path: path traversal is not allowed")

        topic_id = arguments.get("topicId") or arguments.get("topic_id")
        if topic_id:
            from datetime import UTC, datetime

            from app.services.cloud_sandbox import get_sandbox_service
            from app.services.cloud_sandbox.service import guess_mime_type, sandbox_file_hash
            from app.services.file_service import S3Client, create_file_record

            sandbox = get_sandbox_service(user_id, str(topic_id))
            source_path = sandbox.resolve_path(path)
            if not source_path.is_file():
                return _tool_failure(f"Failed to export file: {filename}")
            if "/" in filename or "\\" in filename:
                return _tool_failure("Invalid filename: filename must not contain path separators")

            data = source_path.read_bytes()
            file_hash = sandbox_file_hash(source_path)
            mime_type = guess_mime_type(source_path)
            today = datetime.now(UTC).date().isoformat()
            key = f"code-interpreter-exports/{today}/{topic_id}/{filename}"

            s3 = S3Client.from_settings()
            await s3.upload_bytes(key, data, mime_type)
            metadata = await s3.head(key)
            record = await create_file_record(
                session,
                user_id,
                file_hash=file_hash,
                file_type=metadata.get("content_type") or mime_type,
                name=filename,
                size=int(metadata.get("content_length") or len(data)),
                url=key,
            )
            size = int(metadata.get("content_length") or len(data))
            file_type = metadata.get("content_type") or mime_type
            return _tool_success(
                f"File exported successfully: {filename}\nDownload URL: {record['url']}",
                {
                    "fileId": record["file_id"],
                    "filename": filename,
                    "mimeType": file_type,
                    "size": size,
                    "url": record["url"],
                },
            )

        if not os.path.isfile(path):
            return _tool_failure(f"Failed to export file: {filename}")
        size = os.path.getsize(path)
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return _tool_success(
            f"File exported successfully: {filename}\nDownload URL: {path}",
            {"filename": filename, "mimeType": mime_type, "size": size, "url": path},
        )

    return json.dumps({"error": f"Unknown skills API: {api_name}"})


async def _skills_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    return await skills_with_context(api_name, arguments, session, user_id)


def _context_required(_: dict[str, Any]) -> str:
    return json.dumps({"error": "skills requires DB context"})


@register(
    "lobe-skills__activateSkill",
    description="Activate a skill by name and return its instructions/resources.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Skill name or identifier"}},
        "required": ["name"],
    },
)
async def _skills_activate_skill_context_required(arguments: dict[str, Any]) -> str:
    return _context_required(arguments)


@register("lobe-skills__findAll", description="List all installed skills (user and builtin).", parameters={"type": "object", "properties": {}})
async def _skills_find_all_context_required(arguments: dict[str, Any]) -> str:
    return _context_required(arguments)


@register(
    "lobe-skills__findByName",
    description="Find a skill by name or identifier and return its manifest and tools.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Skill name or identifier"}},
        "required": ["name"],
    },
)
async def _skills_find_by_name_context_required(arguments: dict[str, Any]) -> str:
    return _context_required(arguments)


@register(
    "lobe-skills__readReference",
    description="Read a resource file from an installed or builtin skill.",
    parameters={
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Skill name or identifier"},
            "path": {"type": "string", "description": "Resource path within the skill"},
        },
        "required": ["id", "path"],
    },
)
async def _skills_read_reference_context_required(arguments: dict[str, Any]) -> str:
    return _context_required(arguments)


@register(
    "lobe-skills__readResource",
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
    return _context_required(arguments)


@register(
    "lobe-skills__runCommand",
    description="Run a shell command in a sandboxed environment.",
    parameters={
        "type": "object",
        "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
        "required": ["command"],
    },
)
async def _skills_run_command_context_required(arguments: dict[str, Any]) -> str:
    return _context_required(arguments)


@register(
    "lobe-skills__execScript",
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
    return _context_required(arguments)


@register(
    "lobe-skills__exportFile",
    description="Export a file from the skill execution environment.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Filename for export"},
            "path": {"type": "string", "description": "Path to export"},
        },
        "required": ["path", "filename"],
    },
)
async def _skills_export_file_context_required(arguments: dict[str, Any]) -> str:
    return _context_required(arguments)


for _api in (
    "activateSkill",
    "findAll",
    "findByName",
    "readResource",
    "readReference",
    "runCommand",
    "execScript",
    "exportFile",
):
    register_context_handler(f"lobe-skills__{_api}", _skills_context_dispatch)
