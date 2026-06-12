import asyncio
import json
import os
import uuid
from collections import Counter
from datetime import timedelta

import pytest
from temporalio import activity
from temporalio.client import Client, WorkflowFailureError
from temporalio.worker import Worker

from app.config import settings
from app.services.workflows.temporal_definitions import (
    EthosWorkflow,
    deliver_webhook_activity,
    execute_ethos_workflow_activity,
    plan_ethos_workflow_activity,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TEMPORAL_LIVE_TESTS") != "1",
    reason="Set RUN_TEMPORAL_LIVE_TESTS=1 to run live Temporal tests.",
)


async def _read_http_request_body(reader: asyncio.StreamReader) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = await reader.read(4096)
        if not chunk:
            break
        data += chunk

    headers, _, rest = data.partition(b"\r\n\r\n")
    content_length = 0
    for line in headers.decode(errors="replace").split("\r\n"):
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())

    body = rest
    while len(body) < content_length:
        body += await reader.read(content_length - len(body))
    return body[:content_length]


@pytest.mark.asyncio
async def test_live_temporal_worker_executes_webhook_delivery_workflow():
    received: list[dict] = []

    async def handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        body = await _read_http_request_body(reader)
        received.append(json.loads(body.decode() or "{}"))
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 2\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"ok"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_request, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    task_queue = f"ethos-live-test-{uuid.uuid4().hex}"
    workflow_id = f"ethos-live-test-{uuid.uuid4().hex}"

    try:
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[EthosWorkflow],
            activities=[
                execute_ethos_workflow_activity,
                plan_ethos_workflow_activity,
                deliver_webhook_activity,
            ],
        ):
            result = await client.execute_workflow(
                EthosWorkflow.run,
                {
                    "activityTimeoutSeconds": 10,
                    "name": "agent-runtime-hook/webhook-delivery",
                    "payload": {
                        "payload": {"hello": "temporal", "workflowId": workflow_id},
                        "url": f"http://127.0.0.1:{port}/hook",
                    },
                    "webhookMaxAttempts": 1,
                    "workflowTimeoutSeconds": 30,
                },
                id=workflow_id,
                task_queue=task_queue,
                execution_timeout=timedelta(seconds=30),
            )
    finally:
        server.close()
        await server.wait_closed()

    assert result == {"statusCode": 200, "success": True}
    assert received == [{"hello": "temporal", "workflowId": workflow_id}]


