from datetime import UTC, datetime

import pytest
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.config import settings
from app.services.workflows.handlers import is_execution_time
from app.services.workflows.temporal_backend import (
    cancel_temporal_workflow,
    start_temporal_workflow,
    temporal_available,
    workflow_id_for,
    workflow_id_reuse_policy,
)
from app.services.workflows.temporal_definitions import (
    _activity_retry_policy,
    _child_retry_policy,
    _webhook_retry_policy,
)


def test_is_execution_time_matches_current_minute_without_prior_run():
    assert is_execution_time(
        cron_pattern="*/5 * * * *",
        current_time=datetime(2026, 5, 21, 10, 15, tzinfo=UTC),
        last_executed_at=None,
        timezone="UTC",
    )


def test_is_execution_time_skips_when_last_run_is_current_minute():
    current = datetime(2026, 5, 21, 10, 15, tzinfo=UTC)

    assert not is_execution_time(
        cron_pattern="*/5 * * * *",
        current_time=current,
        last_executed_at=current,
        timezone="UTC",
    )


def test_is_execution_time_respects_timezone():
    assert is_execution_time(
        cron_pattern="0 9 * * *",
        current_time=datetime(2026, 5, 21, 14, 0, tzinfo=UTC),
        last_executed_at=None,
        timezone="America/Chicago",
    )


def test_temporal_backend_is_available_with_installed_sdk():
    assert temporal_available()


def test_workflow_id_reuse_policy_defaults_to_duplicate_failed_only():
    assert workflow_id_reuse_policy() is WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
    assert workflow_id_reuse_policy("allow_duplicate") is WorkflowIDReusePolicy.ALLOW_DUPLICATE
    assert workflow_id_reuse_policy("reject-duplicate") is WorkflowIDReusePolicy.REJECT_DUPLICATE


def test_workflow_id_is_deterministic_for_known_payload_identity():
    assert (
        workflow_id_for("task/schedule-execute", {"taskId": "task:123"})
        == "ethos-task-schedule-execute-task-123"
    )


def test_temporal_retry_policies_are_configurable_from_workflow_input():
    assert _activity_retry_policy({"activityMaxAttempts": 4}).maximum_attempts == 4
    assert _webhook_retry_policy({"webhookMaxAttempts": 8}).maximum_attempts == 8
    assert _child_retry_policy({"childWorkflowMaxAttempts": 2}).maximum_attempts == 2


@pytest.mark.asyncio
async def test_start_temporal_workflow_reports_duplicate_without_inline_rerun(monkeypatch):
    class FakeClient:
        async def start_workflow(self, *_args, **kwargs):
            assert kwargs["id"] == "ethos-task-schedule-execute-task-123"
            assert kwargs["id_reuse_policy"] is WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
            raise WorkflowAlreadyStartedError(kwargs["id"], "EthosWorkflow")

    async def fake_get_temporal_client():
        return FakeClient()

    monkeypatch.setattr(
        "app.services.workflows.temporal_backend.get_temporal_client",
        fake_get_temporal_client,
    )

    result = await start_temporal_workflow("task/schedule-execute", {"taskId": "task:123"})

    assert result == {
        "accepted": False,
        "duplicate": True,
        "success": True,
        "temporalTaskQueue": settings.temporal_task_queue,
        "workflowId": "ethos-task-schedule-execute-task-123",
        "workflowName": "task/schedule-execute",
    }


@pytest.mark.asyncio
async def test_cancel_temporal_workflow_calls_cancel(monkeypatch):
    calls = []

    class FakeHandle:
        async def cancel(self):
            calls.append({"action": "cancel"})

        async def terminate(self, *, reason=None):
            calls.append({"action": "terminate", "reason": reason})

    class FakeClient:
        def get_workflow_handle(self, workflow_id, *, run_id=None):
            calls.append({"run_id": run_id, "workflow_id": workflow_id})
            return FakeHandle()

    async def fake_get_temporal_client():
        return FakeClient()

    monkeypatch.setattr(
        "app.services.workflows.temporal_backend.get_temporal_client",
        fake_get_temporal_client,
    )

    result = await cancel_temporal_workflow("wf_1", run_id="run_1", reason="user requested")

    assert result == {
        "action": "canceled",
        "reason": "user requested",
        "runId": "run_1",
        "success": True,
        "workflowId": "wf_1",
    }
    assert calls == [{"run_id": "run_1", "workflow_id": "wf_1"}, {"action": "cancel"}]


@pytest.mark.asyncio
async def test_cancel_temporal_workflow_can_terminate(monkeypatch):
    calls = []

    class FakeHandle:
        async def cancel(self):
            calls.append({"action": "cancel"})

        async def terminate(self, *, reason=None):
            calls.append({"action": "terminate", "reason": reason})

    class FakeClient:
        def get_workflow_handle(self, workflow_id, *, run_id=None):
            return FakeHandle()

    async def fake_get_temporal_client():
        return FakeClient()

    monkeypatch.setattr(
        "app.services.workflows.temporal_backend.get_temporal_client",
        fake_get_temporal_client,
    )

    result = await cancel_temporal_workflow("wf_1", reason="stale", terminate=True)

    assert result["action"] == "terminated"
    assert calls == [{"action": "terminate", "reason": "stale"}]
