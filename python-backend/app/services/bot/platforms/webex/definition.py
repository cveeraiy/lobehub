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
    make_user_id_field,
)
from app.services.bot.platforms.types import PlatformDefinition, ValidationError, ValidationResult

WEBEX_API_BASE = "https://webexapis.com/v1"
MAX_WEBEX_MESSAGE_LENGTH = 7400


class WebexPlatformDefinition(PlatformDefinition):
    id = "webex"
    name = "Cisco Webex"
    connection_mode = "webhook"
    description = "Connect a Cisco Webex bot"
    documentation = {
        "portalUrl": "https://developer.webex.com/my-apps",
        "setupGuideUrl": "https://developer.webex.com/docs/bots",
    }
    show_webhook_url = True
    supports_markdown = True
    supports_message_edit = False
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
                    "key": "botToken",
                    "description": "channel.botTokenEncryptedHint",
                    "label": "channel.botToken",
                    "required": True,
                    "type": "password",
                },
                {
                    "key": "webhookSecret",
                    "description": "channel.signingSecretHint",
                    "label": "channel.signingSecret",
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
                make_user_id_field("webex"),
                {
                    "key": "charLimit",
                    "default": MAX_WEBEX_MESSAGE_LENGTH,
                    "description": "channel.charLimitHint",
                    "label": "channel.charLimit",
                    "maximum": MAX_WEBEX_MESSAGE_LENGTH,
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
                    "maximum": 100,
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
        bot_token = credentials.get("botToken")
        if not bot_token:
            errors.append(ValidationError(field="botToken", message="Bot Token is required"))
        if not credentials.get("webhookSecret"):
            errors.append(ValidationError(field="webhookSecret", message="Webhook Secret is required"))
        if not application_id:
            errors.append(ValidationError(field="applicationId", message="Bot Person ID is required"))
        if errors:
            return ValidationResult(valid=False, errors=errors)

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get(
                    f"{WEBEX_API_BASE}/people/me",
                    headers={"Authorization": f"Bearer {bot_token}"},
                )
            except httpx.HTTPError:
                return ValidationResult(
                    valid=False,
                    errors=[ValidationError(field="botToken", message="Failed to authenticate with Webex API")],
                )

        if not response.is_success:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(field="botToken", message="Failed to authenticate with Webex API")],
            )
        data = response.json()
        if isinstance(data, dict) and data.get("id") != application_id:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(field="applicationId", message="Application ID must match the Webex bot ID")],
            )
        return ValidationResult(valid=True)


webex = WebexPlatformDefinition()