@pytest.mark.asyncio
async def test_live_temporal_worker_executes_agent_eval_child_fanout():
    activity_calls: list[dict] = []

    @activity.defn(name="plan_ethos_workflow_activity")
    async def fake_plan_activity(input_: dict) -> dict:
        activity_calls.append({"input": input_, "type": "plan"})
        assert input_["name"] == "agent-eval-run/test-cases:plan"
        return {"runId": "run_live", "testCaseIds": ["case_1", "case_2"], "userId": "user_live"}

    @activity.defn(name="execute_ethos_workflow_activity")
    async def fake_execute_activity(input_: dict) -> dict:
        activity_calls.append({"input": input_, "type": "execute"})
        name = input_["name"]
        payload = input_.get("payload") or {}
        if name == "agent-eval-run/execute-test-case":
            return {
                "passed": payload["testCaseId"] == "case_1",
                "score": 1.0 if payload["testCaseId"] == "case_1" else 0.25,
                "status": "completed",
                "success": True,
                "testCaseId": payload["testCaseId"],
            }
        if name == "agent-eval-run/finalize-run":
            return {"runId": payload["runId"], "status": payload["status"], "success": True}
        raise AssertionError(f"Unexpected workflow activity: {name}")

    task_queue = f"ethos-live-fanout-{uuid.uuid4().hex}"
    workflow_id = f"ethos-live-fanout-{uuid.uuid4().hex}"
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[EthosWorkflow],
        activities=[fake_execute_activity, fake_plan_activity],
    ):
        result = await client.execute_workflow(
            EthosWorkflow.run,
            {
                "activityMaxAttempts": 1,
                "activityTimeoutSeconds": 10,
                "childWorkflowMaxAttempts": 1,
                "name": "agent-eval-run/run-benchmark",
                "payload": {"runId": "run_live", "userId": "user_live"},
                "workflowTimeoutSeconds": 30,
            },
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

    assert result == {
        "avg_score": 0.625,
        "completed": 2,
        "failed": 1,
        "failures": [],
        "passed": 1,
        "run_id": "run_live",
        "status": "completed",
        "success": True,
        "total": 2,
    }
    assert [call["input"]["name"] for call in activity_calls] == [
        "agent-eval-run/test-cases:plan",
        "agent-eval-run/execute-test-case",
        "agent-eval-run/execute-test-case",
        "agent-eval-run/finalize-run",
    ]


@pytest.mark.asyncio
async def test_live_temporal_worker_executes_task_schedule_child_fanout():
    activity_calls: list[dict] = []

    @activity.defn(name="plan_ethos_workflow_activity")
    async def fake_plan_activity(input_: dict) -> dict:
        activity_calls.append({"input": input_, "type": "plan"})
        assert input_["name"] == "task/schedule-dispatch:plan"
        return {
            "due": [
                {"taskId": "task_1", "userId": "user_live"},
                {"taskId": "task_2", "userId": "user_live"},
            ],
            "skipped": 1,
            "success": True,
            "total": 3,
        }

    @activity.defn(name="execute_ethos_workflow_activity")
    async def fake_execute_activity(input_: dict) -> dict:
        activity_calls.append({"input": input_, "type": "execute"})
        assert input_["name"] == "task/schedule-execute"
        return {
            "status": "completed",
            "success": True,
            "taskId": input_["payload"]["taskId"],
        }

    task_queue = f"ethos-live-schedule-{uuid.uuid4().hex}"
    workflow_id = f"ethos-live-schedule-{uuid.uuid4().hex}"
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[EthosWorkflow],
        activities=[fake_execute_activity, fake_plan_activity],
    ):
        result = await client.execute_workflow(
            EthosWorkflow.run,
            {
                "activityMaxAttempts": 1,
                "activityTimeoutSeconds": 10,
                "childWorkflowMaxAttempts": 1,
                "name": "task/schedule-dispatch",
                "payload": {"now": "2026-05-23T12:00:00Z"},
                "workflowTimeoutSeconds": 30,
            },
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

    assert result == {
        "dispatched": 2,
        "due": 2,
        "failures": [],
        "skipped": 1,
        "success": True,
        "total": 3,
    }
    assert [call["input"]["name"] for call in activity_calls] == [
        "task/schedule-dispatch:plan",
        "task/schedule-execute",
        "task/schedule-execute",
    ]


@pytest.mark.asyncio
async def test_live_temporal_worker_honors_memory_cancel_checks_before_fanout():
    activity_calls: list[dict] = []

    @activity.defn(name="plan_ethos_workflow_activity")
    async def fake_plan_activity(input_: dict) -> bool:
        activity_calls.append({"input": input_, "type": "plan"})
        assert input_["name"] == "memory-user-memory/cancel-check"
        return True

    @activity.defn(name="execute_ethos_workflow_activity")
    async def fake_execute_activity(input_: dict) -> dict:
        activity_calls.append({"input": input_, "type": "execute"})
        raise AssertionError(f"Unexpected memory execution after cancellation: {input_['name']}")

    task_queue = f"ethos-live-memory-cancel-{uuid.uuid4().hex}"
    workflow_id = f"ethos-live-memory-cancel-{uuid.uuid4().hex}"
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[EthosWorkflow],
        activities=[fake_execute_activity, fake_plan_activity],
    ):
        result = await client.execute_workflow(
            EthosWorkflow.run,
            {
                "activityMaxAttempts": 1,
                "activityTimeoutSeconds": 10,
                "childWorkflowMaxAttempts": 1,
                "name": "memory-user-memory/pipelines/chat-topic/process-topics",
                "payload": {
                    "asyncTaskId": "async_1",
                    "topicIds": ["topic_1", "topic_2"],
                    "userId": "user_live",
                },
                "workflowTimeoutSeconds": 30,
            },
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

    assert result == {
        "message": "Memory extraction task cancellation requested, skip topic batch.",
        "processedTopics": 0,
    }
    assert [call["input"]["name"] for call in activity_calls] == ["memory-user-memory/cancel-check"]


@pytest.mark.asyncio
async def test_live_temporal_worker_executes_memory_topic_child_fanout_and_persona_update():
    activity_calls: list[dict] = []

    @activity.defn(name="plan_ethos_workflow_activity")
    async def fake_plan_activity(input_: dict) -> bool:
        activity_calls.append({"input": input_, "type": "plan"})
        assert input_["name"] == "memory-user-memory/cancel-check"
        return False

    @activity.defn(name="execute_ethos_workflow_activity")
    async def fake_execute_activity(input_: dict) -> dict:
        activity_calls.append({"input": input_, "type": "execute"})
        name = input_["name"]
        payload = input_.get("payload") or {}
        if name == "memory-user-memory/pipelines/chat-topic/process-topic":
            return {"success": True, "topicId": payload["topicId"]}
        if name == "memory-user-memory/pipelines/persona/update-writing":
            return {"success": True, "userId": payload["userId"]}
        raise AssertionError(f"Unexpected memory activity: {name}")

    task_queue = f"ethos-live-memory-fanout-{uuid.uuid4().hex}"
    workflow_id = f"ethos-live-memory-fanout-{uuid.uuid4().hex}"
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[EthosWorkflow],
        activities=[fake_execute_activity, fake_plan_activity],
    ):
        result = await client.execute_workflow(
            EthosWorkflow.run,
            {
                "activityMaxAttempts": 1,
                "activityTimeoutSeconds": 10,
                "childWorkflowMaxAttempts": 1,
                "name": "memory-user-memory/pipelines/chat-topic/process-topics",
                "payload": {
                    "asyncTaskId": "async_1",
                    "topicIds": ["topic_1", "topic_2"],
                    "userId": "user_live",
                },
                "workflowTimeoutSeconds": 30,
            },
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
    )

    assert result == {"processedTopics": 2, "processedUsers": 1, "success": True}
    assert Counter(call["input"]["name"] for call in activity_calls) == {
        "memory-user-memory/cancel-check": 5,
        "memory-user-memory/pipelines/chat-topic/process-topic": 2,
        "memory-user-memory/pipelines/persona/update-writing": 1,
    }


