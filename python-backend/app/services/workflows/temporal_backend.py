"""Temporal backend for durable workflow execution."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from uuid import uuid4

from app.config import settings
from app.services.workflows.temporal_definitions import (
    EthosWorkflow,
    deliver_webhook_activity,
    execute_ethos_workflow_activity,
    plan_ethos_workflow_activity,
    temporal_definitions_available,
)

try:
    from temporalio.client import Client
    from temporalio.common import WorkflowIDReusePolicy
    from temporalio.exceptions import WorkflowAlreadyStartedError
    from temporalio.worker import Worker
except Exception:  # pragma: no cover - exercised when dependency is absent in old envs
    Client = None
    WorkflowIDReusePolicy = None
    WorkflowAlreadyStartedError = None
    Worker = None


class TemporalUnavailableError(RuntimeError):
    """Raised when Temporal is enabled but the SDK/server is not available."""


def temporal_available() -> bool:
    return Client is not None and Worker is not None and temporal_definitions_available()


def workflow_id_for(name: str, payload: dict[str, Any]) -> str:
    identity = (
        payload.get("workflowRunId")
        or payload.get("runId")
        or payload.get("run_id")
        or payload.get("taskId")
        or payload.get("task_id")
        or payload.get("topicId")
        or payload.get("topic_id")
        or payload.get("deliveryId")
        or payload.get("delivery_id")
        or uuid4().hex
    )
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-")
    safe_identity = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(identity)).strip("-")
    return f"ethos-{safe_name}-{safe_identity}"


def workflow_id_reuse_policy(value: str | None = None):
    if WorkflowIDReusePolicy is None:
        raise TemporalUnavailableError("temporalio is not installed")
    normalized = (value or settings.temporal_workflow_id_reuse_policy).strip().lower().replace("-", "_")
    mapping = {
        "allow_duplicate": WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        "allow_duplicate_failed_only": WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        "reject_duplicate": WorkflowIDReusePolicy.REJECT_DUPLICATE,
        "terminate_if_running": WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    }
    return mapping.get(normalized, WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY)


async def get_temporal_client():
    if Client is None:
        raise TemporalUnavailableError("temporalio is not installed")
    return await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)


async def start_temporal_workflow(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not temporal_available():
        raise TemporalUnavailableError("temporalio is not installed")
    client = await get_temporal_client()
    workflow_id = workflow_id_for(name, payload)
    try:
        handle = await client.start_workflow(
            EthosWorkflow.run,
            {
                "activityTimeoutSeconds": settings.temporal_activity_timeout_seconds,
                "activityMaxAttempts": settings.temporal_activity_max_attempts,
                "childWorkflowMaxAttempts": settings.temporal_child_workflow_max_attempts,
                "name": name,
                "payload": payload,
                "webhookMaxAttempts": settings.temporal_webhook_max_attempts,
                "workflowTimeoutSeconds": settings.temporal_workflow_timeout_seconds,
            },
            id=workflow_id,
            id_reuse_policy=workflow_id_reuse_policy(),
            task_queue=settings.temporal_task_queue,
            execution_timeout=timedelta(seconds=settings.temporal_workflow_timeout_seconds),
        )
    except Exception as exc:
        if WorkflowAlreadyStartedError is not None and isinstance(exc, WorkflowAlreadyStartedError):
            return {
                "accepted": False,
                "duplicate": True,
                "success": True,
                "temporalTaskQueue": settings.temporal_task_queue,
                "workflowName": name,
                "workflowId": workflow_id,
            }
        raise
    return {
        "accepted": True,
        "success": True,
        "temporalTaskQueue": settings.temporal_task_queue,
        "workflowName": name,
        "workflowRunId": handle.result_run_id,
        "workflowId": workflow_id,
    }


async def cancel_temporal_workflow(
    workflow_id: str,
    *,
    reason: str | None = None,
    run_id: str | None = None,
    terminate: bool = False,
) -> dict[str, Any]:
    if not temporal_available():
        raise TemporalUnavailableError("temporalio is not installed")
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id, run_id=run_id)
    if terminate:
        await handle.terminate(reason=reason)
        action = "terminated"
    else:
        await handle.cancel()
        action = "canceled"
    return {
        "action": action,
        "reason": reason,
        "runId": run_id,
        "success": True,
        "workflowId": workflow_id,
    }


async def start_temporal_webhook_delivery(
    url: str,
    payload: dict[str, Any],
    *,
    hook_id: str | None = None,
) -> dict[str, Any]:
    delivery_payload = {"payload": payload, "url": url}
    identity = hook_id or payload.get("hookId") or uuid4().hex
    return await start_temporal_workflow(
        "agent-runtime-hook/webhook-delivery",
        {"deliveryId": identity, **delivery_payload},
    )


async def run_worker() -> None:
    if not temporal_available():
        raise TemporalUnavailableError("temporalio is not installed")
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[EthosWorkflow],
        activities=[execute_ethos_workflow_activity, plan_ethos_workflow_activity, deliver_webhook_activity],
    )
    await worker.run()
