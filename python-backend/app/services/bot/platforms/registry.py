from __future__ import annotations

from app.services.bot.platforms.discord.definition import discord
from app.services.bot.platforms.feishu.definition import feishu, lark
from app.services.bot.platforms.line.definition import line
from app.services.bot.platforms.qq.definition import qq
from app.services.bot.platforms.slack.definition import slack
from app.services.bot.platforms.teams.definition import teams
from app.services.bot.platforms.telegram.definition import telegram
from app.services.bot.platforms.types import PlatformDefinition
from app.services.bot.platforms.wechat.definition import wechat


class PlatformRegistry:
    def __init__(self) -> None:
        self._platforms: dict[str, PlatformDefinition] = {}

    def register(self, definition: PlatformDefinition) -> None:
        if definition.id in self._platforms:
            raise ValueError(f"Platform '{definition.id}' is already registered")
        self._platforms[definition.id] = definition

    def get(self, platform: str) -> PlatformDefinition | None:
        return self._platforms.get(platform)

    def require(self, platform: str) -> PlatformDefinition:
        definition = self.get(platform)
        if definition is None:
            raise ValueError(f"Unsupported bot platform: {platform}")
        return definition

    def list(self) -> list[PlatformDefinition]:
        return list(self._platforms.values())

    def list_serialized(self) -> list[dict]:
        return [definition.serialize() for definition in self.list()]


platform_registry = PlatformRegistry()
platform_registry.register(discord)
platform_registry.register(telegram)
platform_registry.register(line)
platform_registry.register(slack)
platform_registry.register(feishu)
platform_registry.register(lark)
platform_registry.register(qq)
platform_registry.register(wechat)
platform_registry.register(teams)
