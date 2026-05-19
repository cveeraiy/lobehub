"""REST endpoints for schema-free enterprise AI governance policies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id, require_admin
from app.services.enterprise_ai_policy import get_enterprise_ai_policy_service
from app.services.enterprise_ai_policy.types import EnterpriseAiPolicyInput, PolicyTargetInput

router = APIRouter(tags=["Enterprise AI Policies"])


@router.get("/api/enterprise-ai-policy/effective")
async def get_effective_enterprise_ai_policy(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = get_enterprise_ai_policy_service()
    policy = await service.resolve_for_user(user_id, session)
    return policy.model_dump(mode="json")


@router.get("/api/admin/enterprise-ai-policies")
async def list_enterprise_ai_policies(
    admin_id: str = Depends(require_admin),
):
    service = get_enterprise_ai_policy_service()
    policies = await service.list_policies()
    return [policy.model_dump(mode="json", by_alias=True) for policy in policies]


@router.post("/api/admin/enterprise-ai-policies", status_code=status.HTTP_201_CREATED)
async def create_enterprise_ai_policy(
    body: EnterpriseAiPolicyInput,
    admin_id: str = Depends(require_admin),
):
    service = get_enterprise_ai_policy_service()
    policy = await service.create_policy(body, admin_id)
    return policy.model_dump(mode="json", by_alias=True)


@router.put("/api/admin/enterprise-ai-policies/{policy_id}")
async def update_enterprise_ai_policy(
    policy_id: str,
    body: EnterpriseAiPolicyInput,
    admin_id: str = Depends(require_admin),
):
    service = get_enterprise_ai_policy_service()
    policy = await service.update_policy(policy_id, body, admin_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    return policy.model_dump(mode="json", by_alias=True)


@router.delete("/api/admin/enterprise-ai-policies/{policy_id}")
async def delete_enterprise_ai_policy(
    policy_id: str,
    admin_id: str = Depends(require_admin),
):
    service = get_enterprise_ai_policy_service()
    await service.delete_policy(policy_id)
    return {"ok": True}


@router.post("/api/admin/enterprise-ai-policies/{policy_id}/targets")
async def assign_enterprise_ai_policy_target(
    policy_id: str,
    body: PolicyTargetInput,
    admin_id: str = Depends(require_admin),
):
    service = get_enterprise_ai_policy_service()
    policy = await service.assign_target(policy_id, body, admin_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    return policy.model_dump(mode="json", by_alias=True)


@router.delete("/api/admin/enterprise-ai-policies/{policy_id}/targets/{target_type}/{target_id}")
async def remove_enterprise_ai_policy_target(
    policy_id: str,
    target_type: str,
    target_id: str,
    admin_id: str = Depends(require_admin),
):
    service = get_enterprise_ai_policy_service()
    policy = await service.remove_target(policy_id, target_type, target_id, admin_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    return policy.model_dump(mode="json", by_alias=True)
