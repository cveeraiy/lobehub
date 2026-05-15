"""Brief server runtime tool — create briefs and request checkpoints.

Ports TS ``serverRuntimes/brief.ts``:
- createBrief: Create a brief (decision, result, insight, error)
- requestCheckpoint: Pause task and create a decision brief
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

BRIEF_IDENTIFIER = "lobehub_brief"

# Default brief actions by type (mirrors TS DEFAULT_BRIEF_ACTIONS)
_DEFAULT_ACTIONS: dict[str, list[dict[str, str]]] = {
    "decision": [
        {"key": "approve", "label": "Approve", "type": "primary"},
        {"key": "reject", "label": "Reject", "type": "default"},
        {"key": "feedback", "label": "Feedback", "type": "default"},
    ],
    "insight": [
        {"key": "acknowledge", "label": "Got it", "type": "primary"},
    ],
    "error": [
        {"key": "retry", "label": "Retry", "type": "primary"},
        {"key": "acknowledge", "label": "Dismiss", "type": "default"},
    ],
}


async def brief_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    **kwargs: Any,
) -> str:
    """Brief tool — create briefs and checkpoints."""
    from sqlalchemy import update as sa_update
    from app.models.task import Brief, Task

    task_id = kwargs.get("task_id")

    if api_name == "createBrief":
        title = arguments.get("title", "")
        summary = arguments.get("summary", "")
        brief_type = arguments.get("type", "insight")
        priority = arguments.get("priority", "info")
        custom_actions = arguments.get("actions")

        if not title or not summary:
            return json.dumps({"success": False, "content": "title and summary are required"})

        # Result briefs have hardcoded approve action; custom actions are ignored
        if brief_type == "result":
            actions = None
        else:
            actions = custom_actions or _DEFAULT_ACTIONS.get(brief_type, [])

        brief = Brief(
            user_id=user_id,
            task_id=task_id,
            type=brief_type,
            title=title,
            summary=summary,
            priority=priority,
            actions=actions,
        )
        session.add(brief)
        await session.flush()
        await session.refresh(brief)

        content = (
            f"📋 Brief created [{brief.id}]\n"
            f"Type: {brief_type} | Priority: {priority}\n"
            f"Title: {title}\n"
            f"Summary: {summary}"
        )

        return json.dumps({"success": True, "content": content})

    elif api_name == "requestCheckpoint":
        reason = arguments.get("reason", "")
        if not reason:
            return json.dumps({"success": False, "content": "reason is required"})

        # Pause the task
        if task_id:
            await session.execute(
                sa_update(Task)
                .where(Task.id == task_id, Task.created_by_user_id == user_id)
                .values(status="paused")
            )

        # Create a decision brief
        brief = Brief(
            user_id=user_id,
            task_id=task_id,
            type="decision",
            title="Checkpoint requested",
            summary=reason,
            priority="normal",
        )
        session.add(brief)
        await session.flush()

        content = (
            f"⏸️ Checkpoint created\n"
            f"Reason: {reason}\n"
            f"Task paused — waiting for user decision."
        )

        return json.dumps({"success": True, "content": content})

    return json.dumps({"error": f"Unknown brief API: {api_name}"})


@register(
    BRIEF_IDENTIFIER,
    description="Brief management — create briefs for user notification and request checkpoints. "
                "APIs: createBrief, requestCheckpoint.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "enum": ["createBrief", "requestCheckpoint"],
            },
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def brief_tool_stub(args: dict[str, Any]) -> str:
    return json.dumps({"error": "Brief tool requires server context (session + user_id)."})


register_context_handler(BRIEF_IDENTIFIER, brief_with_context)
