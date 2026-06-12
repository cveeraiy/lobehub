from __future__ import annotations

import httpx
import pytest

from app.services.bot.platforms.teams.client import (
    BotFrameworkAuthError,
    TeamsConnectorClient,
    validate_bot_framework_authorization,
)


@pytest.mark.asyncio
async def test_validate_bot_framework_authorization_requires_bearer_token() -> None:
    with pytest.raises(BotFrameworkAuthError, match="Missing Bot Framework bearer token"):
        await validate_bot_framework_authorization(None, app_id="app-id", service_url="https://service")


@pytest.mark.asyncio
async def test_validate_bot_framework_authorization_rejects_invalid_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://login.botframework.com/v1/.well-known/openidconfiguration":
            return httpx.Response(200, json={"jwks_uri": "https://keys.example/jwks"})
        return httpx.Response(200, json={"keys": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BotFrameworkAuthError, match="Invalid Bot Framework bearer token"):
            await validate_bot_framework_authorization(
                "Bearer invalid.jwt.token",
                app_id="app-id",
                service_url="https://service",
                client=client,
            )


@pytest.mark.asyncio
async def test_teams_connector_client_sends_reply_to_activity_endpoint() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token":
            return httpx.Response(200, json={"access_token": "access-token", "expires_in": 3600})
        if str(request.url) == "https://smba.trafficmanager.net/teams/v3/conversations/conv-1/activities/activity-1":
            return httpx.Response(200, json={"id": "reply-1"})
        return httpx.Response(404)

    activity = {
        "id": "activity-1",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "conversation": {"id": "conv-1"},
        "from": {"id": "user-1"},
        "recipient": {"id": "bot-1"},
    }

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TeamsConnectorClient("app-id", "app-password").send_reply(activity, "hello back", client)

    assert result == {"id": "reply-1"}
    token_request = requests[0]
    assert token_request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert b"client_id=app-id" in token_request.content
    assert b"scope=https%3A%2F%2Fapi.botframework.com%2F.default" in token_request.content

    reply_request = requests[1]
    assert reply_request.headers["authorization"] == "Bearer access-token"
    assert reply_request.url.path == "/teams/v3/conversations/conv-1/activities/activity-1"
    assert reply_request.read() == (
        b'{"type":"message","text":"hello back","from":{"id":"bot-1"},'
        b'"recipient":{"id":"user-1"},"replyToId":"activity-1"}'
    )
