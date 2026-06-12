from types import SimpleNamespace

import pytest

from app.routers import business, device, generation_workers, oauth_device_flow
from app.routers.market import (
    CredBody,
    _cred_from_body,
    _decode_secret,
    _public_cred,
)
from app.services.agent_signal.orchestrator import SignalOrchestrator, _register_default_handlers
from app.services.generation_worker import _extract_image_urls


def _paths(router):
    return {(route.path, ",".join(sorted(route.methods or []))) for route in router.router.routes}


def test_new_parity_routers_are_registered():
    assert ("/api/generation-workers/tasks/{task_id}/run", "POST") in _paths(generation_workers)
    assert ("/api/generation-workers/run-pending", "POST") in _paths(generation_workers)
    assert ("/api/oauth-device-flow/auth-status", "GET") in _paths(oauth_device_flow)
    assert ("/api/oauth-device-flow/initiate-device-code", "POST") in _paths(oauth_device_flow)
    assert ("/api/oauth-device-flow/poll-auth-status", "POST") in _paths(oauth_device_flow)
    assert ("/api/oauth-device-flow/revoke-auth", "POST") in _paths(oauth_device_flow)
    assert ("/api/device/status", "GET") in _paths(device)
    assert ("/api/device/proxy/{path:path}", "DELETE,GET,PATCH,POST,PUT") in _paths(device)
    assert ("/api/subscription", "GET") in _paths(business)
    assert ("/api/top-up", "GET") in _paths(business)
    assert ("/api/spend", "GET") in _paths(business)
    assert ("/api/business/subscription", "GET") in _paths(business)
    assert ("/api/business/top-up", "GET") in _paths(business)
    assert ("/api/business/spend", "GET") in _paths(business)


def test_market_credential_secret_is_not_returned_by_default():
    cred = _cred_from_body(CredBody(key="api", name="API key", values={"token": "secret"}), 1, "kv")

    public = _public_cred(cred)

    assert public["id"] == 1
    assert public["hasSecret"] is True
    assert "secret" not in public
    assert "plaintext" not in public
    assert _decode_secret(cred["secret"]) == {"token": "secret"}


def test_market_credential_can_return_plaintext_when_requested():
    cred = _cred_from_body(CredBody(key="api", values={"token": "secret"}), 1, "kv")

    public = _public_cred(cred, decrypt=True)

    assert public["plaintext"] == {"token": "secret"}


def test_generation_worker_extracts_urls_from_dict_and_objects():
    response = {
        "data": [
            {"url": "https://example.com/a.png"},
            SimpleNamespace(url="https://example.com/b.png"),
        ]
    }

    assert _extract_image_urls(response) == ["https://example.com/a.png", "https://example.com/b.png"]


def test_oauth_error_status_mapping():
    assert oauth_device_flow._oauth_error_status("authorization_pending") == "pending"
    assert oauth_device_flow._oauth_error_status("slow_down") == "slow_down"
    assert oauth_device_flow._oauth_error_status("expired_token") == "expired"
    assert oauth_device_flow._oauth_error_status("access_denied") == "denied"


def test_oauth_request_bodies_accept_camel_case():
    body = oauth_device_flow.PollBody(providerId="githubcopilot", deviceCode="abc")

    assert body.provider_id == "githubcopilot"
    assert body.device_code == "abc"


@pytest.mark.asyncio
async def test_oauth_auth_status_reads_legacy_trpc_token_keys(monkeypatch):
    provider = SimpleNamespace(
        key_vaults=oauth_device_flow._encode_key_vaults(
            {
                "githubAvatarUrl": "https://example.test/avatar.png",
                "githubUsername": "octo",
                "oauthAccessToken": "a",
                "oauthTokenExpiresAt": "123",
            }
        )
    )

    async def fake_provider(_session, _user_id, _provider_id):
        return provider

    monkeypatch.setattr(oauth_device_flow, "_provider", fake_provider)
    result = await oauth_device_flow.get_auth_status(
        provider_id="githubcopilot",
        user_id="user_1",
        session=object(),
    )

    assert result == {
        "avatarUrl": "https://example.test/avatar.png",
        "expiresAt": "123",
        "isAuthenticated": True,
        "username": "octo",
    }


@pytest.mark.asyncio
async def test_oauth_revoke_clears_provider_tokens(monkeypatch):
    provider = SimpleNamespace(
        key_vaults=oauth_device_flow._encode_key_vaults(
            {
                "bearerToken": "b",
                "githubAvatarUrl": "https://example.test/avatar.png",
                "githubUserInfo": {"username": "u"},
                "githubUsername": "u",
                "oauthAccessToken": "a",
                "oauthTokenExpiresAt": "123",
                "other": "kept",
            }
        ),
        updated_at=None,
    )

    class FakeSession:
        def add(self, value):
            self.added = value

        async def flush(self):
            pass

    async def fake_provider(_session, _user_id, _provider_id):
        return provider

    monkeypatch.setattr(oauth_device_flow, "_provider", fake_provider)
    result = await oauth_device_flow.revoke_auth(
        oauth_device_flow.ProviderBody(provider_id="githubcopilot"),
        user_id="user_1",
        session=FakeSession(),
    )

    assert result == {"success": True}
    decoded = oauth_device_flow._decode_key_vaults(provider)
    assert "oauthAccessToken" not in decoded
    assert "bearerToken" not in decoded
    assert "githubAvatarUrl" not in decoded
    assert "githubUsername" not in decoded
    assert "oauthTokenExpiresAt" not in decoded
    assert decoded["other"] == "kept"


def test_signal_orchestrator_registers_skill_maintainer_handlers():
    orchestrator = SignalOrchestrator()
    _register_default_handlers(orchestrator)

    assert "skillMaintainer" in orchestrator._handlers
    assert "skill_maintainer" in orchestrator._handlers
