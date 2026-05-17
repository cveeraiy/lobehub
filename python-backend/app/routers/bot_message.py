"""Bot Message router — platform messaging dispatch.

Mirrors TS ``botMessageRouter`` — 18 procedures for cross-platform bot messaging.

The TS implementation uses platform-specific adapter packages
(@lobechat/chat-adapter-*) that are not available in Python.
This router provides the endpoint stubs so the SPA's dynamic
``router[apiName]`` dispatch doesn't 404. Platform adapters can
be wired in later.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot-message", tags=["bot-message"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class BotActionBody(BaseModel):
    """Generic body accepted by all bot-message endpoints."""
    bot_id: str
    channel_id: Optional[str] = None
    content: Optional[str] = None
    message_id: Optional[str] = None
    user_id_target: Optional[str] = None
    emoji: Optional[str] = None
    query: Optional[str] = None
    thread_id: Optional[str] = None
    name: Optional[str] = None
    server_id: Optional[str] = None
    member_id: Optional[str] = None
    filter: Optional[str] = None
    limit: Optional[int] = None
    before: Optional[str] = None
    after: Optional[str] = None
    cursor: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reply_to: Optional[str] = None
    embeds: Optional[list[dict[str, Any]]] = None
    author_id: Optional[str] = None
    question: Optional[str] = None
    options: Optional[list[str]] = None
    duration: Optional[int] = None
    multiple_answers: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _not_impl(action: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": f"Bot message action '{action}' is not yet implemented in the Python backend. "
                 "Platform adapter packages are required.",
    }


# ---------------------------------------------------------------------------
# Endpoints — one per TS procedure
# ---------------------------------------------------------------------------

@router.post("/send-message")
async def send_message(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("sendMessage")


@router.post("/send-direct-message")
async def send_direct_message(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("sendDirectMessage")


@router.get("/read-messages")
async def read_messages(
    botId: str,
    channelId: str,
    limit: Optional[int] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    cursor: Optional[str] = None,
    startTime: Optional[str] = None,
    endTime: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("readMessages")


@router.post("/edit-message")
async def edit_message(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("editMessage")


@router.post("/delete-message")
async def delete_message(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("deleteMessage")


@router.get("/search-messages")
async def search_messages(
    botId: str,
    channelId: str,
    query: str,
    authorId: Optional[str] = None,
    limit: Optional[int] = None,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("searchMessages")


@router.post("/react-to-message")
async def react_to_message(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("reactToMessage")


@router.get("/get-reactions")
async def get_reactions(
    botId: str, channelId: str, messageId: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("getReactions")


@router.post("/pin-message")
async def pin_message(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("pinMessage")


@router.post("/unpin-message")
async def unpin_message(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("unpinMessage")


@router.get("/list-pins")
async def list_pins(
    botId: str, channelId: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("listPins")


@router.get("/channel-info")
async def get_channel_info(
    botId: str, channelId: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("getChannelInfo")


@router.get("/list-channels")
async def list_channels(
    botId: str, serverId: Optional[str] = None, filter: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("listChannels")


@router.get("/member-info")
async def get_member_info(
    botId: str, memberId: str, serverId: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("getMemberInfo")


@router.post("/create-thread")
async def create_thread(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("createThread")


@router.get("/list-threads")
async def list_threads(
    botId: str, channelId: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    return _not_impl("listThreads")


@router.post("/reply-to-thread")
async def reply_to_thread(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("replyToThread")


@router.post("/create-poll")
async def create_poll(body: BotActionBody, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _not_impl("createPoll")
