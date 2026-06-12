from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.common import (
    DEFAULT_BOT_DEBOUNCE_MS,
    DEFAULT_BOT_HISTORY_LIMIT,
    MAX_BOT_DEBOUNCE_MS,
    MIN_BOT_HISTORY_LIMIT,
    allow_from_field,
    display_tool_calls_field,
    make_dm_policy_field,
    make_group_policy_fields,
    make_server_id_field,
    make_user_id_field,
)
from app.services.bot.platforms.types import PlatformDefinition, ValidationError, ValidationResult

MAX_DISCORD_HISTORY_LIMIT = 100


class DiscordPlatformDefinition(PlatformDefinition):
    id = "discord"
    name = "Discord"
    connection_mode = "websocket"
    description = "Connect a Discord bot"
    documentation = {
        "portalUrl": "https://discord.com/developers/applications",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/discord",
    }
    schema = [
        {
            "key": "applicationId",
            "description": "channel.applicationIdHint",
            "label": "channel.applicationId",
            "required": True,
            "type": "string",
        },
        {
            "key": "credentials",
            "label": "channel.credentials",
            "properties": [
                {
                    "key": "publicKey",
                    "description": "channel.publicKeyHint",
                    "label": "channel.publicKey",
                    "required": True,
                    "type": "string",
                },
                {
                    "key": "botToken",
                    "description": "channel.botTokenEncryptedHint",
                    "label": "channel.botToken",
                    "required": True,
                    "type": "password",
                },
            ],
            "type": "object",
        },
        {
            "key": "settings",
            "label": "channel.settings",
            "properties": [
                make_user_id_field("discord"),
                make_server_id_field("discord"),
                {
                    "key": "charLimit",
                    "default": 2000,
                    "description": "channel.charLimitHint",
                    "label": "channel.charLimit",
                    "maximum": 2000,
                    "minimum": 100,
                    "type": "number",
                },
                {
                    "key": "concurrency",
                    "default": "queue",
                    "description": "channel.concurrencyHint",
                    "enum": ["queue", "debounce"],
                    "enumDescriptions": [
                        "channel.concurrencyQueueHint",
                        "channel.concurrencyDebounceHint",
                    ],
                    "enumLabels": ["channel.concurrencyQueue", "channel.concurrencyDebounce"],
                    "label": "channel.concurrency",
                    "type": "string",
                },
                {
                    "key": "debounceMs",
                    "default": DEFAULT_BOT_DEBOUNCE_MS,
                    "description": "channel.debounceMsHint",
                    "label": "channel.debounceMs",
                    "maximum": MAX_BOT_DEBOUNCE_MS,
                    "minimum": 100,
                    "type": "number",
                    "visibleWhen": {"field": "concurrency", "value": "debounce"},
                },
                {
                    "key": "showUsageStats",
                    "default": False,
                    "description": "channel.showUsageStatsHint",
                    "label": "channel.showUsageStats",
                    "type": "boolean",
                },
                display_tool_calls_field(),
                {
                    "key": "historyLimit",
                    "default": DEFAULT_BOT_HISTORY_LIMIT,
                    "description": "channel.historyLimitHint",
                    "label": "channel.historyLimit",
                    "maximum": MAX_DISCORD_HISTORY_LIMIT,
                    "minimum": MIN_BOT_HISTORY_LIMIT,
                    "type": "number",
                },
                make_dm_policy_field("open"),
                *make_group_policy_fields("open"),
                allow_from_field(),
            ],
            "type": "object",
        },
    ]

    async def validate_credentials(
        self,
        credentials: dict[str, str],
        settings: dict[str, Any] | None = None,
        application_id: str | None = None,
    ) -> ValidationResult:
        errors: list[ValidationError] = []
        if not credentials.get("botToken"):
            errors.append(ValidationError(field="botToken", message="Bot Token is required"))
        if not credentials.get("publicKey"):
            errors.append(ValidationError(field="publicKey", message="Public Key is required"))
        if errors:
            return ValidationResult(valid=False, errors=errors)

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {credentials['botToken']}"},
                )
            except httpx.HTTPError:
                return ValidationResult(
                    valid=False,
                    errors=[
                        ValidationError(
                            field="botToken",
                            message="Failed to authenticate with Discord API",
                        )
                    ],
                )

        if response.is_success:
            return ValidationResult(valid=True)
        return ValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    field="botToken",
                    message="Failed to authenticate with Discord API",
                )
            ],
        )


discord = DiscordPlatformDefinition()
