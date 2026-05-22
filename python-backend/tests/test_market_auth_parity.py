from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.dependencies import get_current_user_id
from app.routers import market


class FakeMarketClient:
    requests: list[dict[str, Any]] = []
    responses: list[httpx.Response] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> FakeMarketClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"method": "GET", "url": url, **kwargs})
        return self.responses.pop(0)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"method": "POST", "url": url, **kwargs})
        return self.responses.pop(0)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"method": "PUT", "url": url, **kwargs})
        return self.responses.pop(0)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(market.router)

    async def fake_user_id() -> str:
        return "user-1"

    async def fake_db():
        yield object()

    async def fake_market_access_headers(*args: Any, **kwargs: Any) -> dict[str, str]:
        return {"Authorization": "Bearer market-token"}

    FakeMarketClient.requests = []
    FakeMarketClient.responses = []
    app.dependency_overrides[get_current_user_id] = fake_user_id
    app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(market, "_market_access_headers", fake_market_access_headers)
    monkeypatch.setattr(market.httpx, "AsyncClient", FakeMarketClient)
    return TestClient(app)


def test_refresh_market_oidc_token_returns_camel_case(client: TestClient) -> None:
    FakeMarketClient.responses = [
        httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "expires_in": 3600,
                "refresh_token": "refresh-token",
                "scope": "openid profile email",
                "token_type": "Bearer",
            },
        )
    ]

    response = client.post(
        "/api/market/oidc/token",
        data={
            "client_id": "lobechat-com",
            "grant_type": "refresh_token",
            "refresh_token": "old-refresh-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "accessToken": "access-token",
        "expiresIn": 3600,
        "idToken": None,
        "refreshToken": "refresh-token",
        "scope": "openid profile email",
        "tokenType": "Bearer",
    }
    request = FakeMarketClient.requests[0]
    assert request["url"] == "https://market.lobehub.com/oauth/token"
    assert request["data"]["grant_type"] == "refresh_token"


def test_get_market_user_by_username_normalizes_profile(client: TestClient) -> None:
    FakeMarketClient.responses = [
        httpx.Response(
            200,
            json={
                "user": {
                    "avatarUrl": "avatar.png",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "displayName": "Market User",
                    "id": 123,
                    "meta": {
                        "bannerUrl": "banner.png",
                        "description": "About",
                        "socialLinks": {"github": "octo"},
                    },
                    "namespace": "market-user",
                    "type": "user",
                    "userName": "market-user",
                }
            },
        )
    ]

    response = client.get("/api/market/user/market-user")

    assert response.status_code == 200
    assert response.json() == {
        "avatarUrl": "avatar.png",
        "bannerUrl": "banner.png",
        "createdAt": "2026-01-01T00:00:00Z",
        "description": "About",
        "displayName": "Market User",
        "id": 123,
        "namespace": "market-user",
        "socialLinks": {"github": "octo"},
        "type": "user",
        "userName": "market-user",
    }


def test_scan_claimable_resources_unwraps_data(client: TestClient) -> None:
    FakeMarketClient.responses = [
        httpx.Response(
            200,
            json={
                "data": {
                    "plugins": [{"id": 1, "identifier": "plugin-a", "type": "plugin"}],
                    "skills": [{"id": 2, "identifier": "skill-a", "type": "skill"}],
                }
            },
        )
    ]

    response = client.get("/api/market/social-profile/claimable-resources")

    assert response.status_code == 200
    assert response.json() == {
        "plugins": [{"id": 1, "identifier": "plugin-a", "type": "plugin"}],
        "skills": [{"id": 2, "identifier": "skill-a", "type": "skill"}],
    }


def test_claim_resources_posts_each_asset(client: TestClient) -> None:
    FakeMarketClient.responses = [
        httpx.Response(200, json={}),
        httpx.Response(200, json={}),
    ]

    response = client.post(
        "/api/market/social-profile/claim-resources",
        json={"pluginIds": ["20"], "skillIds": ["10"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "claimed": [
            {"assetId": 10, "assetType": "skill"},
            {"assetId": 20, "assetType": "plugin"},
        ],
        "errors": None,
        "success": True,
    }
    assert [request["json"] for request in FakeMarketClient.requests] == [
        {"assetId": 10, "assetType": "skill"},
        {"assetId": 20, "assetType": "plugin"},
    ]


def test_update_market_user_profile_maps_taken_username_to_conflict(client: TestClient) -> None:
    FakeMarketClient.responses = [httpx.Response(400, json={"error": "Username already taken"})]

    response = client.put(
        "/api/market/user/me",
        json={"displayName": "Market User", "userName": "market-user"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username is already taken"
