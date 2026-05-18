from __future__ import annotations

import pytest

from app.services.bot.platforms import platform_registry
from app.services.bot.platforms.discord.definition import discord


def test_discord_platform_serializes_frontend_schema() -> None:
    data = discord.serialize()

    assert data["id"] == "discord"
    assert data["connectionMode"] == "websocket"
    assert data["documentation"]["portalUrl"] == "https://discord.com/developers/applications"
    assert any(field["key"] == "applicationId" for field in data["schema"])


def test_registry_exposes_only_python_migrated_platforms() -> None:
    assert [platform.id for platform in platform_registry.list()] == ["discord"]


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
