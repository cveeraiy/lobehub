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

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
LARK_API_BASE = "https://open.larksuite.com/open-apis"
DEFAULT_FEISHU_CONNECTION_MODE = "websocket"
MAX_FEISHU_HISTORY_LIMIT = 50


def _shared_schema() -> list[dict[str, Any]]:
    return [
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
                {
                    "key": "verificationToken",
                    "description": "channel.verificationTokenHint",
                    "label": "channel.verificationToken",
                    "required": False,
                    "type": "password",
                },
                {
                    "key": "encryptKey",
                    "description": "channel.encryptKeyHint",
                    "label": "channel.encryptKey",
                    "required": False,
                    "type": "password",
                },
            ],
            "type": "object",
        },
        {
            "key": "settings",
            "label": "channel.settings",
            "properties": [
                make_user_id_field("feishu"),
                {
                    "key": "connectionMode",
                    "default": DEFAULT_FEISHU_CONNECTION_MODE,
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
                    "maximum": 30_000,
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
                    "maximum": MAX_FEISHU_HISTORY_LIMIT,
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


class FeishuPlatformDefinition(PlatformDefinition):
    id = "feishu"
    name = "Feishu"
    connection_mode = DEFAULT_FEISHU_CONNECTION_MODE
    description = "Connect a Feishu bot"
    documentation = {
        "portalUrl": "https://open.feishu.cn/app",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/feishu",
    }
    schema = _shared_schema()
    supports_markdown = False
    api_base = FEISHU_API_BASE

    async def validate_credentials(
        self,
        credentials: dict[str, str],
        settings: dict[str, Any] | None = None,
        application_id: str | None = None,
    ) -> ValidationResult:
        errors: list[ValidationError] = []
        app_secret = credentials.get("appSecret")
        if not application_id:
            errors.append(ValidationError(field="applicationId", message="Application ID is required"))
        if not app_secret:
            errors.append(ValidationError(field="appSecret", message="App Secret is required"))
        if errors:
            return ValidationResult(valid=False, errors=errors)

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.post(
                    f"{self.api_base}/auth/v3/tenant_access_token/internal",
                    json={"app_id": application_id, "app_secret": app_secret},
                )
                response.raise_for_status()
                data = response.json()
                if data.get("code") != 0 or not data.get("tenant_access_token"):
                    raise ValueError(f"{data.get('code')} {data.get('msg')}".strip())
            except (httpx.HTTPError, ValueError) as error:
                return ValidationResult(
                    valid=False,
                    errors=[
                        ValidationError(
                            field="credentials",
                            message=str(error) or "Failed to authenticate with Feishu API",
                        )
                    ],
                )

        return ValidationResult(valid=True)


class LarkPlatformDefinition(FeishuPlatformDefinition):
    id = "lark"
    name = "Lark"
    description = "Connect a Lark bot"
    documentation = {
        "portalUrl": "https://open.larksuite.com/app",
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/lark",
    }
    api_base = LARK_API_BASE


feishu = FeishuPlatformDefinition()
lark = LarkPlatformDefinition()
