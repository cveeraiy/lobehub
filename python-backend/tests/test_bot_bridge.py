from __future__ import annotations

from typing import Any

import pytest

from app.models.agent_ops import AgentBotProvider
from app.services.bot.bridge import BotBridge, build_user_content, extract_assistant_text
from app.services.bot.inbound import NormalizedAttachment, NormalizedBotMessage


class FakeRuntime:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.interrupted: list[str] = []
        self.ran: list[str] = []

    async def create_operation(self, user_id: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        self.created.append({"user_id": user_id, "messages": messages, **kwargs})
        return {"operation_id": "op-1", "status": "idle"}

    async def run_operation(self, operation_id: str) -> dict[str, Any]:
        self.ran.append(operation_id)
        return {"messages": [{"role": "assistant", "content": "hello from agent"}]}

    async def interrupt_operation(self, operation_id: str) -> bool:
        self.interrupted.append(operation_id)
        return True


class FakeBackgroundTasks:
    def __init__(self) -> None:
        self.tasks: list[tuple[Any, tuple[Any, ...]]] = []

    def add_task(self, func: Any, *args: Any) -> None:
        self.tasks.append((func, args))


class FakeTeamsClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, app_id: str, app_password: str) -> None:
        self.app_id = app_id
        self.app_password = app_password

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append(
            {
                "activity": activity,
                "app_id": self.app_id,
                "app_password": self.app_password,
                "text": text,
            }
        )
        return {"id": "reply-1"}


class FakeDiscordClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append({"activity": activity, "bot_token": self.bot_token, "text": text})
        return {"id": "reply-1"}


class FakeTelegramClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append({"activity": activity, "bot_token": self.bot_token, "text": text})
        return {"ok": True}


class FakeLineClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, channel_access_token: str) -> None:
        self.channel_access_token = channel_access_token

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append(
            {
                "activity": activity,
                "channel_access_token": self.channel_access_token,
                "text": text,
            }
        )
        return {}


class FakeSlackClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append({"activity": activity, "bot_token": self.bot_token, "text": text})
        return {"ok": True}


class FakeFeishuClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, app_id: str, app_secret: str, platform: str = "feishu") -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.platform = platform

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append(
            {
                "activity": activity,
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "platform": self.platform,
                "text": text,
            }
        )
        return {"code": 0}


class FakeQQClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append(
            {
                "activity": activity,
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "text": text,
            }
        )
        return {"id": "reply-msg"}


class FakeWechatClient:
    replies: list[dict[str, Any]] = []

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    async def send_reply(self, activity: dict[str, Any], text: str) -> dict[str, Any]:
        self.replies.append({"activity": activity, "bot_token": self.bot_token, "text": text})
        return {"ret": 0}


def make_provider(platform: str = "teams") -> AgentBotProvider:
    return AgentBotProvider(
        id="provider-1",
        agent_id="agent-1",
        user_id="user-1",
        platform=platform,
        application_id="app-1",
        credentials=None,
        settings={},
        enabled=True,
    )


def make_message(platform: str = "teams", text: str = "hello") -> NormalizedBotMessage:
    return NormalizedBotMessage(
        platform=platform,
        application_id="app-1",
        message_id="msg-1",
        thread_id=f"{platform}:thread-1",
        channel_id="thread-1",
        author_id="user-ext-1",
        text=text,
        is_dm=True,
        raw={
            "id": "activity-1",
            "serviceUrl": "https://smba.trafficmanager.net/teams/",
            "conversation": {"id": "conv-1"},
            "from": {"id": "user-1"},
            "recipient": {"id": "bot-1"},
        },
    )


def test_extract_assistant_text_returns_last_assistant_message() -> None:
    assert extract_assistant_text(
        {
            "messages": [
                {"role": "assistant", "content": "first"},
                {"role": "user", "content": "next"},
                {"role": "assistant", "content": "last"},
            ]
        }
    ) == "last"


def test_build_user_content_includes_attachment_summary() -> None:
    message = make_message(text="see attached")
    message = NormalizedBotMessage(
        **{**message.to_dict(), "attachments": [NormalizedAttachment(type="image", id="file-1", mime_type="image/png")]}
    )

    assert build_user_content(message) == "see attached\n\nAttachments:\n1. image mime=image/png id=file-1"


