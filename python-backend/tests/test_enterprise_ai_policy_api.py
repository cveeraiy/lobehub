from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status

from app.db import get_db
from app.dependencies import get_current_user_id, require_admin
from app.models.user import User
from app.routers import enterprise_ai_policies, user
from app.services.enterprise_ai_policy.service import get_enterprise_ai_policy_service


class _ScalarResult:
    def __init__(self, value: Any = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = False

    async def get(self, model: Any, item_id: str) -> Any:
        if model is User:
            return User(id=item_id, org_id="org-1")
        return None

    async def execute(self, statement: Any) -> _ScalarResult:
        return _ScalarResult(None)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def app() -> FastAPI:
    get_enterprise_ai_policy_service.cache_clear()

    test_app = FastAPI()
    test_app.include_router(enterprise_ai_policies.router)
    test_app.include_router(user.router)

    async def current_user() -> str:
        return "user-1"

    async def admin_user() -> str:
        return "admin-1"

    async def db_session():
        yield _FakeSession()

    test_app.dependency_overrides[get_current_user_id] = current_user
    test_app.dependency_overrides[require_admin] = admin_user
    test_app.dependency_overrides[get_db] = db_session

    yield test_app

    test_app.dependency_overrides.clear()
    get_enterprise_ai_policy_service.cache_clear()


@pytest.fixture
async def client(app: FastAPI):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.asyncio
async def test_admin_policy_crud_and_effective_policy(client: httpx.AsyncClient) -> None:
    create = await client.post(
        "/api/admin/enterprise-ai-policies",
        json={
            "name": "Engineering defaults",
            "priority": 10,
            "enabled": True,
            "managed_settings": {"provider": True, "model": True, "skills": True},
            "provider_config": {"openai": {"enabled": True}},
            "model_config": {"default_agent": {"model": "gpt-4o", "provider": "openai"}},
            "skill_config": {"allow": ["web-search"]},
            "restrictions": {"deny_models": ["gpt-3.5-turbo"]},
            "targets": [{"target_type": "user", "target_id": "user-1"}],
        },
    )

    assert create.status_code == 201
    created = create.json()
    assert created["id"].startswith("policy_")
    assert created["model_config"]["default_agent"]["model"] == "gpt-4o"

    list_response = await client.get("/api/admin/enterprise-ai-policies")
    assert list_response.status_code == 200
    assert [policy["id"] for policy in list_response.json()] == [created["id"]]

    effective_response = await client.get("/api/enterprise-ai-policy/effective")
    assert effective_response.status_code == 200
    effective = effective_response.json()
    assert effective["managed_settings"] == {"provider": True, "model": True, "skills": True}
    assert effective["default_agent"] == {"model": "gpt-4o", "provider": "openai"}
    assert effective["source_policy_ids"] == [created["id"]]

    delete_response = await client.delete(f"/api/admin/enterprise-ai-policies/{created['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_admin_group_targets_are_selectable(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ENTERPRISE_AI_USER_GROUPS_JSON",
        '{"user-1": ["engineering"], "user-2": ["finance", "engineering"]}',
    )
    get_enterprise_ai_policy_service.cache_clear()

    response = await client.get("/api/admin/enterprise-ai-policies/group-targets")

    assert response.status_code == 200
    assert response.json() == [{"id": "engineering"}, {"id": "finance"}]


@pytest.mark.asyncio
async def test_user_settings_update_rejects_managed_paths(client: httpx.AsyncClient) -> None:
    create = await client.post(
        "/api/admin/enterprise-ai-policies",
        json={
            "name": "Managed user",
            "managed_settings": {"provider": True, "model": True, "skills": True},
            "targets": [{"target_type": "user", "target_id": "user-1"}],
        },
    )
    assert create.status_code == 201

    response = await client.put(
        "/api/user/settings",
        json={
            "key_vaults": {"openai": {"apiKey": "secret"}},
            "default_agent": {"model": "gpt-4o", "provider": "openai"},
            "tool": {"builtin": {"web-search": True}},
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "ENTERPRISE_SETTING_MANAGED",
        "paths": ["key_vaults", "default_agent", "tool"],
    }


@pytest.mark.asyncio
async def test_non_admin_cannot_mutate_policies(app: FastAPI) -> None:
    async def forbidden_admin() -> str:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    app.dependency_overrides[require_admin] = forbidden_admin

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/admin/enterprise-ai-policies",
            json={"name": "Blocked"},
        )

    assert response.status_code == 403
