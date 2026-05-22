"""Activator builtin tool — dynamic tool/skill discovery and activation."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)


# ── Context-aware implementation ─────────────────────────────────────


async def activator_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    activated_tool_ids: set[str] | None = None,
) -> str:
    """Activator tool — activate tools/skills so their schemas become available.

    ``activated_tool_ids`` is a mutable set maintained per agent operation.
    When a tool is activated, its identifier is added to this set and its
    manifest (including tool schemas) is returned so the LLM knows what
    new APIs are available.
    """
    from sqlalchemy import and_, select

    from app.models.skill import AgentSkill
    from app.skills.builtin import get_builtin_skill

    if activated_tool_ids is None:
        activated_tool_ids = set()

    if api_name == "activateTools":
        identifiers = arguments.get("identifiers", [])
        if not identifiers:
            return json.dumps({"error": "No tool identifiers provided."})

        activated: list[dict[str, Any]] = []
        already_active: list[str] = []
        not_found: list[str] = []

        for ident in identifiers:
            if ident in activated_tool_ids:
                already_active.append(ident)
                continue

            # Try user skills
            stmt = select(AgentSkill).where(
                and_(
                    (AgentSkill.identifier == ident) | (AgentSkill.display_name == ident),
                    AgentSkill.user_id == user_id,
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()

            if row:
                manifest = row.manifest or {}
                tools = manifest.get("tools", [])
                activated_tool_ids.add(ident)
                activated.append({
                    "identifier": row.identifier,
                    "name": row.display_name or row.identifier,
                    "description": row.description,
                    "tools": tools,
                    "system_role": manifest.get("prompt") or manifest.get("systemRole"),
                })
                continue

            # Try builtin skills
            builtin = get_builtin_skill(ident)
            if builtin:
                activated_tool_ids.add(ident)
                activated.append({
                    "identifier": builtin["identifier"],
                    "name": builtin["name"],
                    "description": builtin["description"],
                    "tools": builtin.get("tools", []),
                    "system_role": builtin.get("prompt"),
                })
                continue

            not_found.append(ident)

        # Build response
        parts: list[str] = []
        if activated:
            parts.append("Successfully activated:")
            for a in activated:
                parts.append(f"\n## {a['name']} ({a['identifier']})")
                if a.get("system_role"):
                    parts.append(a["system_role"])
                if a["tools"]:
                    parts.append("\nAvailable APIs:")
                    for t in a["tools"]:
                        fn = t.get("function", t)
                        parts.append(f"- **{fn.get('name', '?')}**: {fn.get('description', '')}")
        if already_active:
            parts.append(f"\nAlready active: {', '.join(already_active)}")
        if not_found:
            parts.append(f"\nNot found: {', '.join(not_found)}")

        return json.dumps({
            "content": "\n".join(parts),
            "activated": [a["identifier"] for a in activated],
            "already_active": already_active,
            "not_found": not_found,
            "activated_details": activated,
            "success": True,
        })

    if api_name == "activateSkill":
        name = arguments.get("name", "")
        if not name:
            return json.dumps({"error": "name is required"})

        # Delegate to activateTools with single identifier
        return await activator_with_context(
            "activateTools",
            {"identifiers": [name]},
            session,
            user_id,
            activated_tool_ids=activated_tool_ids,
        )

    return json.dumps({"error": f"Unknown activator API: {api_name}"})


# ── Dispatcher for double-underscore routing ─────────────────────────


async def _activator_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    activated_tool_ids: set[str] | None = None,
    **kwargs: Any,
) -> str:
    return await activator_with_context(
        api_name, arguments, session, user_id,
        activated_tool_ids=activated_tool_ids,
    )


# ── Registered tools (context-backed) ───────────────────────────────


@register(
    "activator__activateTools",
    description="Activate tools/skills so their full API schemas become available. "
    "Call this before using any tool that is not yet activated.",
    parameters={
        "type": "object",
        "properties": {
            "identifiers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Array of tool/skill identifiers to activate",
            },
        },
        "required": ["identifiers"],
    },
)
async def _activate_tools_context_required(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "activator requires DB context"})


@register(
    "activator__activateSkill",
    description="Activate a single skill by name so its tools become available.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name or identifier to activate"},
        },
        "required": ["name"],
    },
)
async def _activate_skill_context_required(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "activator requires DB context"})


# Register context handlers
for _api in ("activateTools", "activateSkill"):
    register_context_handler(f"activator__{_api}", _activator_context_dispatch)
