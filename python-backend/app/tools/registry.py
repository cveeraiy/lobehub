"""Tool registry — central catalog of builtin tools with OpenAI-format schemas.

Each tool module uses ``@register`` to add itself on import.  The registry
provides:
- ``get_all_tool_schemas()`` — list of ``{"type": "function", "function": {...}}``
- ``get_tool(name)`` — retrieve a single ToolDef by name
- ``get_handler(name)`` — retrieve the async handler for a tool
- ``get_context_handler(name)`` — retrieve the context-aware handler (if any)
- ``tool_names()`` — list of registered tool names

Context-aware tools
-------------------
Some tools (memory, topic_reference, skills, etc.) need a DB session and
user_id at runtime.  These register a ``context_handler`` via
``register_context_handler(name, handler)``.  The dispatcher in
``tool_execution.py`` checks for context handlers first, falling back to
the plain handler (which returns a stub error).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Coroutine, Optional, Protocol, runtime_checkable

ToolHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, str]]


@runtime_checkable
class ContextHandler(Protocol):
    """Protocol for context-aware tool handlers.

    All context handlers receive at minimum:
    - arguments: the tool call arguments dict
    - session: the async DB session
    - user_id: the authenticated user's ID

    Additional keyword arguments (api_name, activated_tool_ids, etc.)
    are passed for tools that need them.
    """

    async def __call__(
        self,
        arguments: dict[str, Any],
        session: Any,
        user_id: str,
        **kwargs: Any,
    ) -> str: ...


@dataclasses.dataclass(frozen=True)
class ToolDef:
    """A registered builtin tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the function parameters
    handler: ToolHandler


_registry: dict[str, ToolDef] = {}
_context_handlers: dict[str, ContextHandler] = {}


def register(
    name: str,
    *,
    description: str,
    parameters: dict[str, Any],
) -> Callable[[ToolHandler], ToolHandler]:
    """Decorator to register a builtin tool.

    Usage::

        @register(
            "my_tool",
            description="Does something useful",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
        async def my_tool(args: dict) -> str:
            return "result"
    """

    def decorator(fn: ToolHandler) -> ToolHandler:
        _registry[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
        )
        return fn

    return decorator


def register_context_handler(name: str, handler: ContextHandler) -> None:
    """Register a context-aware handler for a tool that needs DB session."""
    _context_handlers[name] = handler


def get_tool(name: str) -> ToolDef | None:
    return _registry.get(name)


def get_handler(name: str) -> ToolHandler | None:
    """Get the plain async handler for a tool."""
    td = _registry.get(name)
    return td.handler if td else None


def get_context_handler(name: str) -> ContextHandler | None:
    """Get the context-aware handler for a tool (if registered)."""
    return _context_handlers.get(name)


def tool_names() -> list[str]:
    return list(_registry.keys())


def get_all_tool_schemas() -> list[dict[str, Any]]:
    """Return OpenAI function-calling format schemas for all registered tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": td.name,
                "description": td.description,
                "parameters": td.parameters,
            },
        }
        for td in _registry.values()
    ]
