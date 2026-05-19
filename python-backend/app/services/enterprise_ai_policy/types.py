"""Types for schema-free enterprise AI governance policies."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TargetType = Literal["global", "organization", "group", "user"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ManagedSettings(BaseModel):
    provider: bool = False
    model: bool = False
    skills: bool = False


class EnterpriseAiPolicyTarget(BaseModel):
    target_type: TargetType
    target_id: str = "*"


class EnterpriseAiPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: Optional[str] = None
    organization_id: Optional[str] = None
    priority: int = 0
    enabled: bool = True
    managed_settings: ManagedSettings = Field(default_factory=ManagedSettings)
    provider_config: dict[str, Any] = Field(default_factory=dict)
    ai_model_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    skill_config: dict[str, Any] = Field(default_factory=dict)
    restrictions: dict[str, Any] = Field(default_factory=dict)
    targets: list[EnterpriseAiPolicyTarget] = Field(default_factory=list)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UserPolicyContext(BaseModel):
    user_id: str
    organization_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)


class EffectiveEnterpriseAiPolicy(BaseModel):
    managed_settings: ManagedSettings = Field(default_factory=ManagedSettings)
    providers: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)
    default_agent: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, Any] = Field(default_factory=dict)
    restrictions: dict[str, Any] = Field(default_factory=dict)
    source_policy_ids: list[str] = Field(default_factory=list)


class EnterpriseAiPolicyInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: Optional[str] = None
    organization_id: Optional[str] = None
    priority: int = 0
    enabled: bool = True
    managed_settings: ManagedSettings = Field(default_factory=ManagedSettings)
    provider_config: dict[str, Any] = Field(default_factory=dict)
    ai_model_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    skill_config: dict[str, Any] = Field(default_factory=dict)
    restrictions: dict[str, Any] = Field(default_factory=dict)
    targets: list[EnterpriseAiPolicyTarget] = Field(default_factory=list)


class PolicyTargetInput(BaseModel):
    target_type: TargetType
    target_id: str
