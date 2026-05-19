from __future__ import annotations

from app.services.bot.inbound import (
    normalize_discord_message,
    normalize_feishu_event,
    normalize_inbound_webhook,
    normalize_line_webhook,
    normalize_qq_webhook,
    normalize_slack_event,
    normalize_teams_activity,
    normalize_telegram_update,
    normalize_webex_webhook,
    normalize_wechat_message,
)


def test_normalize_telegram_text_message() -> None:
    result = normalize_telegram_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 1001, "language_code": "pt-br"},
                "chat": {"id": -100123, "type": "supergroup"},
                "text": "hello from telegram",
            },
        },
        "123456789",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.to_dict() == {
        "platform": "telegram",
        "application_id": "123456789",
        "message_id": "telegram:-100123:42",
        "thread_id": "telegram:-100123",
        "channel_id": "-100123",
        "author_id": "1001",
        "text": "hello from telegram",
        "is_dm": False,
        "raw": {
            "message_id": 42,
            "from": {"id": 1001, "language_code": "pt-br"},
            "chat": {"id": -100123, "type": "supergroup"},
            "text": "hello from telegram",
        },
        "author_locale": "pt-br",
    }


def test_normalize_telegram_caption_dm_message() -> None:
    result = normalize_telegram_update(
        {
            "message": {
                "message_id": 7,
                "from": {"id": 1001},
                "chat": {"id": 1001, "type": "private"},
                "caption": "image caption",
            },
        },
        "123456789",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.is_dm is True
    assert result.message.text == "image caption"


def test_normalize_telegram_photo_without_caption_as_attachment() -> None:
    result = normalize_telegram_update(
        {
            "message": {
                "message_id": 8,
                "from": {"id": 1001},
                "chat": {"id": 1001, "type": "private"},
                "photo": [
                    {"file_id": "small", "file_size": 10},
                    {"file_id": "large", "file_size": 100},
                ],
            },
        },
        "123456789",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.text == ""
    assert result.message.attachments is not None
    assert result.message.attachments[0].to_dict() == {
        "type": "image",
        "id": "large",
        "size": 100,
        "raw": {"file_id": "large", "file_size": 100},
    }


def test_normalize_telegram_ignores_unsupported_update() -> None:
    result = normalize_telegram_update({"callback_query": {"id": "cb-1"}}, "123456789")

    assert result.status == "ignored"
    assert result.reason == "unsupported_update"
    assert result.message is None


def test_normalize_inbound_webhook_reports_unknown_platform() -> None:
    result = normalize_inbound_webhook("unknown", "app-1", {"event": {}})

    assert result.status == "ignored"
    assert result.reason == "unsupported_platform:unknown"


def test_normalize_line_user_text_message() -> None:
    result = normalize_line_webhook(
        {
            "destination": "Ubot",
            "events": [
                {
                    "type": "message",
                    "replyToken": "reply-token",
                    "source": {"type": "user", "userId": "Uuser"},
                    "message": {"type": "text", "id": "line-msg-1", "text": "hello line"},
                },
            ],
        },
        "Ubot",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.to_dict() == {
        "platform": "line",
        "application_id": "Ubot",
        "message_id": "line:line-msg-1",
        "thread_id": "line:user:Uuser",
        "channel_id": "Uuser",
        "author_id": "Uuser",
        "text": "hello line",
        "is_dm": True,
        "raw": {
            "type": "message",
            "replyToken": "reply-token",
            "source": {"type": "user", "userId": "Uuser"},
            "message": {"type": "text", "id": "line-msg-1", "text": "hello line"},
        },
        "author_locale": None,
    }


def test_normalize_line_group_text_message() -> None:
    result = normalize_line_webhook(
        {
            "events": [
                {
                    "type": "message",
                    "source": {"type": "group", "groupId": "Ggroup", "userId": "Uuser"},
                    "message": {"type": "text", "id": "line-msg-2", "text": "hello group"},
                },
            ],
        },
        "Ubot",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.thread_id == "line:group:Ggroup"
    assert result.message.channel_id == "Ggroup"
    assert result.message.author_id == "Uuser"
    assert result.message.is_dm is False


def test_normalize_line_verification_ping_is_ignored() -> None:
    result = normalize_line_webhook({"destination": "Ubot", "events": []}, "Ubot")

    assert result.status == "ignored"
    assert result.reason == "verification_ping"


def test_normalize_line_unsupported_event_is_ignored() -> None:
    result = normalize_line_webhook({"events": [{"type": "follow"}]}, "Ubot")

    assert result.status == "ignored"
    assert result.reason == "no_supported_message"


def test_normalize_line_image_message_as_attachment() -> None:
    result = normalize_line_webhook(
        {
            "events": [
                {
                    "type": "message",
                    "source": {"type": "user", "userId": "Uuser"},
                    "message": {"type": "image", "id": "line-img-1"},
                },
            ],
        },
        "Ubot",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.text == ""
    assert result.message.attachments is not None
    assert result.message.attachments[0].to_dict() == {
        "type": "image",
        "id": "line-img-1",
        "mime_type": "image/jpeg",
        "raw": {"type": "image", "id": "line-img-1"},
    }


def test_normalize_slack_app_mention() -> None:
    result = normalize_slack_event(
        {
            "type": "event_callback",
            "event": {
                "type": "app_mention",
                "channel": "C123",
                "user": "U123",
                "ts": "1710000000.000100",
                "text": "<@BOT> hello slack",
            },
        },
        "A123",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.to_dict() == {
        "platform": "slack",
        "application_id": "A123",
        "message_id": "1710000000.000100",
        "thread_id": "slack:C123",
        "channel_id": "C123",
        "author_id": "U123",
        "text": "<@BOT> hello slack",
        "is_dm": False,
        "raw": {
            "type": "app_mention",
            "channel": "C123",
            "user": "U123",
            "ts": "1710000000.000100",
            "text": "<@BOT> hello slack",
        },
        "author_locale": None,
    }


def test_normalize_slack_thread_message() -> None:
    result = normalize_slack_event(
        {
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": "D123",
                "user": "U123",
                "ts": "1710000001.000100",
                "thread_ts": "1710000000.000100",
                "text": "thread reply",
            },
        },
        "A123",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.thread_id == "slack:D123:1710000000.000100"
    assert result.message.is_dm is True


def test_normalize_slack_ignores_bot_messages() -> None:
    result = normalize_slack_event(
        {
            "type": "event_callback",
            "event": {
                "type": "message",
                "bot_id": "B123",
                "channel": "C123",
                "ts": "1710000000.000100",
                "text": "bot text",
            },
        },
        "A123",
    )

    assert result.status == "ignored"
    assert result.reason == "bot_message"


def test_normalize_slack_url_verification_is_ignored() -> None:
    result = normalize_slack_event({"type": "url_verification", "challenge": "challenge"}, "A123")

    assert result.status == "ignored"
    assert result.reason == "url_verification"


def test_normalize_slack_file_without_text_as_attachment() -> None:
    result = normalize_slack_event(
        {
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": "C123",
                "user": "U123",
                "ts": "1710000000.000100",
                "files": [
                    {
                        "id": "F123",
                        "name": "screenshot.png",
                        "mimetype": "image/png",
                        "size": 123,
                        "url_private": "https://files.slack.com/files-pri/T/F/screenshot.png",
                    }
                ],
            },
        },
        "A123",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.text == ""
    assert result.message.attachments is not None
    assert result.message.attachments[0].type == "image"
    assert result.message.attachments[0].url == "https://files.slack.com/files-pri/T/F/screenshot.png"


def test_normalize_discord_guild_message_sanitizes_bot_mention() -> None:
    result = normalize_discord_message(
        {
            "id": "discord-msg-1",
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "author": {"id": "user-1"},
            "content": "<@123456789> hello discord",
        },
        "123456789",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.to_dict() == {
        "platform": "discord",
        "application_id": "123456789",
        "message_id": "discord-msg-1",
        "thread_id": "discord:guild-1:channel-1",
        "channel_id": "channel-1",
        "author_id": "user-1",
        "text": "hello discord",
        "is_dm": False,
        "raw": {
            "id": "discord-msg-1",
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "author": {"id": "user-1"},
            "content": "<@123456789> hello discord",
        },
        "author_locale": None,
    }


def test_normalize_discord_dm_attachment_without_text() -> None:
    result = normalize_discord_message(
        {
            "id": "discord-msg-2",
            "channel_id": "dm-channel-1",
            "author": {"id": "user-1"},
            "content": "",
            "attachments": [
                {
                    "content_type": "image/png",
                    "filename": "screenshot.png",
                    "id": "att-1",
                    "size": 123,
                    "url": "https://cdn.discordapp.com/attachments/file.png",
                }
            ],
        },
        "123456789",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.thread_id == "discord:@me:dm-channel-1"
    assert result.message.is_dm is True
    assert result.message.attachments is not None
    assert result.message.attachments[0].to_dict() == {
        "type": "image",
        "id": "att-1",
        "name": "screenshot.png",
        "mime_type": "image/png",
        "size": 123,
        "url": "https://cdn.discordapp.com/attachments/file.png",
        "raw": {
            "content_type": "image/png",
            "filename": "screenshot.png",
            "id": "att-1",
            "size": 123,
            "url": "https://cdn.discordapp.com/attachments/file.png",
        },
    }


def test_normalize_discord_ignores_bot_message() -> None:
    result = normalize_discord_message(
        {
            "id": "discord-msg-3",
            "channel_id": "channel-1",
            "author": {"id": "bot-1", "bot": True},
            "content": "bot text",
        },
        "123456789",
    )

    assert result.status == "ignored"
    assert result.reason == "bot_message"


def test_normalize_feishu_p2p_text_message() -> None:
    result = normalize_feishu_event(
        "feishu",
        {
            "header": {"event_type": "im.message.receive_v1", "token": "verify"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_sender"}},
                "message": {
                    "message_id": "om_msg",
                    "chat_id": "oc_chat",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "content": '{"text":"hello feishu"}',
                },
            },
        },
        "cli_app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.to_dict() == {
        "platform": "feishu",
        "application_id": "cli_app",
        "message_id": "om_msg",
        "thread_id": "feishu:p2p:oc_chat",
        "channel_id": "oc_chat",
        "author_id": "ou_sender",
        "text": "hello feishu",
        "is_dm": True,
        "raw": {
            "message_id": "om_msg",
            "chat_id": "oc_chat",
            "chat_type": "p2p",
            "message_type": "text",
            "content": '{"text":"hello feishu"}',
        },
        "author_locale": None,
    }


def test_normalize_lark_group_text_message() -> None:
    result = normalize_feishu_event(
        "lark",
        {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"user_id": "user_sender"}},
                "message": {
                    "message_id": "om_msg",
                    "chat_id": "oc_group",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": '{"text":"hello lark group"}',
                },
            },
        },
        "cli_app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.thread_id == "lark:group:oc_group"
    assert result.message.channel_id == "oc_group"
    assert result.message.author_id == "user_sender"
    assert result.message.is_dm is False


def test_normalize_feishu_url_verification_is_ignored() -> None:
    result = normalize_feishu_event("feishu", {"type": "url_verification", "challenge": "c"}, "cli_app")

    assert result.status == "ignored"
    assert result.reason == "url_verification"


def test_normalize_feishu_unsupported_event_is_ignored() -> None:
    result = normalize_feishu_event("feishu", {"header": {"event_type": "app.opened"}}, "cli_app")

    assert result.status == "ignored"
    assert result.reason == "unsupported_event"


def test_normalize_feishu_image_without_text_as_attachment() -> None:
    result = normalize_feishu_event(
        "feishu",
        {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_sender"}},
                "message": {
                    "message_id": "om_img",
                    "chat_id": "oc_chat",
                    "chat_type": "p2p",
                    "message_type": "image",
                    "content": '{"image_key":"img-key"}',
                },
            },
        },
        "cli_app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.text == ""
    assert result.message.attachments is not None
    assert result.message.attachments[0].to_dict() == {
        "type": "image",
        "id": "img-key",
        "raw": {"image_key": "img-key"},
    }


def test_normalize_qq_group_message() -> None:
    result = normalize_qq_webhook(
        {
            "op": 0,
            "t": "GROUP_AT_MESSAGE_CREATE",
            "d": {
                "id": "qq-msg-1",
                "group_openid": "group_openid",
                "author": {"id": "author_openid"},
                "content": "<@bot> hello qq",
            },
        },
        "qq-app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.thread_id == "qq:group:group_openid"
    assert result.message.channel_id == "group_openid"
    assert result.message.author_id == "author_openid"
    assert result.message.is_dm is False


def test_normalize_qq_c2c_message() -> None:
    result = normalize_qq_webhook(
        {
            "op": 0,
            "t": "C2C_MESSAGE_CREATE",
            "d": {
                "id": "qq-msg-2",
                "author": {"id": "user_openid"},
                "content": "hello c2c",
            },
        },
        "qq-app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.thread_id == "qq:c2c:user_openid"
    assert result.message.is_dm is True


def test_normalize_qq_verification_is_ignored() -> None:
    result = normalize_qq_webhook({"op": 13, "d": {"plain_token": "token"}}, "qq-app")

    assert result.status == "ignored"
    assert result.reason == "verification"


def test_normalize_qq_attachment_without_text() -> None:
    result = normalize_qq_webhook(
        {
            "op": 0,
            "t": "GROUP_AT_MESSAGE_CREATE",
            "d": {
                "id": "qq-msg-3",
                "group_openid": "group_openid",
                "author": {"id": "author_openid"},
                "attachments": [
                    {
                        "content_type": "image/png",
                        "filename": "screenshot.png",
                        "id": "att-1",
                        "size": 100,
                        "url": "https://multimedia.nt.qq.com.cn/download?fileid=abc",
                    }
                ],
            },
        },
        "qq-app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.text == ""
    assert result.message.attachments is not None
    assert result.message.attachments[0].type == "image"
    assert result.message.attachments[0].url == "https://multimedia.nt.qq.com.cn/download?fileid=abc"


def test_normalize_wechat_text_message() -> None:
    result = normalize_wechat_message(
        {
            "context_token": "ctx",
            "from_user_id": "user@im.wechat",
            "item_list": [{"type": 1, "text_item": {"text": "hello wechat"}}],
            "message_id": 42,
            "message_state": 2,
            "message_type": 1,
        },
        "wechat-app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.thread_id == "wechat:single:user@im.wechat"
    assert result.message.channel_id == "user@im.wechat"
    assert result.message.text == "hello wechat"
    assert result.message.is_dm is True


def test_normalize_wechat_ignores_bot_message() -> None:
    result = normalize_wechat_message(
        {
            "from_user_id": "bot@im.wechat",
            "item_list": [{"type": 1, "text_item": {"text": "bot text"}}],
            "message_id": 43,
            "message_state": 2,
            "message_type": 2,
        },
        "wechat-app",
    )

    assert result.status == "ignored"
    assert result.reason == "bot_message"


def test_normalize_wechat_ignores_unfinished_message() -> None:
    result = normalize_wechat_message(
        {
            "from_user_id": "user@im.wechat",
            "item_list": [{"type": 1, "text_item": {"text": "partial"}}],
            "message_id": 44,
            "message_state": 1,
            "message_type": 1,
        },
        "wechat-app",
    )

    assert result.status == "ignored"
    assert result.reason == "unfinished_message"


def test_normalize_wechat_image_without_text_as_attachment() -> None:
    result = normalize_wechat_message(
        {
            "context_token": "ctx",
            "from_user_id": "user@im.wechat",
            "item_list": [
                {
                    "type": 1,
                    "image_item": {"media": {"encrypt_query_param": "enc"}},
                }
            ],
            "message_id": 45,
            "message_state": 2,
            "message_type": 1,
        },
        "wechat-app",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.text == ""
    assert result.message.attachments is not None
    assert result.message.attachments[0].type == "image"


def test_normalize_teams_message_activity() -> None:
    result = normalize_teams_activity(
        {
            "type": "message",
            "id": "activity-1",
            "serviceUrl": "https://smba.trafficmanager.net/teams/",
            "locale": "en-US",
            "from": {"id": "29:user"},
            "recipient": {"id": "28:bot"},
            "conversation": {"id": "19:conversation", "conversationType": "personal"},
            "text": "hello teams",
        },
        "teams-app-id",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.to_dict() == {
        "platform": "teams",
        "application_id": "teams-app-id",
        "message_id": "activity-1",
        "thread_id": "teams:19:conversation",
        "channel_id": "19:conversation",
        "author_id": "29:user",
        "text": "hello teams",
        "is_dm": True,
        "raw": {
            "type": "message",
            "id": "activity-1",
            "serviceUrl": "https://smba.trafficmanager.net/teams/",
            "locale": "en-US",
            "from": {"id": "29:user"},
            "recipient": {"id": "28:bot"},
            "conversation": {"id": "19:conversation", "conversationType": "personal"},
            "text": "hello teams",
        },
        "author_locale": "en-US",
    }


def test_normalize_teams_ignores_non_message_activity() -> None:
    result = normalize_teams_activity({"type": "conversationUpdate"}, "teams-app-id")

    assert result.status == "ignored"
    assert result.reason == "unsupported_activity"


def test_normalize_webex_message_webhook() -> None:
    result = normalize_webex_webhook(
        {
            "id": "webhook-event-1",
            "resource": "messages",
            "event": "created",
            "data": {
                "id": "webex-msg-1",
                "roomId": "room-1",
                "roomType": "group",
                "personId": "person-1",
                "markdown": "**hello** webex",
            },
        },
        "bot-person-1",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.to_dict() == {
        "platform": "webex",
        "application_id": "bot-person-1",
        "message_id": "webex-msg-1",
        "thread_id": "webex:room:room-1",
        "channel_id": "room-1",
        "author_id": "person-1",
        "text": "**hello** webex",
        "is_dm": False,
        "raw": {
            "id": "webhook-event-1",
            "resource": "messages",
            "event": "created",
            "data": {
                "id": "webex-msg-1",
                "roomId": "room-1",
                "roomType": "group",
                "personId": "person-1",
                "markdown": "**hello** webex",
            },
        },
        "author_locale": None,
    }


def test_normalize_webex_direct_file_message() -> None:
    result = normalize_webex_webhook(
        {
            "resource": "messages",
            "event": "created",
            "data": {
                "id": "webex-msg-2",
                "roomId": "room-2",
                "roomType": "direct",
                "personId": "person-1",
                "files": ["https://webexapis.com/v1/contents/file-1"],
            },
        },
        "bot-person-1",
    )

    assert result.status == "accepted"
    assert result.message is not None
    assert result.message.text == ""
    assert result.message.is_dm is True
    assert result.message.attachments is not None
    assert result.message.attachments[0].to_dict() == {
        "type": "file",
        "url": "https://webexapis.com/v1/contents/file-1",
    }


def test_normalize_webex_ignores_bot_message() -> None:
    result = normalize_webex_webhook(
        {
            "resource": "messages",
            "event": "created",
            "data": {
                "id": "webex-msg-3",
                "roomId": "room-1",
                "roomType": "group",
                "personId": "bot-person-1",
                "text": "bot text",
            },
        },
        "bot-person-1",
    )

    assert result.status == "ignored"
    assert result.reason == "bot_message"
