from __future__ import annotations

from typing import Any

import httpx

from app.services.bot.platforms.common import (
    MAX_BOT_DEBOUNCE_MS,
    allow_from_field,
    display_tool_calls_field,
    make_dm_policy_field,
    make_group_policy_fields,
    make_user_id_field,
)
from app.services.bot.platforms.types import PlatformDefinition, ValidationError, ValidationResult

QQ_AUTH_URL = "https://bots.qq.com/app/getAppAccessToken"
DEFAULT_QQ_CONNECTION_MODE = "websocket"


class QQPlatformDefinition(PlatformDefinition):
    id = "qq"
    name = "QQ"
    connection_mode = DEFAULT_QQ_CONNECTION_MODE
    description = "Connect a QQ bot"
    documentation = {
        "portalUrl": "https://q.qq.com/",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/qq",
    }
    supports_markdown = False
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
                    "key": "appSecret",
                    "description": "channel.appSecretHint",
                    "label": "channel.appSecret",
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
                make_user_id_field("qq"),
                {
                    "key": "connectionMode",
                    "default": DEFAULT_QQ_CONNECTION_MODE,
                    "description": "channel.connectionModeHint",
                    "enum": ["websocket", "webhook"],
                    "enumDescriptions": [
                        "channel.connectionModeWebSocketHint",
                        "channel.connectionModeWebhookHint",
                    ],
                    "enumLabels": ["channel.connectionModeWebSocket", "channel.connectionModeWebhook"],
                    "label": "channel.connectionMode",
                    "type": "string",
                },
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
                    "default": 5000,
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
        errors: list[ValidationError] = []
        app_secret = credentials.get("appSecret")
        if not application_id:
            errors.append(ValidationError(field="applicationId", message="App ID is required"))
        if not app_secret:
            errors.append(ValidationError(field="appSecret", message="App Secret is required"))
        if errors:
            return ValidationResult(valid=False, errors=errors)

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.post(
                    QQ_AUTH_URL,
                    json={"appId": application_id, "clientSecret": app_secret},
                )
                response.raise_for_status()
                data = response.json()
                if not data.get("access_token"):
                    raise ValueError("missing access_token")
            except (httpx.HTTPError, ValueError):
                return ValidationResult(
                    valid=False,
                    errors=[
                        ValidationError(
                            field="credentials",
                            message="Failed to authenticate with QQ API",
                        )
                    ],
                )

        return ValidationResult(valid=True)


qq = QQPlatformDefinition()
