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

SLACK_API_BASE = "https://slack.com/api"
MAX_SLACK_HISTORY_LIMIT = 999
DEFAULT_SLACK_CONNECTION_MODE = "websocket"


class SlackPlatformDefinition(PlatformDefinition):
    id = "slack"
    name = "Slack"
    connection_mode = DEFAULT_SLACK_CONNECTION_MODE
    description = "Connect a Slack bot"
    documentation = {
        "portalUrl": "https://api.slack.com/apps",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/slack",
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
                    "key": "botToken",
                    "description": "channel.botTokenEncryptedHint",
                    "label": "channel.botToken",
                    "required": True,
                    "type": "password",
                },
                {
                    "key": "signingSecret",
                    "description": "channel.signingSecretHint",
                    "label": "channel.signingSecret",
                    "required": True,
                    "type": "password",
                },
                {
                    "key": "appToken",
                    "description": "channel.slack.appTokenHint",
                    "label": "channel.slack.appToken",
                    "placeholder": "xapp-...",
                    "type": "password",
                },
            ],
            "type": "object",
        },
        {
            "key": "settings",
            "label": "channel.settings",
            "properties": [
                make_user_id_field("slack"),
                make_server_id_field("slack"),
                {
                    "key": "connectionMode",
                    "default": DEFAULT_SLACK_CONNECTION_MODE,
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
                    "default": 4000,
                    "description": "channel.charLimitHint",
                    "label": "channel.charLimit",
                    "maximum": 40_000,
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
                    "maximum": MAX_SLACK_HISTORY_LIMIT,
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
        app_token = credentials.get("appToken")
        if not bot_token:
            errors.append(ValidationError(field="botToken", message="Bot Token is required"))
        if not credentials.get("signingSecret"):
            errors.append(ValidationError(field="signingSecret", message="Signing Secret is required"))
        if (settings or {}).get("connectionMode") == "websocket" and not app_token:
            errors.append(
                ValidationError(
                    field="appToken",
                    message="App-Level Token is required for WebSocket (Socket Mode)",
                )
            )
        if errors:
            return ValidationResult(valid=False, errors=errors)

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                auth_response = await client.post(
                    f"{SLACK_API_BASE}/auth.test",
                    headers={
                        "Authorization": f"Bearer {bot_token}",
                        "Content-Type": "application/json",
                    },
                )
                auth_response.raise_for_status()
                auth_data = auth_response.json()
                if not auth_data.get("ok"):
                    raise ValueError(auth_data.get("error") or "auth.test failed")

                if app_token:
                    app_response = await client.post(
                        f"{SLACK_API_BASE}/apps.connections.open",
                        headers={
                            "Authorization": f"Bearer {app_token}",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                    app_response.raise_for_status()
                    app_data = app_response.json()
                    if not app_data.get("ok"):
                        return ValidationResult(
                            valid=False,
                            errors=[
                                ValidationError(
                                    field="appToken",
                                    message=f"App Token validation failed: {app_data.get('error')}",
                                )
                            ],
                        )
            except (httpx.HTTPError, ValueError) as error:
                message = str(error) or "Failed to authenticate with Slack API"
                return ValidationResult(
                    valid=False,
                    errors=[ValidationError(field="botToken", message=message)],
                )

        return ValidationResult(valid=True)


slack = SlackPlatformDefinition()

