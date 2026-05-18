from __future__ import annotations

from typing import Any

Field = dict[str, Any]

DEFAULT_BOT_DEBOUNCE_MS = 2000
DEFAULT_BOT_HISTORY_LIMIT = 50
MAX_BOT_DEBOUNCE_MS = 30_000
MIN_BOT_HISTORY_LIMIT = 1


def display_tool_calls_field() -> Field:
    return {
        "key": "displayToolCalls",
        "default": False,
        "description": "channel.displayToolCallsHint",
        "label": "channel.displayToolCalls",
        "type": "boolean",
    }


def make_server_id_field(platform: str) -> Field:
    tooltips = {
        "discord": "channel.serverIdHint.discord",
        "slack": "channel.serverIdHint.slack",
    }
    return {
        "key": "serverId",
        "description": "channel.serverIdHint",
        "label": "channel.serverId",
        "tooltip": tooltips.get(platform),
        "type": "string",
    }


def make_user_id_field(platform: str) -> Field:
    tooltips = {
        "discord": "channel.userIdHint.discord",
        "feishu": "channel.userIdHint.feishu",
        "qq": "channel.userIdHint.qq",
        "slack": "channel.userIdHint.slack",
        "telegram": "channel.userIdHint.telegram",
    }
    return {
        "key": "userId",
        "description": "channel.userIdHint",
        "label": "channel.userId",
        "tooltip": tooltips.get(platform),
        "type": "string",
    }


def make_dm_policy_field(policy: str = "open") -> Field:
    return {
        "key": "dmPolicy",
        "default": policy,
        "description": "channel.dmPolicyHint",
        "enum": ["open", "allowlist", "pairing", "disabled"],
        "enumDescriptions": [
            "channel.dmPolicyOpenHint",
            "channel.dmPolicyAllowlistHint",
            "channel.dmPolicyPairingHint",
            "channel.dmPolicyDisabledHint",
        ],
        "enumLabels": [
            "channel.dmPolicyOpen",
            "channel.dmPolicyAllowlist",
            "channel.dmPolicyPairing",
            "channel.dmPolicyDisabled",
        ],
        "label": "channel.dmPolicy",
        "type": "string",
    }


def _allowlist_items(prefix: str) -> Field:
    return {
        "key": "item",
        "label": "",
        "type": "object",
        "properties": [
            {
                "key": "id",
                "label": f"channel.{prefix}IdLabel",
                "placeholder": f"channel.{prefix}IdPlaceholder",
                "required": True,
                "type": "string",
            },
            {
                "key": "name",
                "label": f"channel.{prefix}NameLabel",
                "placeholder": f"channel.{prefix}NamePlaceholder",
                "type": "string",
            },
        ],
    }


def allow_from_field() -> Field:
    return {
        "key": "allowFrom",
        "default": [],
        "description": "channel.allowFromHint",
        "label": "channel.allowFrom",
        "type": "array",
        "items": _allowlist_items("allowFrom"),
    }


def make_group_policy_fields(policy: str = "open") -> list[Field]:
    return [
        {
            "key": "groupPolicy",
            "default": policy,
            "description": "channel.groupPolicyHint",
            "enum": ["open", "allowlist", "disabled"],
            "enumDescriptions": [
                "channel.groupPolicyOpenHint",
                "channel.groupPolicyAllowlistHint",
                "channel.groupPolicyDisabledHint",
            ],
            "enumLabels": [
                "channel.groupPolicyOpen",
                "channel.groupPolicyAllowlist",
                "channel.groupPolicyDisabled",
            ],
            "label": "channel.groupPolicy",
            "type": "string",
        },
        {
            "key": "groupAllowFrom",
            "default": [],
            "description": "channel.groupAllowFromHint",
            "label": "channel.groupAllowFrom",
            "type": "array",
            "items": _allowlist_items("groupAllowFrom"),
            "visibleWhen": {"field": "groupPolicy", "value": "allowlist"},
        },
    ]


def extract_defaults(schema: list[Field]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for field in schema:
        if "default" in field:
            defaults[field["key"]] = field["default"]
        if field.get("type") == "object" and field.get("properties"):
            nested = extract_defaults(field["properties"])
            if nested:
                defaults[field["key"]] = nested
    return defaults


def merge_settings_with_defaults(platform_schema: list[Field], settings: dict[str, Any] | None) -> dict[str, Any]:
    settings_schema = next((field for field in platform_schema if field.get("key") == "settings"), None)
    defaults = extract_defaults(settings_schema.get("properties", []) if settings_schema else [])
    return {**defaults, **(settings or {})}

