"""Shared fixtures for e2e tests.

Authenticates via Keycloak Resource Owner Password Grant to get a real
JWT Bearer token.  All API calls go through normal OIDC auth.

Environment variables:
    E2E_PYTHON_URL              Python backend URL (default: http://localhost:8000)
    E2E_KC_URL                  Keycloak base URL (default: http://localhost:8080)
    E2E_KC_REALM                Keycloak realm (default: lobehub)
    E2E_KC_CLIENT_ID            OIDC client ID (default: lobehub-app)
    E2E_KC_CLIENT_SECRET        OIDC client secret (default: lobehub-dev-secret)
    E2E_KC_USERNAME             Keycloak test user (default: chandra)
    E2E_KC_PASSWORD             Keycloak test user password (default: test123)
"""

from __future__ import annotations

import os

import httpx
import pytest
import pytest_asyncio


# ── Config ──────────────────────────────────────────────────────────

PYTHON_URL = os.environ.get("E2E_PYTHON_URL", "http://localhost:8000")

KC_URL = os.environ.get("E2E_KC_URL", "http://localhost:8080")
KC_REALM = os.environ.get("E2E_KC_REALM", "lobehub")
KC_CLIENT_ID = os.environ.get("E2E_KC_CLIENT_ID", "lobehub-app")
KC_CLIENT_SECRET = os.environ.get("E2E_KC_CLIENT_SECRET", "lobehub-dev-secret")
KC_USERNAME = os.environ.get("E2E_KC_USERNAME", "chandra")
KC_PASSWORD = os.environ.get("E2E_KC_PASSWORD", "test123")

# Second test user for cross-user isolation & sharing tests
KC_USERNAME_B = os.environ.get("E2E_KC_USERNAME_B", "testuser_b")
KC_PASSWORD_B = os.environ.get("E2E_KC_PASSWORD_B", "test123")

KC_TOKEN_URL = f"{KC_URL}/realms/{KC_REALM}/protocol/openid-connect/token"


# ── Markers ──────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e: end-to-end test against running backend")


# ── Token helper ─────────────────────────────────────────────────────

def _get_keycloak_token(username: str = KC_USERNAME, password: str = KC_PASSWORD) -> dict:
    """Obtain a Keycloak access token via Resource Owner Password Grant (sync)."""
    resp = httpx.post(
        KC_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": KC_CLIENT_ID,
            "client_secret": KC_CLIENT_SECRET,
            "username": username,
            "password": password,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    return PYTHON_URL


@pytest.fixture(scope="session")
def access_token() -> str:
    """A valid Keycloak JWT for the test user."""
    token_data = _get_keycloak_token()
    return token_data["access_token"]


@pytest.fixture(scope="session")
def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="session")
def user_id(access_token: str) -> str:
    """Extract the Keycloak user ID (sub claim) from the JWT."""
    import base64, json
    payload = access_token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    claims = json.loads(base64.b64decode(payload))
    return claims["sub"]


@pytest_asyncio.fixture
async def client(base_url: str, auth_headers: dict[str, str]):
    """Async HTTP client with Keycloak Bearer auth pre-configured."""
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            **auth_headers,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as c:
        yield c


@pytest_asyncio.fixture
async def unauthed_client(base_url: str):
    """Async HTTP client with no auth headers."""
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    ) as c:
        yield c


# ── Second user (User B) fixtures ──────────────────────────────────

@pytest.fixture(scope="session")
def access_token_b() -> str:
    """A valid Keycloak JWT for the second test user."""
    token_data = _get_keycloak_token(KC_USERNAME_B, KC_PASSWORD_B)
    return token_data["access_token"]


@pytest.fixture(scope="session")
def auth_headers_b(access_token_b: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token_b}"}


@pytest.fixture(scope="session")
def user_id_b(access_token_b: str) -> str:
    """Extract the Keycloak user ID (sub claim) for User B."""
    import base64, json
    payload = access_token_b.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    claims = json.loads(base64.b64decode(payload))
    return claims["sub"]


@pytest_asyncio.fixture
async def client_b(base_url: str, auth_headers_b: dict[str, str]):
    """Async HTTP client authenticated as User B."""
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            **auth_headers_b,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as c:
        yield c


# ── Shared state across test modules ────────────────────────────────
# Stores IDs created by earlier tests so later tests can reference them.


class SharedState:
    """Simple namespace for sharing IDs between ordered test modules."""

    session_id: str | None = None
    session_group_id: str | None = None
    agent_id: str | None = None
    agent_group_id: str | None = None
    topic_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    skill_id: str | None = None
    plugin_identifier: str | None = None
    task_id: str | None = None
    brief_id: str | None = None
    cron_job_id: str | None = None
    memory_id: str | None = None
    identity_id: str | None = None
    preference_id: str | None = None
    api_key_id: str | None = None
    share_id: str | None = None
    # Skill sharing
    shared_skill_id: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    notification_id: str | None = None
    knowledge_base_id: str | None = None
    document_id: str | None = None
    benchmark_id: str | None = None
    dataset_id: str | None = None
    eval_run_id: str | None = None


@pytest.fixture(scope="session")
def state() -> SharedState:
    return SharedState()
