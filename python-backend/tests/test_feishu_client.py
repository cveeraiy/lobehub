from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.feishu.client import FeishuClient


@pytest.mark.asyncio
async def test_feishu_client_replies_to_message() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal":
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "tenant-token", "expire": 7200})
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "reply-msg"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await FeishuClient("cli-app", "app-secret").reply_message("om-msg", "hello", client=client)

    assert result == {"code": 0, "data": {"message_id": "reply-msg"}}
    assert requests[0].read() == b'{"app_id":"cli-app","app_secret":"app-secret"}'
    assert str(requests[1].url) == "https://open.feishu.cn/open-apis/im/v1/messages/om-msg/reply"
    assert requests[1].headers["authorization"] == "Bearer tenant-token"
    assert requests[1].read() == b'{"content":"{\\"text\\": \\"hello\\"}","msg_type":"text"}'


@pytest.mark.asyncio
async def test_lark_client_uses_lark_base_url() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal":
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "tenant-token", "expire": 7200})
        return httpx.Response(200, json={"code": 0, "data": {"message_id": "reply-msg"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await FeishuClient("cli-app", "app-secret", "lark").reply_message("om-msg", "hello", client=client)

    assert str(requests[1].url) == "https://open.larksuite.com/open-apis/im/v1/messages/om-msg/reply"


@pytest.mark.asyncio
async def test_feishu_client_send_reply_uses_event_message_id(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    async def fake_reply_message(
        self: FeishuClient,
        message_id: str,
        text: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, object]:
        calls.append({"message_id": message_id, "text": text})
        return {"code": 0}

    monkeypatch.setattr(FeishuClient, "reply_message", fake_reply_message)

    result = await FeishuClient("cli-app", "secret").send_reply({"message_id": "om-msg"}, "hello")

    assert result == {"code": 0}
    assert calls == [{"message_id": "om-msg", "text": "hello"}]
