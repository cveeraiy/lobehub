"""Skill engine — system prompt injection and tool schema resolution.

Skills are agent capabilities that modify the system prompt and/or
register tool schemas.  Each skill definition includes:
- A prompt template (Jinja2-like or plain text)
- Optional tool schemas (OpenAI function-calling format)
- Optional knowledge base IDs for automatic RAG

This module resolves an agent's skill configuration into:
1. An augmented system prompt
2. A list of tool schemas for the LLM ``tools`` parameter
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentKnowledgeBase
from app.models.skill import AgentSkill

logger = logging.getLogger(__name__)


async def get_agent_system_prompt(
    session: AsyncSession,
    user_id: str,
    agent_id: str,
) -> str | None:
    """Return the agent's base system prompt."""
    stmt = select(Agent.system_role).where(
        and_(Agent.id == agent_id, Agent.user_id == user_id)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row


async def get_agent_skills(
    session: AsyncSession,
    user_id: str,
    agent_id: str,
) -> list[AgentSkill]:
    """Return all skills attached to an agent via ``Agent.plugins``."""
    # Agent.plugins is a JSON array of skill identifiers
    agent_stmt = select(Agent.plugins).where(
        and_(Agent.id == agent_id, Agent.user_id == user_id)
    )
    plugins = (await session.execute(agent_stmt)).scalar_one_or_none()
    if not plugins:
        return []

    stmt = (
        select(AgentSkill)
        .where(
            and_(
                AgentSkill.identifier.in_(plugins),
                AgentSkill.user_id == user_id,
            )
        )
    )
    return list((await session.execute(stmt)).scalars().all())


def build_system_prompt(
    base_prompt: str | None,
    skills: list[AgentSkill],
    *,
    user_context: Optional[str] = None,
) -> str:
    """Assemble the final system prompt from base + skill prompts.

    Parameters
    ----------
    base_prompt : str | None
        The agent's core system role prompt.
    skills : list[AgentSkill]
        Resolved skill records (each has ``manifest.prompt``).
    user_context : str | None
        Optional per-request context (e.g. current date, user timezone).
    """
    parts: list[str] = []

    if base_prompt:
        parts.append(base_prompt)

    # Inject skill prompts
    for skill in skills:
        manifest = skill.manifest or {}
        prompt = manifest.get("prompt") or manifest.get("systemPrompt")
        if prompt:
            parts.append(f"## Skill: {manifest.get('name', 'unnamed')}\n{prompt}")

    if user_context:
        parts.append(f"## Context\n{user_context}")

    return "\n\n".join(parts) if parts else ""


def collect_tool_schemas(skills: list[AgentSkill]) -> list[dict[str, Any]]:
    """Extract OpenAI-format tool schemas from skill manifests.

    Each skill manifest may contain a ``tools`` array of function schemas.
    """
    tools: list[dict[str, Any]] = []
    for skill in skills:
        manifest = skill.manifest or {}
        skill_tools = manifest.get("tools") or manifest.get("functions") or []
        for tool_def in skill_tools:
            # Ensure wrapper format: {"type": "function", "function": {...}}
            if "function" in tool_def:
                tools.append(tool_def)
            elif "name" in tool_def:
                tools.append({"type": "function", "function": tool_def})
    return tools


async def resolve_agent_context(
    session: AsyncSession,
    user_id: str,
    agent_id: str,
    *,
    user_context: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve the full LLM call context for an agent.

    Returns
    -------
    dict with keys:
        - ``system_prompt`` : str
        - ``tools`` : list[dict]  (OpenAI function-calling schemas)
        - ``kb_ids`` : list[str]  (knowledge base IDs for RAG)
    """
    base_prompt = await get_agent_system_prompt(session, user_id, agent_id)
    skills = await get_agent_skills(session, user_id, agent_id)

    system_prompt = build_system_prompt(base_prompt, skills, user_context=user_context)
    tools = collect_tool_schemas(skills)

    # Collect KB IDs from agents_knowledge_bases junction table
    kb_stmt = select(AgentKnowledgeBase.knowledge_base_id).where(
        and_(
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.user_id == user_id,
            AgentKnowledgeBase.enabled == True,  # noqa: E712
        )
    )
    kb_rows = (await session.execute(kb_stmt)).scalars().all()
    kb_ids = list(kb_rows)

    return {
        "system_prompt": system_prompt,
        "tools": tools,
        "kb_ids": kb_ids,
    }
