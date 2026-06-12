from __future__ import annotations

from typing import Any

from app.services.bot.platforms.common import MAX_BOT_DEBOUNCE_MS, display_tool_calls_field
from app.services.bot.platforms.types import PlatformDefinition, ValidationError, ValidationResult


class WechatPlatformDefinition(PlatformDefinition):
    id = "wechat"
    name = "WeChat"
    connection_mode = "polling"
    description = "Connect a WeChat bot via iLink API"
    documentation = {
        "setupGuideUrl": "https://lobehub.com/docs/usage/channels/wechat",
    }
    supports_message_edit = False
    schema = [
        {
            "key": "settings",
            "label": "channel.settings",
            "properties": [
                {
                    "key": "charLimit",
                    "default": 2000,
                    "description": "channel.charLimitHint",
                    "label": "channel.charLimit",
                    "maximum": 2048,
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
        if not credentials.get("botToken"):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(field="botToken", message="Bot Token is required")],
            )

        return ValidationResult(valid=True)


wechat = WechatPlatformDefinition()
