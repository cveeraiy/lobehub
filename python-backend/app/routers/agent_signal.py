"""Agent Signal Router — REST endpoints for the signal orchestrator.

Exposes:
- POST /api/agent-signal/emit        — Emit a signal
- GET  /api/agent-signal/policies     — List registered policies
- POST /api/agent-signal/policies     — Register a policy
- DELETE /api/agent-signal/policies/{id} — Unregister a policy
- POST /api/agent-signal/cleanup      — Cleanup dedup cache
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.agent_signal.orchestrator import get_orchestrator
from app.services.agent_signal.types import Signal, SignalAction, SignalPolicy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-signal", tags=["agent-signal"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class EmitSignalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: Optional[str] = None
    type: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    scope: Optional[str] = None
    dedup_key: Optional[str] = None
    scope_key: Optional[str] = Field(default=None, alias="scopeKey")
    source_id: Optional[str] = Field(default=None, alias="sourceId")
    source_type: Optional[str] = Field(default=None, alias="sourceType")
    timestamp: Optional[int] = None


class EmitSignalResponse(BaseModel):
    success: bool = True
    actions_dispatched: int = 0
    actions: list[dict[str, Any]] = Field(default_factory=list)


class RegisterPolicyRequest(BaseModel):
    id: str
    name: str
    source_pattern: Optional[str] = None
    type_pattern: Optional[str] = None
    agent_id: Optional[str] = None
    action_type: str = "run_task"
    action_params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: int = 0
    max_firings_per_hour: int = 0


class PolicyResponse(BaseModel):
    id: str
    name: str
    source_pattern: Optional[str] = None
    type_pattern: Optional[str] = None
    agent_id: Optional[str] = None
    action_type: str
    enabled: bool
    cooldown_seconds: int
    max_firings_per_hour: int


class CleanupResponse(BaseModel):
    success: bool = True
    evicted: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/emit", response_model=EmitSignalResponse)
async def emit_signal(body: EmitSignalRequest):
    """Emit a signal into the orchestrator pipeline."""
    orchestrator = get_orchestrator()
    source = body.source or body.source_type
    signal_type = body.type or body.source_type

    if not source or not signal_type:
        raise HTTPException(status_code=422, detail="source/sourceType is required")

    signal = Signal(
        source=source,
        type=signal_type,
        agent_id=body.agent_id,
        user_id=body.user_id,
        payload=body.payload,
        scope=body.scope or body.scope_key,
        dedup_key=body.dedup_key or body.source_id,
    )

    actions: list[SignalAction] = await orchestrator.emit(signal)

    return EmitSignalResponse(
        success=True,
        actions_dispatched=len(actions),
        actions=[
            {
                "type": a.type,
                "agent_id": a.agent_id,
                "task_id": a.task_id,
                "params": a.params,
            }
            for a in actions
        ],
    )


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies():
    """List all registered signal policies."""
    orchestrator = get_orchestrator()
    return [
        PolicyResponse(
            id=p.id,
            name=p.name,
            source_pattern=p.source_pattern,
            type_pattern=p.type_pattern,
            agent_id=p.agent_id,
            action_type=p.action_type,
            enabled=p.enabled,
            cooldown_seconds=p.cooldown_seconds,
            max_firings_per_hour=p.max_firings_per_hour,
        )
        for p in orchestrator._policies
    ]


@router.post("/policies", response_model=PolicyResponse, status_code=201)
async def register_policy(body: RegisterPolicyRequest):
    """Register a new signal policy."""
    orchestrator = get_orchestrator()

    # Check for duplicate ID
    for existing in orchestrator._policies:
        if existing.id == body.id:
            raise HTTPException(status_code=409, detail=f"Policy {body.id} already exists")

    policy = SignalPolicy(
        id=body.id,
        name=body.name,
        source_pattern=body.source_pattern,
        type_pattern=body.type_pattern,
        agent_id=body.agent_id,
        action_type=body.action_type,
        action_params=body.action_params,
        enabled=body.enabled,
        cooldown_seconds=body.cooldown_seconds,
        max_firings_per_hour=body.max_firings_per_hour,
    )
    orchestrator.register_policy(policy)

    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        source_pattern=policy.source_pattern,
        type_pattern=policy.type_pattern,
        agent_id=policy.agent_id,
        action_type=policy.action_type,
        enabled=policy.enabled,
        cooldown_seconds=policy.cooldown_seconds,
        max_firings_per_hour=policy.max_firings_per_hour,
    )


@router.delete("/policies/{policy_id}")
async def unregister_policy(policy_id: str):
    """Remove a signal policy by ID."""
    orchestrator = get_orchestrator()
    original_len = len(orchestrator._policies)
    orchestrator._policies = [p for p in orchestrator._policies if p.id != policy_id]

    if len(orchestrator._policies) == original_len:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return {"success": True, "message": f"Policy {policy_id} removed"}


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_dedup(max_age_seconds: int = 3600):
    """Cleanup stale dedup cache entries."""
    orchestrator = get_orchestrator()
    evicted = orchestrator.cleanup_dedup_cache(max_age_seconds)
    return CleanupResponse(success=True, evicted=evicted)
