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
    from temporalio.worker import Worker
except Exception:  # pragma: no cover - exercised when dependency is absent in old envs
    Client = None
    WorkflowIDReusePolicy = None
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


async def get_temporal_client():
    if Client is None:
        raise TemporalUnavailableError("temporalio is not installed")
    return await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)


async def start_temporal_workflow(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not temporal_available():
        raise TemporalUnavailableError("temporalio is not installed")
    client = await get_temporal_client()
    workflow_id = workflow_id_for(name, payload)
    handle = await client.start_workflow(
        EthosWorkflow.run,
        {
            "activityTimeoutSeconds": settings.temporal_activity_timeout_seconds,
            "name": name,
            "payload": payload,
            "workflowTimeoutSeconds": settings.temporal_workflow_timeout_seconds,
        },
        id=workflow_id,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        task_queue=settings.temporal_task_queue,
        execution_timeout=timedelta(seconds=settings.temporal_workflow_timeout_seconds),
    )
    return {
        "accepted": True,
        "success": True,
        "temporalTaskQueue": settings.temporal_task_queue,
        "workflowName": name,
        "workflowRunId": handle.result_run_id,
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
