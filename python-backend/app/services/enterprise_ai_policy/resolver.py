"""Resolve effective enterprise AI policy for one user."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .types import EffectiveEnterpriseAiPolicy, EnterpriseAiPolicy, UserPolicyContext


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = _deep_merge(current, value)
        else:
            result[key] = deepcopy(value)
    return result


def _target_rank(policy: EnterpriseAiPolicy, context: UserPolicyContext) -> int | None:
    if not policy.targets:
        return 0

    best: int | None = None
    for target in policy.targets:
        rank: int | None = None
        if target.target_type == "global":
            rank = 0
        elif target.target_type == "organization" and target.target_id in context.organization_ids:
            rank = 1
        elif target.target_type == "group" and target.target_id in context.group_ids:
            rank = 2
        elif target.target_type == "user" and target.target_id == context.user_id:
            rank = 3

        if rank is not None:
            best = rank if best is None else max(best, rank)

    return best


class EnterpriseAiPolicyResolver:
    def resolve(
        self,
        policies: list[EnterpriseAiPolicy],
        context: UserPolicyContext,
    ) -> EffectiveEnterpriseAiPolicy:
        applicable: list[tuple[int, EnterpriseAiPolicy]] = []

        for policy in policies:
            if not policy.enabled:
                continue

            rank = _target_rank(policy, context)
            if rank is not None:
                applicable.append((rank, policy))

        applicable.sort(key=lambda item: (item[0], item[1].priority, item[1].updated_at))

        effective = EffectiveEnterpriseAiPolicy()
        for _, policy in applicable:
            effective.managed_settings.provider = (
                effective.managed_settings.provider or policy.managed_settings.provider
            )
            effective.managed_settings.model = (
                effective.managed_settings.model or policy.managed_settings.model
            )
            effective.managed_settings.skills = (
                effective.managed_settings.skills or policy.managed_settings.skills
            )
            effective.providers = _deep_merge(effective.providers, policy.provider_config)
            effective.models = _deep_merge(effective.models, policy.ai_model_config)
            effective.skills = _deep_merge(effective.skills, policy.skill_config)
            effective.restrictions = _deep_merge(effective.restrictions, policy.restrictions)

            default_agent = policy.ai_model_config.get("default_agent")
            if isinstance(default_agent, dict):
                effective.default_agent = _deep_merge(effective.default_agent, default_agent)

            effective.source_policy_ids.append(policy.id)

        return effective