def test_normalize_command_handles_bot_mentions() -> None:
    from app.services.bot.bridge import normalize_command

    assert normalize_command("/new") == "/new"
    assert normalize_command("/stop@mybot please") == "/stop"
    assert normalize_command("hello") is None


@pytest.mark.asyncio
async def test_enqueue_creates_agent_runtime_operation() -> None:
    runtime = FakeRuntime()
    bridge = BotBridge(runtime=runtime)

    result = await bridge.enqueue(make_provider(), make_message(), {"appPassword": "secret"})

    assert result.to_dict() == {"status": "queued", "operation_id": "op-1"}
    assert runtime.created == [
        {
            "user_id": "user-1",
            "messages": [{"role": "user", "content": "hello"}],
            "agent_id": "agent-1",
            "session_id": "teams:thread-1",
        }
    ]


@pytest.mark.asyncio
async def test_enqueue_passes_attachment_summary_to_runtime() -> None:
    runtime = FakeRuntime()
    bridge = BotBridge(runtime=runtime)
    message = make_message(text="")
    message = NormalizedBotMessage(
        **{**message.to_dict(), "attachments": [NormalizedAttachment(type="file", name="report.pdf", size=123)]}
    )

    result = await bridge.enqueue(make_provider(), message, {"appPassword": "secret"})

    assert result.to_dict() == {"status": "queued", "operation_id": "op-1"}
    assert runtime.created[0]["messages"] == [
        {"role": "user", "content": "Attachments:\n1. file name=report.pdf size=123"}
    ]


@pytest.mark.asyncio
async def test_enqueue_new_command_clears_thread_without_creating_operation() -> None:
    runtime = FakeRuntime()
    background = FakeBackgroundTasks()
    bridge = BotBridge(runtime=runtime)

    queued = await bridge.enqueue(make_provider(), make_message(text="hello"), {"appPassword": "secret"})
    result = await bridge.enqueue(
        make_provider(),
        make_message(text="/new"),
        {"appPassword": "secret"},
        background_tasks=background,  # type: ignore[arg-type]
    )

    assert queued.to_dict() == {"status": "queued", "operation_id": "op-1"}
    assert result.to_dict() == {"status": "handled", "reason": "new_conversation"}
    assert len(runtime.created) == 1
    assert len(background.tasks) == 1
    assert background.tasks[0][0] == bridge.send_platform_reply
    assert background.tasks[0][1][2] == "Started a new conversation."


@pytest.mark.asyncio
async def test_enqueue_stop_command_interrupts_active_operation() -> None:
    runtime = FakeRuntime()
    background = FakeBackgroundTasks()
    bridge = BotBridge(runtime=runtime)

    await bridge.enqueue(make_provider(), make_message(text="hello"), {"appPassword": "secret"})
    result = await bridge.enqueue(
        make_provider(),
        make_message(text="/stop"),
        {"appPassword": "secret"},
        background_tasks=background,  # type: ignore[arg-type]
    )

    assert result.to_dict() == {"status": "handled", "reason": "stop"}
    assert runtime.interrupted == ["op-1"]
    assert len(background.tasks) == 1
    assert background.tasks[0][1][2] == "Stopped the current response."


@pytest.mark.asyncio
async def test_enqueue_stop_command_without_active_operation_replies_clear_message() -> None:
    runtime = FakeRuntime()
    background = FakeBackgroundTasks()
    bridge = BotBridge(runtime=runtime)

    result = await bridge.enqueue(
        make_provider(),
        make_message(text="/stop"),
        {"appPassword": "secret"},
        background_tasks=background,  # type: ignore[arg-type]
    )

    assert result.to_dict() == {"status": "handled", "reason": "stop"}
    assert runtime.interrupted == []
    assert len(background.tasks) == 1
    assert background.tasks[0][1][2] == "There is no active response to stop."


