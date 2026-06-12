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

MICROSOFT_BOT_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
MICROSOFT_BOT_SCOPE = "https://api.botframework.com/.default"


class TeamsPlatformDefinition(PlatformDefinition):
    id = "teams"
    name = "Microsoft Teams"
    connection_mode = "webhook"
    description = "Connect a Microsoft Teams bot"
    documentation = {
        "portalUrl": "https://dev.botframework.com/",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/teams",
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
                    "key": "appPassword",
                    "description": "channel.teams.appPasswordHint",
                    "label": "channel.teams.appPassword",
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
                make_user_id_field("teams"),
                {
                    "key": "charLimit",
                    "default": 4000,
                    "description": "channel.charLimitHint",
                    "label": "channel.charLimit",
                    "maximum": 28_000,
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
                    "maximum": DEFAULT_BOT_HISTORY_LIMIT,
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
        app_password = credentials.get("appPassword")
        if not application_id:
            errors.append(ValidationError(field="applicationId", message="Microsoft App ID is required"))
        if not app_password:
            errors.append(ValidationError(field="appPassword", message="Microsoft App Password is required"))
        if errors:
            return ValidationResult(valid=False, errors=errors)

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.post(
                    MICROSOFT_BOT_TOKEN_URL,
                    data={
                        "client_id": application_id,
                        "client_secret": app_password,
                        "grant_type": "client_credentials",
                        "scope": MICROSOFT_BOT_SCOPE,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
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
                            message="Failed to authenticate with Microsoft Bot Framework",
                        )
                    ],
                )

        return ValidationResult(valid=True)


teams = TeamsPlatformDefinition()
