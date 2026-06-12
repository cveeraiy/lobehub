"""Schema-free policy repository backed by process memory and optional env JSON."""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy

from .types import EnterpriseAiPolicy

logger = logging.getLogger(__name__)

POLICIES_ENV = "ENTERPRISE_AI_POLICIES_JSON"


class InMemoryEnterpriseAiPolicyRepository:
    def __init__(self, policies: list[EnterpriseAiPolicy] | None = None) -> None:
        self._policies: dict[str, EnterpriseAiPolicy] = {policy.id: policy for policy in policies or []}

    async def list_policies(self) -> list[EnterpriseAiPolicy]:
        return [deepcopy(policy) for policy in self._policies.values()]

    async def upsert_policy(self, policy: EnterpriseAiPolicy) -> EnterpriseAiPolicy:
        self._policies[policy.id] = deepcopy(policy)
        return deepcopy(policy)

    async def delete_policy(self, policy_id: str) -> None:
        self._policies.pop(policy_id, None)


def load_env_policies() -> list[EnterpriseAiPolicy]:
    raw = os.environ.get(POLICIES_ENV)
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid %s payload", POLICIES_ENV)
        return []

    if not isinstance(payload, list):
        logger.warning("Ignoring %s because it must be a JSON array", POLICIES_ENV)
        return []

    policies: list[EnterpriseAiPolicy] = []
    for item in payload:
        try:
            policies.append(EnterpriseAiPolicy.model_validate(item))
        except Exception as exc:
            logger.warning("Ignoring invalid enterprise AI policy: %s", exc)

    return policies
