from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from fastapi import BackgroundTasks

from app.models.agent_ops import AgentBotProvider
from app.services.agent_runtime import agent_runtime
from app.services.bot.inbound import NormalizedBotMessage
from app.services.bot.platforms.feishu.client import FeishuClient
from app.services.bot.platforms.line.client import LineClient
from app.services.bot.platforms.qq.client import QQClient
from app.services.bot.platforms.slack.client import SlackClient
from app.services.bot.platforms.teams.client import TeamsConnectorClient
from app.services.bot.platforms.telegram.client import TelegramClient
from app.services.bot.platforms.wechat.client import WechatClient

logger = logging.getLogger(__name__)


RuntimeFactory = Callable[..., Awaitable[dict[str, Any]]]
TeamsClientFactory = Callable[[str, str], TeamsConnectorClient]
TelegramClientFactory = Callable[[str], TelegramClient]
LineClientFactory = Callable[[str], LineClient]
SlackClientFactory = Callable[[str], SlackClient]
FeishuClientFactory = Callable[[str, str, str], FeishuClient]
QQClientFactory = Callable[[str, str], QQClient]
WechatClientFactory = Callable[[str], WechatClient]


@dataclass(frozen=True)
class BotBridgeDispatchResult:
    status: str
    operation_id: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def _thread_key(message: NormalizedBotMessage) -> str:
    return f"{message.platform}:{message.application_id}:{message.thread_id}"


def normalize_command(text: str) -> str | None:
    command = text.strip().split(maxsplit=1)[0].lower()
    if "@" in command:
        command = command.split("@", 1)[0]
    return command if command in {"/new", "/stop"} else None


def extract_assistant_text(result: dict[str, Any]) -> str | None:
    messages = result.get("messages")
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return None


class BotBridge:
    def __init__(
        self,
        *,
        runtime: Any = agent_runtime,
        teams_client_factory: TeamsClientFactory = TeamsConnectorClient,
        telegram_client_factory: TelegramClientFactory = TelegramClient,
        line_client_factory: LineClientFactory = LineClient,
        slack_client_factory: SlackClientFactory = SlackClient,
        feishu_client_factory: FeishuClientFactory = FeishuClient,
        qq_client_factory: QQClientFactory = QQClient,
        wechat_client_factory: WechatClientFactory = WechatClient,
    ) -> None:
        self._runtime = runtime
        self._active_operations: dict[str, str] = {}
        self._teams_client_factory = teams_client_factory
        self._telegram_client_factory = telegram_client_factory
        self._line_client_factory = line_client_factory
        self._slack_client_factory = slack_client_factory
        self._feishu_client_factory = feishu_client_factory
        self._qq_client_factory = qq_client_factory
        self._wechat_client_factory = wechat_client_factory

    async def enqueue(
        self,
        provider: AgentBotProvider,
        message: NormalizedBotMessage,
        credentials: dict[str, Any],
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> BotBridgeDispatchResult:
        if not message.text.strip():
            return BotBridgeDispatchResult(status="ignored", reason="empty_message")

        command = normalize_command(message.text)
        if command == "/new":
            self._active_operations.pop(_thread_key(message), None)
            if background_tasks is not None:
                background_tasks.add_task(
                    self.send_platform_reply,
                    message,
                    credentials,
                    "Started a new conversation.",
                )
            return BotBridgeDispatchResult(status="handled", reason="new_conversation")
        if command == "/stop":
            operation_id = self._active_operations.pop(_thread_key(message), None)
            if operation_id:
                interrupted = await self._runtime.interrupt_operation(operation_id)
                reply = "Stopped the current response." if interrupted else "There is no active response to stop."
            else:
                reply = "There is no active response to stop."
            if background_tasks is not None:
                background_tasks.add_task(self.send_platform_reply, message, credentials, reply)
            return BotBridgeDispatchResult(status="handled", reason="stop")

        operation = await self._runtime.create_operation(
            provider.user_id,
            [{"role": "user", "content": message.text}],
            agent_id=provider.agent_id,
            session_id=message.thread_id,
        )
        operation_id = operation.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            return BotBridgeDispatchResult(status="failed", reason="operation_not_created")

        self._active_operations[_thread_key(message)] = operation_id
        if background_tasks is not None:
            background_tasks.add_task(self.run_and_reply, operation_id, message, credentials)

        return BotBridgeDispatchResult(status="queued", operation_id=operation_id)

    async def run_and_reply(
        self,
        operation_id: str,
        message: NormalizedBotMessage,
        credentials: dict[str, Any],
    ) -> None:
        try:
            result = await self._runtime.run_operation(operation_id)
        except Exception:
            logger.exception("Bot bridge operation failed operation_id=%s", operation_id)
            if self._active_operations.get(_thread_key(message)) == operation_id:
                self._active_operations.pop(_thread_key(message), None)
            return
        finally:
            if self._active_operations.get(_thread_key(message)) == operation_id:
                self._active_operations.pop(_thread_key(message), None)

        text = extract_assistant_text(result)
        if not text:
            logger.debug("Bot bridge operation produced no assistant text operation_id=%s", operation_id)
            return

        await self.send_platform_reply(message, credentials, text)

    async def send_platform_reply(
        self,
        message: NormalizedBotMessage,
        credentials: dict[str, Any],
        text: str,
    ) -> None:
        if message.platform == "teams":
            app_password = credentials.get("appPassword")
            if not isinstance(app_password, str) or not app_password:
                logger.warning("Teams bot reply skipped because appPassword is missing")
                return
            await self._teams_client_factory(message.application_id, app_password).send_reply(message.raw, text)
            return
        if message.platform == "telegram":
            bot_token = credentials.get("botToken")
            if not isinstance(bot_token, str) or not bot_token:
                logger.warning("Telegram bot reply skipped because botToken is missing")
                return
            await self._telegram_client_factory(bot_token).send_reply(message.raw, text)
            return
        if message.platform == "line":
            channel_access_token = credentials.get("channelAccessToken")
            if not isinstance(channel_access_token, str) or not channel_access_token:
                logger.warning("LINE bot reply skipped because channelAccessToken is missing")
                return
            await self._line_client_factory(channel_access_token).send_reply(message.raw, text)
            return
        if message.platform == "slack":
            bot_token = credentials.get("botToken")
            if not isinstance(bot_token, str) or not bot_token:
                logger.warning("Slack bot reply skipped because botToken is missing")
                return
            await self._slack_client_factory(bot_token).send_reply(message.raw, text)
            return
        if message.platform in {"feishu", "lark"}:
            app_secret = credentials.get("appSecret")
            if not isinstance(app_secret, str) or not app_secret:
                logger.warning("%s bot reply skipped because appSecret is missing", message.platform)
                return
            await self._feishu_client_factory(message.application_id, app_secret, message.platform).send_reply(
                message.raw,
                text,
            )
            return
        if message.platform == "qq":
            app_secret = credentials.get("appSecret")
            if not isinstance(app_secret, str) or not app_secret:
                logger.warning("QQ bot reply skipped because appSecret is missing")
                return
            await self._qq_client_factory(message.application_id, app_secret).send_reply(message.raw, text)
            return
        if message.platform == "wechat":
            bot_token = credentials.get("botToken")
            if not isinstance(bot_token, str) or not bot_token:
                logger.warning("WeChat bot reply skipped because botToken is missing")
                return
            await self._wechat_client_factory(bot_token).send_reply(message.raw, text)
            return

        logger.info("Bot bridge outbound reply is not implemented for platform=%s", message.platform)


bot_bridge = BotBridge()
