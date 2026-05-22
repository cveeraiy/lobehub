"""Temporal workflow and activity definitions."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

try:
    from temporalio import activity, workflow
    from temporalio.common import RetryPolicy
except Exception:  # pragma: no cover - only used before dependency sync
    activity = None
    workflow = None
    RetryPolicy = None


def temporal_definitions_available() -> bool:
    return activity is not None and workflow is not None and RetryPolicy is not None


if activity is not None:

    @activity.defn
    async def execute_ethos_workflow_activity(input_: dict[str, Any]) -> dict[str, Any]:
        name = input_.get("name")
        payload = input_.get("payload") or {}
        if not isinstance(name, str) or not isinstance(payload, dict):
            raise ValueError("Temporal workflow input must include name and payload")

        from app.db import get_db_context
        from app.services.workflows.handlers import execute_workflow_handler

        async with get_db_context() as session:
            return await execute_workflow_handler(name, payload, session)


else:

    async def execute_ethos_workflow_activity(_input_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("temporalio is not installed")


if workflow is not None:

    @workflow.defn
    class EthosWorkflow:
        @workflow.run
        async def run(self, input_: dict[str, Any]) -> dict[str, Any]:
            timeout_seconds = int(input_.get("activityTimeoutSeconds") or 900)
            return await workflow.execute_activity(
                execute_ethos_workflow_activity,
                input_,
                retry_policy=RetryPolicy(maximum_attempts=3),
                start_to_close_timeout=timedelta(seconds=timeout_seconds),
            )


else:

    class EthosWorkflow:
        async def run(self, _input_: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("temporalio is not installed")
