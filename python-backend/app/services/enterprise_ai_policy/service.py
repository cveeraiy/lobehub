"""Enterprise AI governance service with schema-free persistence."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .repository import EnterpriseAiPolicyRepository
from .resolver import EnterpriseAiPolicyResolver
from .static_repository import InMemoryEnterpriseAiPolicyRepository, load_env_policies
from .types import (
    EffectiveEnterpriseAiPolicy,
    EnterpriseAiPolicy,
    EnterpriseAiPolicyInput,
    EnterpriseAiPolicyTarget,
    PolicyTargetInput,
    UserPolicyContext,
    utcnow,
)

USER_GROUPS_ENV = "ENTERPRISE_AI_USER_GROUPS_JSON"


class EnterpriseAiPolicyService:
    def __init__(
        self,
        repository: EnterpriseAiPolicyRepository,
        resolver: EnterpriseAiPolicyResolver | None = None,
    ) -> None:
        self._repository = repository
        self._resolver = resolver or EnterpriseAiPolicyResolver()

    async def list_policies(self) -> list[EnterpriseAiPolicy]:
        return await self._repository.list_policies()

    async def list_group_ids(self) -> list[str]:
        groups = set(_configured_group_ids())
        policies = await self._repository.list_policies()
        for policy in policies:
            for target in policy.targets:
                if target.target_type == "group" and target.target_id:
                    groups.add(target.target_id)
        return sorted(groups)

    async def create_policy(self, body: EnterpriseAiPolicyInput, admin_user_id: str) -> EnterpriseAiPolicy:
        now = utcnow()
        policy = EnterpriseAiPolicy(
            id=f"policy_{uuid4().hex}",
            created_at=now,
            created_by=admin_user_id,
            updated_at=now,
            updated_by=admin_user_id,
            **body.model_dump(by_alias=True),
        )
        return await self._repository.upsert_policy(policy)

    async def update_policy(
        self,
        policy_id: str,
        body: EnterpriseAiPolicyInput,
        admin_user_id: str,
    ) -> EnterpriseAiPolicy | None:
        policies = await self._repository.list_policies()
        existing = next((policy for policy in policies if policy.id == policy_id), None)
        if existing is None:
            return None

        updated = EnterpriseAiPolicy(
            id=policy_id,
            created_at=existing.created_at,
            created_by=existing.created_by,
            updated_at=utcnow(),
            updated_by=admin_user_id,
            **body.model_dump(by_alias=True),
        )
        return await self._repository.upsert_policy(updated)

    async def delete_policy(self, policy_id: str) -> None:
        await self._repository.delete_policy(policy_id)

    async def assign_target(
        self,
        policy_id: str,
        target: PolicyTargetInput,
        admin_user_id: str,
    ) -> EnterpriseAiPolicy | None:
        policies = await self._repository.list_policies()
        existing = next((policy for policy in policies if policy.id == policy_id), None)
        if existing is None:
            return None

        next_target = EnterpriseAiPolicyTarget(**target.model_dump())
        targets = [
            current
            for current in existing.targets
            if not (
                current.target_type == next_target.target_type
                and current.target_id == next_target.target_id
            )
        ]
        targets.append(next_target)
        existing.targets = targets
        existing.updated_at = utcnow()
        existing.updated_by = admin_user_id
        return await self._repository.upsert_policy(existing)

    async def remove_target(
        self,
        policy_id: str,
        target_type: str,
        target_id: str,
        admin_user_id: str,
    ) -> EnterpriseAiPolicy | None:
        policies = await self._repository.list_policies()
        existing = next((policy for policy in policies if policy.id == policy_id), None)
        if existing is None:
            return None

        existing.targets = [
            target
            for target in existing.targets
            if not (target.target_type == target_type and target.target_id == target_id)
        ]
        existing.updated_at = utcnow()
        existing.updated_by = admin_user_id
        return await self._repository.upsert_policy(existing)

    async def resolve_for_user(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> EffectiveEnterpriseAiPolicy:
        user = await session.get(User, user_id)
        context = UserPolicyContext(
            user_id=user_id,
            organization_ids=_organization_ids(user),
            group_ids=_group_ids_for_user(user_id),
        )
        policies = await self._repository.list_policies()
        return self._resolver.resolve(policies, context)


def _organization_ids(user: User | None) -> list[str]:
    if user is None:
        return []

    ids: list[str] = []
    for value in (getattr(user, "org_id", None), getattr(user, "org_slug", None)):
        if value and value not in ids:
            ids.append(value)
    return ids


def _group_ids_for_user(user_id: str) -> list[str]:
    mapping = _user_group_mapping()
    groups = mapping.get(user_id)
    if not isinstance(groups, list):
        return []

    return [group for group in groups if isinstance(group, str)]


def _configured_group_ids() -> list[str]:
    groups: set[str] = set()
    for values in _user_group_mapping().values():
        if not isinstance(values, list):
            continue
        groups.update(group for group in values if isinstance(group, str))
    return sorted(groups)


def _user_group_mapping() -> dict[str, object]:
    raw = os.environ.get(USER_GROUPS_ENV)
    if not raw:
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


@lru_cache(maxsize=1)
def get_enterprise_ai_policy_service() -> EnterpriseAiPolicyService:
    repository = InMemoryEnterpriseAiPolicyRepository(load_env_policies())
    return EnterpriseAiPolicyService(repository)
