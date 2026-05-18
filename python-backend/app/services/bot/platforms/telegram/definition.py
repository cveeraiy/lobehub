from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.common import (
    DEFAULT_BOT_DEBOUNCE_MS,
    MAX_BOT_DEBOUNCE_MS,
    allow_from_field,
    display_tool_calls_field,
    make_dm_policy_field,
    make_group_policy_fields,
    make_user_id_field,
)
from app.services.bot.platforms.types import PlatformDefinition, ValidationError, ValidationResult

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramPlatformDefinition(PlatformDefinition):
    id = "telegram"
    name = "Telegram"
    connection_mode = "webhook"
    description = "Connect a Telegram bot"
    documentation = {
        "portalUrl": "https://t.me/BotFather",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/telegram",
    }
    schema = [
        {
            "key": "credentials",
            "label": "channel.credentials",
            "properties": [
                {
                    "key": "botToken",
                    "description": "channel.botTokenEncryptedHint",
                    "label": "channel.botToken",
                    "required": True,
                    "type": "password",
                },
                {
                    "key": "secretToken",
                    "description": "channel.secretTokenHint",
                    "label": "channel.secretToken",
                    "required": False,
                    "type": "password",
                },
                {
                    "devOnly": True,
                    "key": "webhookProxyUrl",
                    "description": "channel.devWebhookProxyUrlHint",
                    "label": "channel.devWebhookProxyUrl",
                    "required": False,
                    "type": "string",
                },
            ],
            "type": "object",
        },
        {
            "key": "settings",
            "label": "channel.settings",
            "properties": [
                make_user_id_field("telegram"),
                {
                    "key": "charLimit",
                    "default": 4000,
                    "description": "channel.charLimitHint",
                    "label": "channel.charLimit",
                    "maximum": 4096,
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
        bot_token = credentials.get("botToken")
        if not bot_token:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(field="botToken", message="Bot Token is required")],
            )

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(f"{TELEGRAM_API_BASE}/bot{bot_token}/getMe")
            except httpx.HTTPError:
                return ValidationResult(
                    valid=False,
                    errors=[
                        ValidationError(
                            field="botToken",
                            message="Failed to authenticate with Telegram API",
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
                    message="Failed to authenticate with Telegram API",
                )
            ],
        )


telegram = TelegramPlatformDefinition()

