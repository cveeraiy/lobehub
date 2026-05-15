"""User interaction builtin tool — ask clarifying questions (LangGraph interrupt)."""

from __future__ import annotations

import json
from typing import Any

from app.tools.registry import register


@register(
    "user_interaction",
    description="Ask the user a clarifying question before proceeding.",
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "Question to ask the user"},
            "type": {
                "type": "string",
                "description": "Interaction type",
                "enum": ["question", "confirm", "select"],
                "default": "question",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Options for select-type interaction",
            },
        },
        "required": ["question"],
    },
)
async def user_interaction(arguments: dict[str, Any]) -> str:
    """Ask the user a clarifying question.

    When used inside the LangGraph agent, this tool's response triggers
    an interrupt so the human can answer. Outside LangGraph, it returns
    the question as a structured prompt.
    """
    question = arguments.get("question", "")
    options = arguments.get("options")
    interaction_type = arguments.get("type", "question")

    if not question:
        return json.dumps({"error": "question is required"})

    result: dict[str, Any] = {
        "type": "user_interaction",
        "interaction_type": interaction_type,
        "question": question,
        "status": "awaiting_response",
    }
    if options:
        result["options"] = options

    return json.dumps(result)
