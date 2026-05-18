import pytest

from app.routers import market_discover


class DummyRequest:
    cookies: dict[str, str] = {}
    headers: dict[str, str] = {}


def test_market_discover_routes_are_registered():
    paths = {route.path for route in market_discover.router.routes}

    assert "/api/discover/skill/list" in paths
    assert "/api/discover/mcp/list" in paths
    assert "/api/discover/register-client" in paths


@pytest.mark.asyncio
async def test_skill_list_uses_market_v1_path(monkeypatch):
    calls = []

    async def fake_proxy_get(path, params=None, headers=None):
        calls.append((path, params, headers))
        return {"items": [], "totalCount": 0}

    monkeypatch.setattr(market_discover, "_proxy_get", fake_proxy_get)

    await market_discover.get_skill_list(request=DummyRequest(), _user_id="user-1")

    assert calls[0][0] == "/api/v1/skills"


@pytest.mark.asyncio
async def test_mcp_list_uses_market_plugins_v1_path(monkeypatch):
    calls = []

    async def fake_proxy_get(path, params=None, headers=None):
        calls.append((path, params, headers))
        return {"items": [], "totalCount": 0}

    monkeypatch.setattr(market_discover, "_proxy_get", fake_proxy_get)

    await market_discover.get_mcp_list(request=DummyRequest(), _user_id="user-1")

    assert calls[0][0] == "/api/v1/plugins"
