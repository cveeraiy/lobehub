"""Agent notification callback router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.topic import Topic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent-notify", tags=["Agent Notify"])


class NotifyBody(BaseModel):
    content: str
    topic_id: str
    agent_id: str | None = None
    thread_id: str | None = None


@router.post("/notify")
async def notify(
    body: NotifyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    topic = (
        await session.execute(select(Topic).where(and_(Topic.id == body.topic_id, Topic.user_id == user_id)))
    ).scalar_one_or_none()
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Topic {body.topic_id} not found")

    agent_id = body.agent_id or topic.agent_id
    if not agent_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Topic {body.topic_id} has no associated agent and no agent_id was provided",
        )

    try:
        result = await _exec_agent_notify(user_id, agent_id, body.topic_id, body.thread_id, body.content)
    except Exception as exc:
        logger.exception("agent notify exec_agent failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to trigger agent: {exc}") from exc

    return {"operationId": result.operation_id, "topicId": body.topic_id}


async def _exec_agent_notify(user_id: str, agent_id: str, topic_id: str, thread_id: str | None, content: str):
    from app.services.ai_agent import AiAgentService, ExecAgentParams
    from app.services.ai_agent.types import AppContext

    return await AiAgentService(user_id).exec_agent(
        ExecAgentParams(
            agent_id=agent_id,
            app_context=AppContext(topic_id=topic_id, thread_id=thread_id),
            prompt=content,
            trigger="api",
        )
    )