@pytest.mark.asyncio
async def test_live_temporal_worker_cancels_running_fanout_workflow():
    activity_started = asyncio.Event()

    @activity.defn(name="plan_ethos_workflow_activity")
    async def fake_plan_activity(input_: dict) -> dict:
        assert input_["name"] == "task/schedule-dispatch:plan"
        return {
            "due": [{"taskId": "task_cancel", "userId": "user_live"}],
            "skipped": 0,
            "success": True,
            "total": 1,
        }

    @activity.defn(name="execute_ethos_workflow_activity")
    async def fake_execute_activity(input_: dict) -> dict:
        assert input_["name"] == "task/schedule-execute"
        activity_started.set()
        while True:
            activity.heartbeat()
            await asyncio.sleep(0.1)

    task_queue = f"ethos-live-cancel-{uuid.uuid4().hex}"
    workflow_id = f"ethos-live-cancel-{uuid.uuid4().hex}"
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[EthosWorkflow],
        activities=[fake_execute_activity, fake_plan_activity],
    ):
        handle = await client.start_workflow(
            EthosWorkflow.run,
            {
                "activityMaxAttempts": 1,
                "activityTimeoutSeconds": 30,
                "childWorkflowMaxAttempts": 1,
                "name": "task/schedule-dispatch",
                "payload": {"now": "2026-05-23T12:00:00Z"},
                "workflowTimeoutSeconds": 30,
            },
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )
        await asyncio.wait_for(activity_started.wait(), timeout=10)
        await handle.cancel()
        with pytest.raises(WorkflowFailureError):
            await handle.result()
