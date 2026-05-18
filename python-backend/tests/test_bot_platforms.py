from __future__ import annotations

import pytest

from app.services.bot.platforms import platform_registry
from app.services.bot.platforms.discord.definition import discord
from app.services.bot.platforms.feishu.definition import feishu, lark
from app.services.bot.platforms.line.definition import line
from app.services.bot.platforms.slack.definition import slack
from app.services.bot.platforms.telegram.definition import telegram


def test_discord_platform_serializes_frontend_schema() -> None:
    data = discord.serialize()

    assert data["id"] == "discord"
    assert data["connectionMode"] == "websocket"
    assert data["documentation"]["portalUrl"] == "https://discord.com/developers/applications"
    assert any(field["key"] == "applicationId" for field in data["schema"])


def test_registry_exposes_only_python_migrated_platforms() -> None:
    assert [platform.id for platform in platform_registry.list()] == [
        "discord",
        "telegram",
        "line",
        "slack",
        "feishu",
        "lark",
    ]


def test_discord_settings_merge_schema_defaults() -> None:
    settings = discord.merge_settings({"charLimit": 1000})

    assert settings["charLimit"] == 1000
    assert settings["concurrency"] == "queue"
    assert settings["historyLimit"] == 50
    assert settings["dmPolicy"] == "open"
    assert settings["groupPolicy"] == "open"


@pytest.mark.asyncio
async def test_discord_validate_credentials_reports_missing_fields() -> None:
    result = await discord.validate_credentials({})

    assert result.valid is False
    assert result.to_dict() == {
        "valid": False,
        "errors": [
            {"field": "botToken", "message": "Bot Token is required"},
            {"field": "publicKey", "message": "Public Key is required"},
        ],
    }


def test_telegram_platform_serializes_frontend_schema() -> None:
    data = telegram.serialize()

    assert data["id"] == "telegram"
    assert data["connectionMode"] == "webhook"
    assert data["documentation"]["portalUrl"] == "https://t.me/BotFather"
    assert not any(field["key"] == "applicationId" for field in data["schema"])


def test_telegram_settings_merge_schema_defaults() -> None:
    settings = telegram.merge_settings({"charLimit": 1000})

    assert settings["charLimit"] == 1000
    assert settings["concurrency"] == "queue"
    assert settings["dmPolicy"] == "open"
    assert settings["groupPolicy"] == "open"


@pytest.mark.asyncio
async def test_telegram_validate_credentials_reports_missing_bot_token() -> None:
    result = await telegram.validate_credentials({})

    assert result.valid is False
    assert result.to_dict() == {
        "valid": False,
        "errors": [{"field": "botToken", "message": "Bot Token is required"}],
    }


def test_line_platform_serializes_frontend_schema() -> None:
    data = line.serialize()

    assert data["id"] == "line"
    assert data["connectionMode"] == "webhook"
    assert data["showWebhookUrl"] is True
    assert data["supportsMarkdown"] is False
    assert data["supportsMessageEdit"] is False
    assert any(field["key"] == "applicationId" for field in data["schema"])


def test_line_settings_merge_schema_defaults() -> None:
    settings = line.merge_settings({"charLimit": 1000})

    assert settings["charLimit"] == 1000
    assert settings["concurrency"] == "queue"
    assert settings["displayToolCalls"] is False


@pytest.mark.asyncio
async def test_line_validate_credentials_reports_missing_fields() -> None:
    result = await line.validate_credentials({})

    assert result.valid is False
    assert result.to_dict() == {
        "valid": False,
        "errors": [
            {"field": "channelAccessToken", "message": "Channel Access Token is required"},
            {"field": "channelSecret", "message": "Channel Secret is required"},
            {"field": "applicationId", "message": "Destination User ID is required"},
        ],
    }


def test_slack_platform_serializes_frontend_schema() -> None:
    data = slack.serialize()

    assert data["id"] == "slack"
    assert data["connectionMode"] == "websocket"
    assert data["documentation"]["portalUrl"] == "https://api.slack.com/apps"
    assert any(field["key"] == "applicationId" for field in data["schema"])


def test_slack_settings_merge_schema_defaults() -> None:
    settings = slack.merge_settings({"charLimit": 1000})

    assert settings["charLimit"] == 1000
    assert settings["connectionMode"] == "websocket"
    assert settings["historyLimit"] == 50
    assert settings["dmPolicy"] == "open"


@pytest.mark.asyncio
async def test_slack_validate_credentials_reports_missing_fields() -> None:
    result = await slack.validate_credentials({}, {"connectionMode": "websocket"})

    assert result.valid is False
    assert result.to_dict() == {
        "valid": False,
        "errors": [
            {"field": "botToken", "message": "Bot Token is required"},
            {"field": "signingSecret", "message": "Signing Secret is required"},
            {
                "field": "appToken",
                "message": "App-Level Token is required for WebSocket (Socket Mode)",
            },
        ],
    }


def test_feishu_platform_serializes_frontend_schema() -> None:
    data = feishu.serialize()

    assert data["id"] == "feishu"
    assert data["connectionMode"] == "websocket"
    assert data["documentation"]["portalUrl"] == "https://open.feishu.cn/app"
    assert data["supportsMarkdown"] is False
    assert any(field["key"] == "applicationId" for field in data["schema"])


def test_lark_platform_serializes_frontend_schema() -> None:
    data = lark.serialize()

    assert data["id"] == "lark"
    assert data["connectionMode"] == "websocket"
    assert data["documentation"]["portalUrl"] == "https://open.larksuite.com/app"
    assert data["supportsMarkdown"] is False
    assert any(field["key"] == "applicationId" for field in data["schema"])


def test_feishu_settings_merge_schema_defaults() -> None:
    settings = feishu.merge_settings({"charLimit": 1000})

    assert settings["charLimit"] == 1000
    assert settings["connectionMode"] == "websocket"
    assert settings["historyLimit"] == 50
    assert settings["dmPolicy"] == "open"
    assert settings["groupPolicy"] == "open"


@pytest.mark.asyncio
async def test_feishu_validate_credentials_reports_missing_fields() -> None:
    result = await feishu.validate_credentials({})

    assert result.valid is False
    assert result.to_dict() == {
        "valid": False,
        "errors": [
            {"field": "applicationId", "message": "Application ID is required"},
            {"field": "appSecret", "message": "App Secret is required"},
        ],
    }


@pytest.mark.asyncio
async def test_lark_validate_credentials_reports_missing_fields() -> None:
    result = await lark.validate_credentials({})

    assert result.valid is False
    assert result.to_dict() == {
        "valid": False,
        "errors": [
            {"field": "applicationId", "message": "Application ID is required"},
            {"field": "appSecret", "message": "App Secret is required"},
        ],
    }
