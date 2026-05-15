"""Topic reference builtin tool — fetch conversation history from another topic."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)


async def topic_reference_with_context(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Fetch topic summary or recent messages from the database."""
    from sqlalchemy import and_, desc, select
    from app.models.topic import Topic
    from app.models.message import Message

    topic_id = arguments.get("topic_id", "")
    if not topic_id:
        return json.dumps({"error": "topic_id is required"})

    # Fetch the topic
    stmt = select(Topic).where(
        and_(Topic.id == topic_id, Topic.user_id == user_id)
    )
    topic = (await session.execute(stmt)).scalar_one_or_none()
    if not topic:
        return json.dumps({"error": f"Topic not found: {topic_id}"})

    result: dict[str, Any] = {
        "topic_id": topic_id,
        "title": topic.title,
    }

    # Include history_summary if available
    if topic.history_summary:
        result["summary"] = topic.history_summary

    # Fetch recent messages
    msg_stmt = (
        select(Message)
        .where(
            and_(
                Message.topic_id == topic_id,
                Message.user_id == user_id,
            )
        )
        .order_by(desc(Message.created_at))
        .limit(20)
    )
    messages = list((await session.execute(msg_stmt)).scalars().all())
    messages.reverse()  # Chronological order

    result["messages"] = [
        {
            "role": m.role,
            "content": (m.content or "")[:500],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    return json.dumps(result)


@register(
    "topic_reference",
    description="Fetch conversation history or summary from another topic.",
    parameters={
        "type": "object",
        "properties": {
            "topic_id": {"type": "string", "description": "ID of the topic to reference"},
        },
        "required": ["topic_id"],
    },
)
async def _topic_reference_stub(arguments: dict[str, Any]) -> str:
    """Stub — real implementation routed via context handler."""
    return json.dumps({"error": "topic_reference requires DB context"})


register_context_handler("topic_reference", topic_reference_with_context)
