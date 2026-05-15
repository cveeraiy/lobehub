"""Tool execution service — dispatch builtin tools + MCP tool calls.

Handles the ``tool_calls`` returned by an LLM response:
1. Checks for a context-aware handler (needs DB session + user_id).
2. Falls back to the plain builtin handler from ``app.tools``.
3. Falls back to MCP service.
4. Returns tool results that can be fed back to the LLM.

All tool definitions live in ``app/tools/`` (one file per tool domain).
The unified registry in ``app.tools.registry`` is the single source of truth
for handlers, context handlers, schemas, and tool names.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from app.tools import get_all_tool_schemas, get_context_handler, get_handler, tool_names

logger = logging.getLogger(__name__)


# ── Dispatch ─────────────────────────────────────────────────────────

async def execute_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    mcp_client: Optional[Any] = None,
) -> str:
    """Execute a single tool call and return the result string.

    Tries builtin tools first, then falls back to MCP.
    """
    handler = get_handler(tool_name)
    if handler:
        try:
            return await handler(arguments)
        except Exception as exc:
            logger.error("Builtin tool %s failed: %s", tool_name, exc, exc_info=True)
            return json.dumps({"error": str(exc)})

    # MCP fallback
    if mcp_client is not None:
        try:
            if isinstance(mcp_client, dict):
                from app.services.mcp_service import mcp_service
                result = await mcp_service.call_tool(
                    client_params=mcp_client,
                    tool_name=tool_name,
                    args=arguments,
                )
                return result.content
            else:
                from app.services.mcp_service import call_tool
                return await call_tool(mcp_client, tool_name, arguments)
        except Exception as exc:
            logger.error("MCP tool %s failed: %s", tool_name, exc, exc_info=True)
            return json.dumps({"error": str(exc)})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


async def process_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    mcp_client: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """Process a list of LLM tool_calls and return tool messages.

    Independent tool calls are executed concurrently via ``asyncio.gather``.

    Each returned dict is an OpenAI-format tool message::

        {"role": "tool", "tool_call_id": "...", "content": "..."}
    """

    async def _run_one(tc: dict[str, Any]) -> dict[str, Any]:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        raw_args = fn.get("arguments", "{}")

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {}

        content = await execute_tool_call(name, args, mcp_client=mcp_client)
        return {
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "content": content,
        }

    results = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
    return list(results)


# ── Context-aware dispatch ───────────────────────────────────────────
# Tools that need a DB session + user_id register context handlers in
# the unified registry.  This function checks for them first, then
# falls back to the generic dispatch.


async def execute_tool_call_with_context(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    session: Optional[Any] = None,
    user_id: Optional[str] = None,
    mcp_client: Optional[Any] = None,
    activated_tool_ids: Optional[set[str]] = None,
) -> str:
    """Execute a tool call with runtime DB context.

    **Important**: ``activated_tool_ids`` must be pre-created by the caller
    if activation state should persist across calls.  Passing ``None`` means
    activations within this single call won't be visible to subsequent calls.
    """
    if activated_tool_ids is None:
        activated_tool_ids = set()

    if session and user_id:
        # For double-underscore tools (skills__findAll, etc.), extract api_name
        if "__" in tool_name:
            ctx_handler = get_context_handler(tool_name)
            if ctx_handler:
                api_name = tool_name.split("__", 1)[1]
                try:
                    return await ctx_handler(
                        arguments, session, user_id,
                        api_name=api_name,
                        activated_tool_ids=activated_tool_ids,
                    )
                except Exception as exc:
                    logger.error("Context tool %s failed: %s", tool_name, exc, exc_info=True)
                    return json.dumps({"error": str(exc)})

        # For simple-named context tools (memory_search, topic_reference, knowledge_base_search, etc.)
        ctx_handler = get_context_handler(tool_name)
        if ctx_handler:
            try:
                return await ctx_handler(arguments, session, user_id)
            except Exception as exc:
                logger.error("Context tool %s failed: %s", tool_name, exc, exc_info=True)
                return json.dumps({"error": str(exc)})

        # Agent CRUD tools
        if tool_name.startswith("agent_"):
            return await _handle_agent_tool(tool_name, arguments, session, user_id)

    # Fall back to generic dispatch (handles all context-free builtins + MCP)
    return await execute_tool_call(tool_name, arguments, mcp_client=mcp_client)


async def _handle_agent_tool(
    tool_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Handle agent_create/update/delete/list/get with DB context."""
    from sqlalchemy import delete as sa_delete, select, update as sa_update
    from app.models.agent import Agent

    if tool_name == "agent_list":
        from sqlalchemy import desc
        stmt = select(Agent).where(Agent.user_id == user_id).order_by(desc(Agent.updated_at)).limit(20)
        rows = (await session.execute(stmt)).scalars().all()
        return json.dumps([{"id": r.id, "title": r.title, "slug": r.slug} for r in rows])

    if tool_name == "agent_get":
        agent_id = arguments.get("agent_id", "")
        from sqlalchemy import and_
        stmt = select(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user_id))
        agent = (await session.execute(stmt)).scalar_one_or_none()
        if not agent:
            return json.dumps({"error": "Agent not found"})
        return json.dumps({"id": agent.id, "title": agent.title, "slug": agent.slug, "description": agent.description})

    if tool_name == "agent_create":
        agent = Agent(
            user_id=user_id,
            slug=arguments.get("slug", ""),
            title=arguments.get("title", ""),
            description=arguments.get("description"),
        )
        session.add(agent)
        await session.flush()
        return json.dumps({"id": agent.id, "slug": agent.slug})

    if tool_name == "agent_update":
        agent_id = arguments.get("agent_id", "")
        _UPDATABLE_AGENT_FIELDS = {"title", "description", "slug", "system_role", "model"}
        values = {
            k: v for k, v in arguments.items()
            if k in _UPDATABLE_AGENT_FIELDS and v is not None
        }
        if values:
            from sqlalchemy import and_
            stmt = sa_update(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user_id)).values(**values)
            await session.execute(stmt)
        return json.dumps({"ok": True})

    if tool_name == "agent_delete":
        agent_id = arguments.get("agent_id", "")
        from sqlalchemy import and_
        await session.execute(sa_delete(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user_id)))
        return json.dumps({"ok": True})

    return json.dumps({"error": f"Unknown agent tool: {tool_name}"})


def list_builtin_tools() -> list[str]:
    """Return names of all registered builtin tools."""
    return tool_names()


def get_builtin_tool_schemas() -> list[dict[str, Any]]:
    """Return OpenAI-format tool schemas for all builtin tools."""
    return get_all_tool_schemas()
