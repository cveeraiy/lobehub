"""Follow-up Actions router — extract suggested follow-up actions from conversation via LLM."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message
from app.services import llm_service

router = APIRouter(prefix="/api/follow-up", tags=["Follow Up"])

FOLLOW_UP_SYSTEM_PROMPT = """You are an assistant that suggests helpful follow-up actions based on a conversation.

Given the last few messages, suggest 2-4 concise follow-up actions the user might want to take.
Return a JSON array of objects with "label" (short action text) and "prompt" (what to send to continue the conversation).

Example:
[
  {"label": "Explain further", "prompt": "Can you explain that in more detail?"},
  {"label": "Show code example", "prompt": "Can you show me a code example?"}
]

Only return valid JSON. No extra text."""


class ExtractFollowUpBody(BaseModel):
    topic_id: str = Field(..., alias="topicId")
    message_limit: int = Field(default=6, alias="messageLimit")
    hint: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


def _empty_result(message_id: str = "") -> dict[str, Any]:
    return {"chips": [], "messageId": message_id}


def _normalize_actions(actions: Any) -> list[dict[str, str]]:
    if not isinstance(actions, list):
        return []

    chips: list[dict[str, str]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        label = str(action.get("label") or "").strip()
        message = str(action.get("message") or action.get("prompt") or label).strip()
        if not label or not message:
            continue
        chips.append({"label": label[:40], "message": message[:200]})
        if len(chips) >= 4:
            break

    return chips


@router.post("/extract")
async def extract_follow_up_actions(
    body: ExtractFollowUpBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Extract follow-up action suggestions from recent messages in a topic."""
    stmt = (
        select(Message)
        .where(and_(Message.topic_id == body.topic_id, Message.user_id == user_id))
        .order_by(desc(Message.created_at))
        .limit(body.message_limit)
    )
    messages = (await session.execute(stmt)).scalars().all()

    if not messages:
        return _empty_result()

    assistant_message_id = next(
        (m.id for m in messages if m.role == "assistant" and m.content),
        "",
    )

    # Build conversation for LLM
    conversation: list[dict[str, Any]] = [{"role": "system", "content": FOLLOW_UP_SYSTEM_PROMPT}]
    # Reverse to chronological order
    for m in reversed(messages):
        if m.role in ("user", "assistant") and m.content:
            conversation.append({"role": m.role, "content": m.content[:500]})

    if len(conversation) <= 1:
        return _empty_result(assistant_message_id)

    conversation.append({"role": "user", "content": "Based on the conversation above, suggest follow-up actions."})

    try:
        response = await llm_service.chat(
            conversation,
            model="openai/gpt-4o-mini",
            stream=False,
            temperature=0.3,
            max_tokens=300,
        )
        content = response.choices[0].message.content  # type: ignore[attr-defined]

        import json
        actions = json.loads(content)
        if not isinstance(actions, list):
            actions = []
        return {"chips": _normalize_actions(actions), "messageId": assistant_message_id}
    except Exception:
        return _empty_result(assistant_message_id)
