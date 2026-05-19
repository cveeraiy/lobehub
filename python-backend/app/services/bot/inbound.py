from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

InboundStatus = Literal["accepted", "ignored"]


@dataclass(frozen=True)
class NormalizedBotMessage:
    platform: str
    application_id: str
    message_id: str
    thread_id: str
    channel_id: str
    author_id: str
    text: str
    is_dm: bool
    raw: dict[str, Any]
    author_locale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InboundWebhookResult:
    status: InboundStatus
    message: NormalizedBotMessage | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"status": self.status}
        if self.message:
            data["message"] = self.message.to_dict()
        if self.reason:
            data["reason"] = self.reason
        return data


def normalize_telegram_update(payload: dict[str, Any], application_id: str) -> InboundWebhookResult:
    message = payload.get("message")
    if not isinstance(message, dict):
        return InboundWebhookResult(status="ignored", reason="unsupported_update")

    text = message.get("text") or message.get("caption")
    if not isinstance(text, str) or not text.strip():
        return InboundWebhookResult(status="ignored", reason="empty_message")

    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return InboundWebhookResult(status="ignored", reason="missing_sender_or_chat")

    chat_id = chat.get("id")
    message_id = message.get("message_id")
    author_id = sender.get("id")
    if chat_id is None or message_id is None or author_id is None:
        return InboundWebhookResult(status="ignored", reason="missing_message_identifiers")

    chat_type = chat.get("type")
    author_locale = sender.get("language_code")
    return InboundWebhookResult(
        status="accepted",
        message=NormalizedBotMessage(
            platform="telegram",
            application_id=application_id,
            message_id=f"telegram:{chat_id}:{message_id}",
            thread_id=f"telegram:{chat_id}",
            channel_id=str(chat_id),
            author_id=str(author_id),
            text=text,
            is_dm=chat_type == "private",
            author_locale=author_locale if isinstance(author_locale, str) and author_locale else None,
            raw=message,
        ),
    )


def _line_source_id(source: dict[str, Any]) -> str | None:
    source_type = source.get("type")
    if source_type == "group":
        value = source.get("groupId")
    elif source_type == "room":
        value = source.get("roomId")
    else:
        value = source.get("userId")
    return str(value) if value is not None else None


def normalize_line_webhook(payload: dict[str, Any], application_id: str) -> InboundWebhookResult:
    events = payload.get("events")
    if not isinstance(events, list):
        return InboundWebhookResult(status="ignored", reason="missing_events")
    if len(events) == 0:
        return InboundWebhookResult(status="ignored", reason="verification_ping")

    for event in events:
        if not isinstance(event, dict) or event.get("type") != "message":
            continue

        message = event.get("message")
        source = event.get("source")
        if not isinstance(message, dict) or not isinstance(source, dict):
            continue

        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        message_id = message.get("id")
        author_id = source.get("userId")
        source_id = _line_source_id(source)
        source_type = source.get("type")
        if message_id is None or author_id is None or source_id is None:
            continue

        return InboundWebhookResult(
            status="accepted",
            message=NormalizedBotMessage(
                platform="line",
                application_id=application_id,
                message_id=f"line:{message_id}",
                thread_id=f"line:{source_type}:{source_id}",
                channel_id=source_id,
                author_id=str(author_id),
                text=text,
                is_dm=source_type == "user",
                raw=event,
            ),
        )

    return InboundWebhookResult(status="ignored", reason="no_supported_message")


def normalize_slack_event(payload: dict[str, Any], application_id: str) -> InboundWebhookResult:
    if payload.get("type") == "url_verification":
        return InboundWebhookResult(status="ignored", reason="url_verification")
    if payload.get("type") != "event_callback":
        return InboundWebhookResult(status="ignored", reason="unsupported_event")

    event = payload.get("event")
    if not isinstance(event, dict):
        return InboundWebhookResult(status="ignored", reason="missing_event")
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return InboundWebhookResult(status="ignored", reason="bot_message")

    event_type = event.get("type")
    if event_type not in {"app_mention", "message"}:
        return InboundWebhookResult(status="ignored", reason="unsupported_event_type")

    text = event.get("text")
    if not isinstance(text, str) or not text.strip():
        return InboundWebhookResult(status="ignored", reason="empty_message")

    channel = event.get("channel")
    ts = event.get("ts")
    user = event.get("user")
    if channel is None or ts is None or user is None:
        return InboundWebhookResult(status="ignored", reason="missing_message_identifiers")

    thread_ts = event.get("thread_ts")
    thread_id = f"slack:{channel}:{thread_ts}" if thread_ts else f"slack:{channel}"
    return InboundWebhookResult(
        status="accepted",
        message=NormalizedBotMessage(
            platform="slack",
            application_id=application_id,
            message_id=str(ts),
            thread_id=thread_id,
            channel_id=str(channel),
            author_id=str(user),
            text=text,
            is_dm=str(channel).startswith("D"),
            raw=event,
        ),
    )


