from __future__ import annotations

import pytest

from app.routers.user import _blocked_managed_setting_paths
from app.services.enterprise_ai_policy.resolver import EnterpriseAiPolicyResolver
from app.services.enterprise_ai_policy.types import (
    EnterpriseAiPolicy,
    EnterpriseAiPolicyTarget,
    ManagedSettings,
    UserPolicyContext,
)


def _policy(
    policy_id: str,
    target_type: str,
    target_id: str,
    *,
    priority: int = 0,
    provider_config: dict | None = None,
    model_config: dict | None = None,
    skill_config: dict | None = None,
    managed_settings: ManagedSettings | None = None,
) -> EnterpriseAiPolicy:
    return EnterpriseAiPolicy(
        id=policy_id,
        name=policy_id,
        priority=priority,
        targets=[EnterpriseAiPolicyTarget(target_type=target_type, target_id=target_id)],
        provider_config=provider_config or {},
        model_config=model_config or {},
        skill_config=skill_config or {},
        managed_settings=managed_settings or ManagedSettings(),
    )


def test_resolver_applies_user_policy_over_group_and_org() -> None:
    resolver = EnterpriseAiPolicyResolver()
    context = UserPolicyContext(
        user_id="user-1",
        organization_ids=["org-1"],
        group_ids=["group-1"],
    )

    effective = resolver.resolve(
        [
            _policy(
                "org-policy",
                "organization",
                "org-1",
                model_config={"default_agent": {"model": "org-model", "provider": "openai"}},
            ),
            _policy(
                "group-policy",
                "group",
                "group-1",
                model_config={"default_agent": {"model": "group-model"}},
            ),
            _policy(
                "user-policy",
                "user",
                "user-1",
                model_config={"default_agent": {"model": "user-model"}},
            ),
        ],
        context,
    )

    assert effective.default_agent == {"model": "user-model", "provider": "openai"}
    assert effective.source_policy_ids == ["org-policy", "group-policy", "user-policy"]


def test_resolver_ignores_disabled_policy() -> None:
    resolver = EnterpriseAiPolicyResolver()
    context = UserPolicyContext(user_id="user-1")
    disabled = _policy(
        "disabled",
        "user",
        "user-1",
        model_config={"default_agent": {"model": "disabled-model"}},
    )
    disabled.enabled = False

    effective = resolver.resolve([disabled], context)

    assert effective.default_agent == {}
    assert effective.source_policy_ids == []


def test_resolver_uses_priority_within_same_target_level() -> None:
    resolver = EnterpriseAiPolicyResolver()
    context = UserPolicyContext(user_id="user-1", group_ids=["group-1"])

    effective = resolver.resolve(
        [
            _policy(
                "low-priority",
                "group",
                "group-1",
                priority=1,
                model_config={"default_agent": {"model": "low"}},
            ),
            _policy(
                "high-priority",
                "group",
                "group-1",
                priority=10,
                model_config={"default_agent": {"model": "high"}},
            ),
        ],
        context,
    )

    assert effective.default_agent == {"model": "high"}
    assert effective.source_policy_ids == ["low-priority", "high-priority"]


@pytest.mark.parametrize(
    ("managed_settings", "values", "expected"),
    [
        (ManagedSettings(provider=True), {"key_vaults": {}}, ["key_vaults"]),
        (ManagedSettings(provider=True), {"language_model": {}}, ["language_model"]),
        (ManagedSettings(model=True), {"default_agent": {}}, ["default_agent"]),
        (ManagedSettings(skills=True), {"tool": {}, "market": {}}, ["tool", "market"]),
        (ManagedSettings(), {"key_vaults": {}, "default_agent": {}, "tool": {}}, []),
    ],
)
def test_blocked_managed_setting_paths(
    managed_settings: ManagedSettings,
    values: dict,
    expected: list[str],
) -> None:
    assert _blocked_managed_setting_paths(values, managed_settings) == expected
