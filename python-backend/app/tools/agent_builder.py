"""Agent builder builtin tool — CRUD operations on agents from within a chat.

Supports 5 operations: create, update, delete, list, get.
"""

from __future__ import annotations

import json
from typing import Any

from app.tools.registry import register


@register(
    "agent_create",
    description="Create a new AI agent with a custom system prompt and configuration.",
    parameters={
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Unique slug identifier for the agent",
            },
            "title": {
                "type": "string",
                "description": "Display name of the agent",
            },
            "description": {
                "type": "string",
                "description": "Short description of what the agent does",
            },
            "system_role": {
                "type": "string",
                "description": "The system prompt that defines the agent's behavior",
            },
            "model": {
                "type": "string",
                "description": "LLM model to use (e.g. 'gpt-4o')",
            },
        },
        "required": ["slug", "title", "system_role"],
    },
)
async def agent_create(arguments: dict[str, Any]) -> str:
    """Stub — requires runtime session context."""
    return json.dumps({
        "note": "agent_create requires runtime session context",
        "slug": arguments.get("slug"),
        "title": arguments.get("title"),
    })


@register(
    "agent_update",
    description="Update an existing agent's configuration.",
    parameters={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "ID of the agent to update",
            },
            "title": {"type": "string", "description": "New display name"},
            "description": {"type": "string", "description": "New description"},
            "system_role": {"type": "string", "description": "New system prompt"},
            "model": {"type": "string", "description": "New model"},
        },
        "required": ["agent_id"],
    },
)
async def agent_update(arguments: dict[str, Any]) -> str:
    """Stub — requires runtime session context."""
    return json.dumps({
        "note": "agent_update requires runtime session context",
        "agent_id": arguments.get("agent_id"),
    })


@register(
    "agent_delete",
    description="Delete an agent by ID.",
    parameters={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "ID of the agent to delete",
            },
        },
        "required": ["agent_id"],
    },
)
async def agent_delete(arguments: dict[str, Any]) -> str:
    """Stub — requires runtime session context."""
    return json.dumps({
        "note": "agent_delete requires runtime session context",
        "agent_id": arguments.get("agent_id"),
    })


@register(
    "agent_list",
    description="List all agents available to the user.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
async def agent_list(arguments: dict[str, Any]) -> str:
    """Stub — requires runtime session context."""
    return json.dumps({"note": "agent_list requires runtime session context"})


@register(
    "agent_get",
    description="Get details of a specific agent by ID.",
    parameters={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "ID of the agent to retrieve",
            },
        },
        "required": ["agent_id"],
    },
)
async def agent_get(arguments: dict[str, Any]) -> str:
    """Stub — requires runtime session context."""
    return json.dumps({
        "note": "agent_get requires runtime session context",
        "agent_id": arguments.get("agent_id"),
    })
