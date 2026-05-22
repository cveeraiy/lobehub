"""Bot Message router — platform messaging dispatch.

Mirrors TS ``botMessageRouter`` for direct platform messaging operations.
Python implements the operations where platform REST APIs are available
without the TypeScript adapter packages.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent_ops import AgentBotProvider
from app.routers.agent_bot_providers import _decode_credentials
from app.services.bot.platforms.discord.client import DiscordClient
from app.services.bot.platforms.line.client import LineClient
from app.services.bot.platforms.qq.client import QQClient
from app.services.bot.platforms.slack.client import SlackClient
from app.services.bot.platforms.telegram.client import TelegramClient
from app.services.bot.platforms.webex.client import WebexClient
from app.services.bot.platforms.wechat.client import WechatClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot-message", tags=["bot-message"])

DEFAULT_BOT_HISTORY_LIMIT = 10
MAX_BOT_HISTORY_LIMIT = 100


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
        "error": f"Bot message action '{action}' is not supported by the current Python platform runtime.",
    }


def _unsupported(platform: str, action: str) -> None:
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"Bot message action '{action}' is not supported on {platform} in the Python backend.",
    )


def _required(value: str | None, field: str) -> str:
    if not value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{field} is required")
    return value


def _required_int(value: str | None, field: str) -> int:
    raw = _required(value, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{field} must be an integer") from exc


def _message_item_slack(message: dict[str, Any]) -> dict[str, Any]:
    ts = str(message.get("ts") or "")
    timestamp = None
    if ts:
        try:
            timestamp = datetime.fromtimestamp(float(ts), tz=UTC).isoformat()
        except ValueError:
            timestamp = None
    return {
        "id": ts,
        "content": message.get("text") or "",
        "author": {"id": message.get("user") or "", "name": message.get("username") or message.get("user") or ""},
        "timestamp": timestamp,
        "replyTo": message.get("thread_ts") if message.get("thread_ts") != ts else None,
        "attachments": [
            {"name": item.get("name") or item.get("title"), "url": item.get("url_private")}
            for item in message.get("files", [])
            if isinstance(item, dict)
        ],
    }


def _first_sent_message_id(result: dict[str, Any]) -> str | None:
    sent_messages = result.get("sentMessages")
    if isinstance(sent_messages, list) and sent_messages and isinstance(sent_messages[0], dict):
        value = sent_messages[0].get("id")
        return str(value) if value is not None else None
    value = result.get("id")
    return str(value) if value is not None else None


def _message_item_discord(message: dict[str, Any]) -> dict[str, Any]:
    author = message.get("author") if isinstance(message.get("author"), dict) else {}
    reference = message.get("message_reference") if isinstance(message.get("message_reference"), dict) else {}
    return {
        "id": message.get("id") or "",
        "content": message.get("content") or "",
        "author": {"id": author.get("id") or "", "name": author.get("username") or ""},
        "timestamp": message.get("timestamp"),
        "replyTo": reference.get("message_id"),
        "attachments": [
            {"name": item.get("filename"), "url": item.get("url")}
            for item in message.get("attachments", [])
            if isinstance(item, dict)
        ],
    }


async def _resolve_bot(
    session: AsyncSession,
    user_id: str,
    bot_id: str,
) -> tuple[AgentBotProvider, dict[str, str]]:
    row = (
        await session.execute(
            select(AgentBotProvider).where(and_(AgentBotProvider.id == bot_id, AgentBotProvider.user_id == user_id))
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Bot not found: {bot_id}")
    if not row.enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Bot is disabled: {bot_id}")
    return row, _decode_credentials(row.credentials)


async def _slack_call(token: str, method: str, data: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://slack.com/api/{method}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
            data={key: value for key, value in data.items() if value is not None},
        )
    if not response.is_success:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Slack {method} failed: {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Slack {method} failed: {payload.get('error')}")
    return payload


async def _discord_request(
    token: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.request(
            method,
            f"https://discord.com/api/v10{path}",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json=json_body,
            params={key: value for key, value in (params or {}).items() if value is not None},
        )
    if not response.is_success:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Discord API failed: {response.status_code} {response.text}")
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


async def _telegram_call(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
    if not response.is_success:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Telegram {method} failed: {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Telegram {method} failed: {data.get('description')}")
    return data


# ---------------------------------------------------------------------------
# Endpoints — one per TS procedure
# ---------------------------------------------------------------------------

@router.post("/send-message")
async def send_message(
    body: BotActionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, body.bot_id)
    channel_id = _required(body.channel_id, "channel_id")
    content = _required(body.content, "content")

    if provider.platform == "slack":
        result = await SlackClient(_required(credentials.get("botToken"), "botToken")).post_message(
            channel_id,
            content,
            thread_ts=body.reply_to,
        )
        return {"channelId": channel_id, "messageId": result.get("ts"), "platform": provider.platform}
    if provider.platform == "discord":
        result = await DiscordClient(_required(credentials.get("botToken"), "botToken")).create_message(
            channel_id,
            content,
        )
        return {"channelId": channel_id, "messageId": result.get("id"), "platform": provider.platform}
    if provider.platform == "telegram":
        reply_to = int(body.reply_to) if body.reply_to and body.reply_to.isdigit() else None
        result = await TelegramClient(_required(credentials.get("botToken"), "botToken")).send_message(
            channel_id,
            content,
            reply_to_message_id=reply_to,
        )
        return {
            "channelId": channel_id,
            "messageId": str(result.get("result", {}).get("message_id") or result.get("message_id") or ""),
            "platform": provider.platform,
        }
    if provider.platform == "line":
        result = await LineClient(_required(credentials.get("channelAccessToken"), "channelAccessToken")).push_text(
            channel_id,
            content,
        )
        return {"channelId": channel_id, "messageId": _first_sent_message_id(result), "platform": provider.platform}
    if provider.platform == "webex":
        result = await WebexClient(_required(credentials.get("botToken"), "botToken")).create_message(
            channel_id,
            content,
            parent_id=body.reply_to,
        )
        return {"channelId": channel_id, "messageId": result.get("id"), "platform": provider.platform}
    if provider.platform == "qq":
        qq_client = QQClient(provider.application_id, _required(credentials.get("appSecret"), "appSecret"))
        result = await qq_client.send_text(
            f"/channels/{channel_id}/messages",
            content,
            msg_id=body.reply_to,
        )
        return {"channelId": channel_id, "messageId": result.get("id"), "platform": provider.platform}
    if provider.platform == "wechat":
        wechat_client = WechatClient(_required(credentials.get("botToken"), "botToken"))
        result = await wechat_client.send_message(channel_id, content)
        return {"channelId": channel_id, "messageId": result.get("msgid"), "platform": provider.platform}
    _unsupported(provider.platform, "sendMessage")


@router.post("/send-direct-message")
async def send_direct_message(
    body: BotActionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, body.bot_id)
    target_id = _required(body.user_id_target, "user_id")
    content = _required(body.content, "content")

    if provider.platform == "discord":
        token = _required(credentials.get("botToken"), "botToken")
        dm = await _discord_request(token, "POST", "/users/@me/channels", json_body={"recipient_id": target_id})
        result = await DiscordClient(token).create_message(str(dm["id"]), content)
        return {"channelId": dm.get("id"), "messageId": result.get("id"), "platform": provider.platform}
    if provider.platform == "telegram":
        telegram_client = TelegramClient(_required(credentials.get("botToken"), "botToken"))
        result = await telegram_client.send_message(target_id, content)
        return {
            "channelId": target_id,
            "messageId": str(result.get("result", {}).get("message_id") or result.get("message_id") or ""),
            "platform": provider.platform,
        }
    if provider.platform == "line":
        result = await LineClient(_required(credentials.get("channelAccessToken"), "channelAccessToken")).push_text(
            target_id,
            content,
        )
        return {"channelId": target_id, "messageId": _first_sent_message_id(result), "platform": provider.platform}
    if provider.platform == "qq":
        qq_client = QQClient(provider.application_id, _required(credentials.get("appSecret"), "appSecret"))
        result = await qq_client.send_text(
            f"/v2/users/{target_id}/messages",
            content,
        )
        return {"channelId": target_id, "messageId": result.get("id"), "platform": provider.platform}
    if provider.platform == "wechat":
        result = await WechatClient(_required(credentials.get("botToken"), "botToken")).send_message(target_id, content)
        return {"channelId": target_id, "messageId": result.get("msgid"), "platform": provider.platform}
    _unsupported(provider.platform, "sendDirectMessage")


@router.get("/read-messages")
async def read_messages(
    botId: str = Query(alias="bot_id"),
    channelId: str = Query(alias="channel_id"),
    limit: Optional[int] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    cursor: Optional[str] = None,
    startTime: Optional[str] = Query(default=None, alias="start_time"),
    endTime: Optional[str] = Query(default=None, alias="end_time"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, botId)
    read_limit = min(limit or DEFAULT_BOT_HISTORY_LIMIT, MAX_BOT_HISTORY_LIMIT)
    if provider.platform == "slack":
        result = await _slack_call(
            _required(credentials.get("botToken"), "botToken"),
            "conversations.history",
            {"channel": channelId, "latest": before, "oldest": after, "cursor": cursor, "limit": read_limit},
        )
        messages = [_message_item_slack(item) for item in result.get("messages", []) if isinstance(item, dict)]
        return {
            "channelId": channelId,
            "messages": messages,
            "platform": provider.platform,
            "totalFetched": len(messages),
            "hasMore": result.get("has_more", False),
            "nextCursor": result.get("response_metadata", {}).get("next_cursor"),
        }
    if provider.platform == "discord":
        payload = await _discord_request(
            _required(credentials.get("botToken"), "botToken"),
            "GET",
            f"/channels/{channelId}/messages",
            params={"before": before, "after": after, "limit": read_limit},
        )
        messages = [_message_item_discord(item) for item in payload if isinstance(item, dict)]
        return {
            "channelId": channelId,
            "messages": messages,
            "platform": provider.platform,
            "totalFetched": len(messages),
        }
    _unsupported(provider.platform, "readMessages")


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
async def react_to_message(
    body: BotActionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, body.bot_id)
    channel_id = _required(body.channel_id, "channel_id")
    message_id = _required(body.message_id, "message_id")
    emoji = _required(body.emoji, "emoji")
    if provider.platform == "slack":
        await _slack_call(
            _required(credentials.get("botToken"), "botToken"),
            "reactions.add",
            {"channel": channel_id, "timestamp": message_id, "name": emoji.replace(":", "")},
        )
        return {"messageId": message_id, "success": True}
    if provider.platform == "discord":
        await _discord_request(
            _required(credentials.get("botToken"), "botToken"),
            "PUT",
            f"/channels/{channel_id}/messages/{message_id}/reactions/{quote(emoji, safe='')}/@me",
        )
        return {"messageId": message_id, "success": True}
    if provider.platform == "telegram":
        await _telegram_call(
            _required(credentials.get("botToken"), "botToken"),
            "setMessageReaction",
            {
                "chat_id": channel_id,
                "message_id": _required_int(message_id, "message_id"),
                "reaction": [{"type": "emoji", "emoji": emoji}],
            },
        )
        return {"messageId": message_id, "success": True}
    _unsupported(provider.platform, "reactToMessage")


@router.get("/get-reactions")
async def get_reactions(
    botId: str = Query(alias="bot_id"),
    channelId: str = Query(alias="channel_id"),
    messageId: str = Query(alias="message_id"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, botId)
    if provider.platform == "slack":
        result = await _slack_call(
            _required(credentials.get("botToken"), "botToken"),
            "reactions.get",
            {"channel": channelId, "timestamp": messageId},
        )
        reactions = result.get("message", {}).get("reactions", [])
        return {
            "messageId": messageId,
            "reactions": [
                {"count": item.get("count"), "emoji": item.get("name"), "users": item.get("users", [])}
                for item in reactions
                if isinstance(item, dict)
            ],
        }
    if provider.platform == "discord":
        message = await _discord_request(
            _required(credentials.get("botToken"), "botToken"),
            "GET",
            f"/channels/{channelId}/messages/{messageId}",
        )
        reactions = []
        for reaction in message.get("reactions", []):
            emoji_obj = reaction.get("emoji", {}) if isinstance(reaction, dict) else {}
            emoji = f"{emoji_obj.get('name')}:{emoji_obj.get('id')}" if emoji_obj.get("id") else emoji_obj.get("name")
            reactions.append({"count": reaction.get("count"), "emoji": emoji, "users": []})
        return {"messageId": messageId, "reactions": reactions}
    _unsupported(provider.platform, "getReactions")


@router.post("/pin-message")
async def pin_message(
    body: BotActionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, body.bot_id)
    channel_id = _required(body.channel_id, "channel_id")
    message_id = _required(body.message_id, "message_id")
    if provider.platform == "slack":
        await _slack_call(
            _required(credentials.get("botToken"), "botToken"),
            "pins.add",
            {"channel": channel_id, "timestamp": message_id},
        )
        return {"messageId": message_id, "success": True}
    if provider.platform == "discord":
        await _discord_request(
            _required(credentials.get("botToken"), "botToken"),
            "PUT",
            f"/channels/{channel_id}/pins/{message_id}",
        )
        return {"messageId": message_id, "success": True}
    if provider.platform == "telegram":
        await _telegram_call(
            _required(credentials.get("botToken"), "botToken"),
            "pinChatMessage",
            {
                "chat_id": channel_id,
                "message_id": _required_int(message_id, "message_id"),
                "disable_notification": True,
            },
        )
        return {"messageId": message_id, "success": True}
    _unsupported(provider.platform, "pinMessage")


@router.post("/unpin-message")
async def unpin_message(
    body: BotActionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, body.bot_id)
    channel_id = _required(body.channel_id, "channel_id")
    message_id = _required(body.message_id, "message_id")
    if provider.platform == "slack":
        await _slack_call(
            _required(credentials.get("botToken"), "botToken"),
            "pins.remove",
            {"channel": channel_id, "timestamp": message_id},
        )
        return {"messageId": message_id, "success": True}
    if provider.platform == "discord":
        await _discord_request(
            _required(credentials.get("botToken"), "botToken"),
            "DELETE",
            f"/channels/{channel_id}/pins/{message_id}",
        )
        return {"messageId": message_id, "success": True}
    if provider.platform == "telegram":
        await _telegram_call(
            _required(credentials.get("botToken"), "botToken"),
            "unpinChatMessage",
            {"chat_id": channel_id, "message_id": _required_int(message_id, "message_id")},
        )
        return {"messageId": message_id, "success": True}
    _unsupported(provider.platform, "unpinMessage")


@router.get("/list-pins")
async def list_pins(
    botId: str = Query(alias="bot_id"),
    channelId: str = Query(alias="channel_id"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    provider, credentials = await _resolve_bot(session, user_id, botId)
    if provider.platform == "slack":
        result = await _slack_call(
            _required(credentials.get("botToken"), "botToken"),
            "pins.list",
            {"channel": channelId},
        )
        return {
            "messages": [
                _message_item_slack(item.get("message", item))
                for item in result.get("items", [])
                if isinstance(item, dict)
            ]
        }
    if provider.platform == "discord":
        payload = await _discord_request(
            _required(credentials.get("botToken"), "botToken"),
            "GET",
            f"/channels/{channelId}/pins",
        )
        return {"messages": [_message_item_discord(item) for item in payload if isinstance(item, dict)]}
    _unsupported(provider.platform, "listPins")


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
