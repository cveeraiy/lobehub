from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.common import (
    DEFAULT_BOT_DEBOUNCE_MS,
    MAX_BOT_DEBOUNCE_MS,
    display_tool_calls_field,
    make_user_id_field,
)
from app.services.bot.platforms.types import PlatformDefinition, ValidationError, ValidationResult

LINE_API_BASE = "https://api.line.me"


async def fetch_line_bot_info(channel_access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{LINE_API_BASE}/v2/bot/info",
            headers={"Authorization": f"Bearer {channel_access_token}"},
        )
    if not response.is_success:
        text = response.text
        raise ValueError(f"LINE /v2/bot/info failed: {response.status_code} {text}".strip())
    data = response.json()
    if not data.get("userId"):
        raise ValueError("LINE /v2/bot/info returned no userId")
    return data


class LinePlatformDefinition(PlatformDefinition):
    id = "line"
    name = "LINE"
    connection_mode = "webhook"
    description = "Connect a LINE Messaging API bot for direct and group chats."
    documentation = {
        "portalUrl": "https://developers.line.biz/console/",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/line",
    }
    show_webhook_url = True
    supports_markdown = False
    supports_message_edit = False
    schema = [
        {
            "key": "applicationId",
            "description": "channel.line.destinationUserIdHint",
            "label": "channel.line.destinationUserId",
            "placeholder": "channel.line.destinationUserIdPlaceholder",
            "required": True,
            "type": "string",
        },
        {
            "key": "credentials",
            "label": "channel.credentials",
            "properties": [
                {
                    "key": "channelAccessToken",
                    "description": "channel.line.channelAccessTokenHint",
                    "label": "channel.line.channelAccessToken",
                    "required": True,
                    "type": "password",
                },
                {
                    "key": "channelSecret",
                    "description": "channel.line.channelSecretHint",
                    "label": "channel.line.channelSecret",
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
                {
                    "key": "charLimit",
                    "default": 5000,
                    "description": "channel.charLimitHint",
                    "label": "channel.charLimit",
                    "maximum": 5000,
                    "minimum": 100,
                    "type": "number",
                },
                {
                    "key": "concurrency",
                    "default": "queue",
                    "description": "channel.concurrencyHint",
                    "enum": ["queue", "debounce"],
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
                make_user_id_field("line"),
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
        channel_access_token = credentials.get("channelAccessToken")
        if not channel_access_token:
            errors.append(
                ValidationError(
                    field="channelAccessToken",
                    message="Channel Access Token is required",
                )
            )
        if not credentials.get("channelSecret"):
            errors.append(ValidationError(field="channelSecret", message="Channel Secret is required"))
        if not application_id:
            errors.append(ValidationError(field="applicationId", message="Destination User ID is required"))
        if errors:
            return ValidationResult(valid=False, errors=errors)

        try:
            info = await fetch_line_bot_info(channel_access_token or "")
        except ValueError as error:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(field="channelAccessToken", message=str(error))],
            )

        if info.get("userId") != application_id:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        field="applicationId",
                        message=(
                            f"Channel access token belongs to bot {info.get('userId')}, "
                            f"not {application_id}"
                        ),
                    )
                ],
            )
        return ValidationResult(valid=True)


line = LinePlatformDefinition()