def normalize_feishu_event(platform: str, payload: dict[str, Any], application_id: str) -> InboundWebhookResult:
    if payload.get("type") == "url_verification":
        return InboundWebhookResult(status="ignored", reason="url_verification")

    header = payload.get("header")
    if not isinstance(header, dict) or header.get("event_type") != "im.message.receive_v1":
        return InboundWebhookResult(status="ignored", reason="unsupported_event")

    event = payload.get("event")
    if not isinstance(event, dict):
        return InboundWebhookResult(status="ignored", reason="missing_event")

    message = event.get("message")
    sender = event.get("sender")
    if not isinstance(message, dict) or not isinstance(sender, dict):
        return InboundWebhookResult(status="ignored", reason="missing_sender_or_message")

    content_raw = message.get("content")
    if not isinstance(content_raw, str):
        return InboundWebhookResult(status="ignored", reason="missing_content")

    try:
        content = json.loads(content_raw)
    except ValueError:
        return InboundWebhookResult(status="ignored", reason="invalid_content")

    text = content.get("text")
    if not isinstance(text, str) or not text.strip():
        return InboundWebhookResult(status="ignored", reason="empty_message")

    sender_id = sender.get("sender_id")
    if not isinstance(sender_id, dict):
        return InboundWebhookResult(status="ignored", reason="missing_sender_id")

    author_id = sender_id.get("open_id") or sender_id.get("user_id") or sender_id.get("union_id")
    message_id = message.get("message_id")
    chat_id = message.get("chat_id")
    if author_id is None or message_id is None or chat_id is None:
        return InboundWebhookResult(status="ignored", reason="missing_message_identifiers")

    chat_type = message.get("chat_type")
    encoded_chat_type = chat_type if chat_type in {"p2p", "group"} else "unknown"
    return InboundWebhookResult(
        status="accepted",
        message=NormalizedBotMessage(
            platform=platform,
            application_id=application_id,
            message_id=str(message_id),
            thread_id=f"{platform}:{encoded_chat_type}:{chat_id}",
            channel_id=str(chat_id),
            author_id=str(author_id),
            text=text,
            is_dm=chat_type == "p2p",
            raw=message,
        ),
    )


def _qq_thread_id(event_type: str, data: dict[str, Any]) -> tuple[str, str, bool] | None:
    if event_type == "GROUP_AT_MESSAGE_CREATE" and data.get("group_openid"):
        channel_id = str(data["group_openid"])
        return f"qq:group:{channel_id}", channel_id, False
    if event_type == "C2C_MESSAGE_CREATE":
        author = data.get("author")
        if isinstance(author, dict) and author.get("id"):
            channel_id = str(author["id"])
            return f"qq:c2c:{channel_id}", channel_id, True
    if event_type == "AT_MESSAGE_CREATE" and data.get("channel_id"):
        channel_id = str(data["channel_id"])
        guild_id = data.get("guild_id")
        thread_id = f"qq:guild:{channel_id}:{guild_id}" if guild_id else f"qq:guild:{channel_id}"
        return thread_id, channel_id, False
    if event_type == "DIRECT_MESSAGE_CREATE" and data.get("guild_id"):
        channel_id = str(data["guild_id"])
        return f"qq:dms:{channel_id}", channel_id, True
    return None