@pytest.mark.asyncio
async def test_run_and_reply_sends_teams_reply() -> None:
    runtime = FakeRuntime()
    FakeTeamsClient.replies = []
    bridge = BotBridge(runtime=runtime, teams_client_factory=FakeTeamsClient)

    await bridge.run_and_reply("op-1", make_message(), {"appPassword": "secret"})

    assert runtime.ran == ["op-1"]
    assert FakeTeamsClient.replies == [
        {
            "activity": make_message().raw,
            "app_id": "app-1",
            "app_password": "secret",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_sends_discord_reply() -> None:
    runtime = FakeRuntime()
    FakeDiscordClient.replies = []
    bridge = BotBridge(runtime=runtime, discord_client_factory=FakeDiscordClient)

    await bridge.run_and_reply("op-1", make_message("discord"), {"botToken": "bot-token"})

    assert runtime.ran == ["op-1"]
    assert FakeDiscordClient.replies == [
        {
            "activity": make_message("discord").raw,
            "bot_token": "bot-token",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_sends_telegram_reply() -> None:
    runtime = FakeRuntime()
    FakeTelegramClient.replies = []
    bridge = BotBridge(runtime=runtime, telegram_client_factory=FakeTelegramClient)

    await bridge.run_and_reply("op-1", make_message("telegram"), {"botToken": "bot-token"})

    assert runtime.ran == ["op-1"]
    assert FakeTelegramClient.replies == [
        {
            "activity": make_message("telegram").raw,
            "bot_token": "bot-token",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_sends_line_reply() -> None:
    runtime = FakeRuntime()
    FakeLineClient.replies = []
    bridge = BotBridge(runtime=runtime, line_client_factory=FakeLineClient)

    await bridge.run_and_reply("op-1", make_message("line"), {"channelAccessToken": "access-token"})

    assert runtime.ran == ["op-1"]
    assert FakeLineClient.replies == [
        {
            "activity": make_message("line").raw,
            "channel_access_token": "access-token",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_sends_slack_reply() -> None:
    runtime = FakeRuntime()
    FakeSlackClient.replies = []
    bridge = BotBridge(runtime=runtime, slack_client_factory=FakeSlackClient)

    await bridge.run_and_reply("op-1", make_message("slack"), {"botToken": "xoxb-token"})

    assert runtime.ran == ["op-1"]
    assert FakeSlackClient.replies == [
        {
            "activity": make_message("slack").raw,
            "bot_token": "xoxb-token",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_sends_feishu_reply() -> None:
    runtime = FakeRuntime()
    FakeFeishuClient.replies = []
    bridge = BotBridge(runtime=runtime, feishu_client_factory=FakeFeishuClient)

    await bridge.run_and_reply("op-1", make_message("feishu"), {"appSecret": "app-secret"})

    assert runtime.ran == ["op-1"]
    assert FakeFeishuClient.replies == [
        {
            "activity": make_message("feishu").raw,
            "app_id": "app-1",
            "app_secret": "app-secret",
            "platform": "feishu",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_sends_qq_reply() -> None:
    runtime = FakeRuntime()
    FakeQQClient.replies = []
    bridge = BotBridge(runtime=runtime, qq_client_factory=FakeQQClient)

    await bridge.run_and_reply("op-1", make_message("qq"), {"appSecret": "app-secret"})

    assert runtime.ran == ["op-1"]
    assert FakeQQClient.replies == [
        {
            "activity": make_message("qq").raw,
            "app_id": "app-1",
            "app_secret": "app-secret",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_sends_wechat_reply() -> None:
    runtime = FakeRuntime()
    FakeWechatClient.replies = []
    bridge = BotBridge(runtime=runtime, wechat_client_factory=FakeWechatClient)

    await bridge.run_and_reply("op-1", make_message("wechat"), {"botToken": "bot-token"})

    assert runtime.ran == ["op-1"]
    assert FakeWechatClient.replies == [
        {
            "activity": make_message("wechat").raw,
            "bot_token": "bot-token",
            "text": "hello from agent",
        }
    ]


@pytest.mark.asyncio
async def test_run_and_reply_skips_non_teams_outbound() -> None:
    runtime = FakeRuntime()
    FakeTeamsClient.replies = []
    bridge = BotBridge(runtime=runtime, teams_client_factory=FakeTeamsClient)

    await bridge.run_and_reply("op-1", make_message("unknown"), {"appPassword": "secret"})

    assert runtime.ran == ["op-1"]
    assert FakeTeamsClient.replies == []
