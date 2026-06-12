"""AI Chat router — server-side structured chat and message creation.

Mirrors TS ``aiChatRouter`` — two procedures:
  - ``outputJSON`` — structured object generation via LLM
  - ``sendMessageInServer`` — create user + assistant messages atomically
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message
from app.models.topic import Topic
from app.models.topic_ext import Thread
from app.routers.messages import _msg_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-chat", tags=["ai-chat"])

LOADING_FLAT = "..."


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class OutputJSONBody(BaseModel):
    messages: list[dict[str, Any]]
    model: str
    provider: str
    schema_: Optional[dict[str, Any]] = None  # renamed to avoid clash with BaseModel.schema
    tools: Optional[list[Any]] = None

    class Config:
        populate_by_name = True
        # Accept "schema" from JSON
        fields = {"schema_": {"alias": "schema"}}


class NewUserMessage(BaseModel):
    content: str
    files: Optional[list[dict[str, Any]]] = None
    editor_data: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
    page_selections: Optional[list[dict[str, Any]]] = None
    parent_id: Optional[str] = None


class NewAssistantMessage(BaseModel):
    model: Optional[str] = None
    provider: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class NewTopicDef(BaseModel):
    title: Optional[str] = None
    trigger: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    topic_message_ids: Optional[list[str]] = None


class NewThreadDef(BaseModel):
    source_message_id: Optional[str] = None
    parent_thread_id: Optional[str] = None
    title: Optional[str] = None
    type: str = "standalone"


class PreloadMessage(BaseModel):
    content: str
    role: str
    metadata: Optional[dict[str, Any]] = None
    plugin: Optional[dict[str, Any]] = None
    tool_call_id: Optional[str] = None
    tools: Optional[list[Any]] = None


class SendMessageInServerBody(BaseModel):
    agent_id: Optional[str] = None
    group_id: Optional[str] = None
    session_id: Optional[str] = None
    topic_id: Optional[str] = None
    thread_id: Optional[str] = None
    topic_filter: Optional[dict[str, Any]] = None
    new_topic: Optional[NewTopicDef] = None
    new_thread: Optional[NewThreadDef] = None
    new_user_message: NewUserMessage
    new_assistant_message: NewAssistantMessage
    preload_messages: Optional[list[PreloadMessage]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/output-json")
async def output_json(
    body: OutputJSONBody,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Structured object generation via LLM. Mirrors TS ``aiChat.outputJSON``."""
    # This requires the model runtime initialization from DB — delegating to
    # the agent runtime's LLM service for model config resolution.
    try:
        from app.services.llm_service import LLMService
        llm = LLMService(user_id)
        result = await llm.generate_object(
            messages=body.messages,
            model=body.model,
            provider=body.provider,
            schema=body.schema_,
            tools=body.tools,
        )
        return result
    except ImportError:
        raise HTTPException(status_code=501, detail="LLM service not available")
    except Exception as exc:
        logger.error("outputJSON failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/send-message")
async def send_message_in_server(
    body: SendMessageInServerBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create user + assistant messages atomically. Mirrors TS ``aiChat.sendMessageInServer``."""

    topic_id = body.topic_id
    thread_id = body.thread_id
    session_id = body.session_id
    created_thread_id = None
    is_create_new_topic = False

    # Create topic if requested
    if body.new_topic:
        is_create_new_topic = True
        t = Topic(
            user_id=user_id,
            title=body.new_topic.title,
            session_id=session_id,
            agent_id=body.agent_id,
            metadata_=body.new_topic.metadata,
        )
        session.add(t)
        await session.flush()
        topic_id = t.id

    # Create thread if requested
    if body.new_thread:
        thr = Thread(
            topic_id=topic_id or "",
            user_id=user_id,
            title=body.new_thread.title,
            type=body.new_thread.type,
            source_message_id=body.new_thread.source_message_id,
            parent_thread_id=body.new_thread.parent_thread_id,
        )
        session.add(thr)
        await session.flush()
        thread_id = thr.id
        created_thread_id = thr.id

    parent_id = body.new_user_message.parent_id

    # Preload messages
    if body.preload_messages:
        for pm in body.preload_messages:
            pre_msg = Message(
                user_id=user_id,
                topic_id=topic_id,
                thread_id=thread_id,
                agent_id=body.agent_id,
                role=pm.role,
                content=pm.content,
                parent_id=parent_id,
                group_id=body.group_id,
                metadata_=pm.metadata,
                tool_call_id=pm.tool_call_id,
                tools=pm.tools,
            )
            session.add(pre_msg)
            await session.flush()
            parent_id = pre_msg.id

    # Create user message
    user_meta = body.new_user_message.metadata
    if body.new_user_message.page_selections:
        user_meta = {**(user_meta or {}), "pageSelections": body.new_user_message.page_selections}

    user_msg = Message(
        user_id=user_id,
        topic_id=topic_id,
        thread_id=thread_id,
        agent_id=body.agent_id,
        role="user",
        content=body.new_user_message.content,
        editor_data=body.new_user_message.editor_data,
        parent_id=parent_id,
        group_id=body.group_id,
        metadata_=user_meta,
    )
    session.add(user_msg)
    await session.flush()

    # Create assistant message
    asst_msg = Message(
        user_id=user_id,
        topic_id=topic_id,
        thread_id=thread_id,
        agent_id=body.agent_id,
        role="assistant",
        content=LOADING_FLAT,
        model=body.new_assistant_message.model,
        provider=body.new_assistant_message.provider,
        parent_id=user_msg.id,
        group_id=body.group_id,
        metadata_=body.new_assistant_message.metadata,
    )
    session.add(asst_msg)
    await session.flush()

    stmt = select(Message).where(Message.user_id == user_id)
    if session_id:
        stmt = stmt.where(Message.session_id == session_id)
    if topic_id:
        stmt = stmt.where(Message.topic_id == topic_id)
    if body.agent_id:
        stmt = stmt.where(Message.agent_id == body.agent_id)
    if thread_id:
        stmt = stmt.where(Message.thread_id == thread_id)
    messages = (await session.execute(stmt.order_by(Message.created_at))).scalars().all()

    return {
        "assistantMessageId": asst_msg.id,
        "createdThreadId": created_thread_id,
        "isCreateNewTopic": is_create_new_topic,
        "messages": [_msg_dict(m) for m in messages],
        "topicId": topic_id,
        "userMessageId": user_msg.id,
    }