def normalize_qq_webhook(payload: dict[str, Any], application_id: str) -> InboundWebhookResult:
    if payload.get("op") == 13:
        return InboundWebhookResult(status="ignored", reason="verification")
    if payload.get("op") != 0:
        return InboundWebhookResult(status="ignored", reason="unsupported_op")

    event_type = payload.get("t")
    data = payload.get("d")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        return InboundWebhookResult(status="ignored", reason="missing_event")

    text = data.get("content")
    has_attachments = isinstance(data.get("attachments"), list) and len(data["attachments"]) > 0
    if (not isinstance(text, str) or not text.strip()) and not has_attachments:
        return InboundWebhookResult(status="ignored", reason="empty_message")

    thread = _qq_thread_id(event_type, data)
    if thread is None:
        return InboundWebhookResult(status="ignored", reason="unsupported_event_type")
    thread_id, channel_id, is_dm = thread

    author = data.get("author")
    author_id = author.get("id") if isinstance(author, dict) else data.get("group_openid") or channel_id
    message_id = data.get("id")
    if author_id is None or message_id is None:
        return InboundWebhookResult(status="ignored", reason="missing_message_identifiers")

    return InboundWebhookResult(
        status="accepted",
        message=NormalizedBotMessage(
            platform="qq",
            application_id=application_id,
            message_id=str(message_id),
            thread_id=thread_id,
            channel_id=channel_id,
            author_id=str(author_id),
            text=text if isinstance(text, str) else "",
            is_dm=is_dm,
            raw=data,
        ),
    )


def _wechat_text(payload: dict[str, Any]) -> str:
    items = payload.get("item_list")
    if not isinstance(items, list):
        return ""
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text_item = item.get("text_item")
        if isinstance(text_item, dict) and isinstance(text_item.get("text"), str):
            parts.append(text_item["text"])
    return "\n".join(part for part in parts if part.strip())


def normalize_wechat_message(payload: dict[str, Any], application_id: str) -> InboundWebhookResult:
    if payload.get("message_type") == 2:
        return InboundWebhookResult(status="ignored", reason="bot_message")
    if payload.get("message_state") not in {None, 2}:
        return InboundWebhookResult(status="ignored", reason="unfinished_message")

    text = _wechat_text(payload)
    if not text.strip():
        return InboundWebhookResult(status="ignored", reason="empty_message")

    author_id = payload.get("from_user_id")
    message_id = payload.get("message_id")
    if author_id is None or message_id is None:
        return InboundWebhookResult(status="ignored", reason="missing_message_identifiers")

    channel_id = str(author_id)
    return InboundWebhookResult(
        status="accepted",
        message=NormalizedBotMessage(
            platform="wechat",
            application_id=application_id,
            message_id=str(message_id),
            thread_id=f"wechat:single:{channel_id}",
            channel_id=channel_id,
            author_id=channel_id,
            text=text,
            is_dm=True,
            raw=payload,
        ),
    )


def normalize_teams_activity(payload: dict[str, Any], application_id: str) -> InboundWebhookResult:
    if payload.get("type") != "message":
        return InboundWebhookResult(status="ignored", reason="unsupported_activity")

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return InboundWebhookResult(status="ignored", reason="empty_message")

    sender = payload.get("from")
    conversation = payload.get("conversation")
    if not isinstance(sender, dict) or not isinstance(conversation, dict):
        return InboundWebhookResult(status="ignored", reason="missing_sender_or_conversation")

    author_id = sender.get("id")
    conversation_id = conversation.get("id")
    activity_id = payload.get("id")
    if author_id is None or conversation_id is None or activity_id is None:
        return InboundWebhookResult(status="ignored", reason="missing_activity_identifiers")

    conversation_type = conversation.get("conversationType")
    return InboundWebhookResult(
        status="accepted",
        message=NormalizedBotMessage(
            platform="teams",
            application_id=application_id,
            message_id=str(activity_id),
            thread_id=f"teams:{conversation_id}",
            channel_id=str(conversation_id),
            author_id=str(author_id),
            text=text,
            is_dm=conversation_type == "personal",
            raw=payload,
            author_locale=payload.get("locale") if isinstance(payload.get("locale"), str) else None,
        ),
    )


def normalize_inbound_webhook(
    platform: str,
    application_id: str,
    payload: dict[str, Any],
) -> InboundWebhookResult:
    if platform == "telegram":
        return normalize_telegram_update(payload, application_id)
    if platform == "line":
        return normalize_line_webhook(payload, application_id)
    if platform == "slack":
        return normalize_slack_event(payload, application_id)
    if platform in {"feishu", "lark"}:
        return normalize_feishu_event(platform, payload, application_id)
    if platform == "qq":
        return normalize_qq_webhook(payload, application_id)
    if platform == "wechat":
        return normalize_wechat_message(payload, application_id)
    if platform == "teams":
        return normalize_teams_activity(payload, application_id)
    return InboundWebhookResult(status="ignored", reason=f"unsupported_platform:{platform}")
