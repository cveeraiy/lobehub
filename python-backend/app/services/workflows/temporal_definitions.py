"""Temporal workflow and activity definitions."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

try:
    from temporalio import activity, workflow
    from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
    from temporalio.exceptions import CancelledError
except Exception:  # pragma: no cover - only used before dependency sync
    activity = None
    workflow = None
    CancelledError = None
    RetryPolicy = None
    WorkflowIDReusePolicy = None


def temporal_definitions_available() -> bool:
    return activity is not None and workflow is not None and RetryPolicy is not None and WorkflowIDReusePolicy is not None


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, parsed)


def _activity_retry_policy(input_: dict[str, Any], *, default: int = 3):
    if RetryPolicy is None:
        return None
    return RetryPolicy(maximum_attempts=_positive_int(input_.get("activityMaxAttempts"), default))


def _webhook_retry_policy(input_: dict[str, Any]):
    if RetryPolicy is None:
        return None
    return RetryPolicy(maximum_attempts=_positive_int(input_.get("webhookMaxAttempts"), 5))


def _child_retry_policy(input_: dict[str, Any]):
    if RetryPolicy is None:
        return None
    return RetryPolicy(maximum_attempts=_positive_int(input_.get("childWorkflowMaxAttempts"), 1))


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

    @activity.defn
    async def plan_ethos_workflow_activity(input_: dict[str, Any]) -> Any:
        name = input_.get("name")
        payload = input_.get("payload") or {}
        if not isinstance(name, str) or not isinstance(payload, dict):
            raise ValueError("Temporal workflow planner input must include name and payload")

        from app.db import get_db_context
        from app.services.workflows.handlers import execute_workflow_planner

        async with get_db_context() as session:
            return await execute_workflow_planner(name, payload, session)

    @activity.defn
    async def deliver_webhook_activity(input_: dict[str, Any]) -> dict[str, Any]:
        import httpx

        url = input_.get("url")
        payload = input_.get("payload") or {}
        if not isinstance(url, str) or not url:
            raise ValueError("Webhook delivery requires url")
        if not isinstance(payload, dict):
            raise ValueError("Webhook delivery payload must be an object")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            return {"statusCode": response.status_code, "success": True}


else:

    async def execute_ethos_workflow_activity(_input_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("temporalio is not installed")

    async def plan_ethos_workflow_activity(_input_: dict[str, Any]) -> Any:
        raise RuntimeError("temporalio is not installed")

    async def deliver_webhook_activity(_input_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("temporalio is not installed")


if workflow is not None:

    @workflow.defn
    class EthosWorkflow:
        @workflow.run
        async def run(self, input_: dict[str, Any]) -> dict[str, Any]:
            name = input_.get("name")
            timeout_seconds = int(input_.get("activityTimeoutSeconds") or 900)
            if name == "agent-runtime-hook/webhook-delivery":
                return await workflow.execute_activity(
                    deliver_webhook_activity,
                    input_.get("payload") or {},
                    retry_policy=_webhook_retry_policy(input_),
                    start_to_close_timeout=timedelta(seconds=timeout_seconds),
                )
            if name == "task/schedule-dispatch":
                return await _run_schedule_dispatch_workflow(input_, timeout_seconds)
            if name == "agent-eval-run/run-benchmark":
                return await _run_agent_eval_run_benchmark_workflow(input_, timeout_seconds)
            if name == "agent-eval-run/paginate-test-cases":
                return await _run_agent_eval_run_benchmark_workflow(input_, timeout_seconds)
            if name == "memory-user-memory/pipelines/chat-topic/process-users":
                return await _run_memory_process_users_workflow(input_, timeout_seconds)
            if name == "memory-user-memory/pipelines/chat-topic/process-user-topics":
                return await _run_memory_process_user_topics_workflow(input_, timeout_seconds)
            if name == "memory-user-memory/pipelines/chat-topic/process-topics":
                return await _run_memory_process_topics_workflow(input_, timeout_seconds)
            if name == "memory-user-memory/pipelines/chat-topic/process-topic":
                return await _run_memory_process_topic_workflow(input_, timeout_seconds)
            return await workflow.execute_activity(
                execute_ethos_workflow_activity,
                input_,
                retry_policy=_activity_retry_policy(input_),
                start_to_close_timeout=timedelta(seconds=timeout_seconds),
            )


    async def _run_activity(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        return await workflow.execute_activity(
            execute_ethos_workflow_activity,
            input_,
            retry_policy=_activity_retry_policy(input_),
            start_to_close_timeout=timedelta(seconds=timeout_seconds),
        )


    async def _run_plan(input_: dict[str, Any], timeout_seconds: int) -> Any:
        return await workflow.execute_activity(
            plan_ethos_workflow_activity,
            input_,
            retry_policy=_activity_retry_policy(input_),
            start_to_close_timeout=timedelta(seconds=timeout_seconds),
        )


    def _child_input(name: str, payload: dict[str, Any], parent: dict[str, Any]) -> dict[str, Any]:
        return {
            "activityTimeoutSeconds": parent.get("activityTimeoutSeconds") or 900,
            "activityMaxAttempts": parent.get("activityMaxAttempts") or 3,
            "childWorkflowMaxAttempts": parent.get("childWorkflowMaxAttempts") or 1,
            "name": name,
            "payload": payload,
            "webhookMaxAttempts": parent.get("webhookMaxAttempts") or 5,
            "workflowTimeoutSeconds": parent.get("workflowTimeoutSeconds") or 3600,
        }


    async def _start_child(name: str, payload: dict[str, Any], parent: dict[str, Any], child_id: str):
        return await workflow.start_child_workflow(
            EthosWorkflow.run,
            _child_input(name, payload, parent),
            id=f"{workflow.info().workflow_id}:{child_id}",
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            parent_close_policy=workflow.ParentClosePolicy.TERMINATE,
            retry_policy=_child_retry_policy(parent),
            task_queue=workflow.info().task_queue,
            execution_timeout=timedelta(seconds=int(parent.get("workflowTimeoutSeconds") or 3600)),
        )


    async def _collect_child_failures(items: list[Any], handles: list[Any], key: str) -> list[dict[str, str]]:
        failures: list[dict[str, str]] = []
        for item, handle in zip(items, handles):
            try:
                await handle
            except Exception as exc:
                if _is_cancelled_failure(exc):
                    raise
                failures.append({"error": str(exc), key: str(item)})
        return failures


    def _is_cancelled_failure(exc: BaseException) -> bool:
        current: BaseException | None = exc
        while current is not None:
            if CancelledError is not None and isinstance(current, CancelledError):
                return True
            current = current.__cause__
        return False


    async def _await_child_result(handle: Any) -> Any:
        try:
            return await handle
        except Exception as exc:
            if _is_cancelled_failure(exc):
                raise
            raise


    async def _run_schedule_dispatch_workflow(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        payload = input_.get("payload") or {}
        plan = await _run_plan({"name": "task/schedule-dispatch:plan", "payload": payload}, timeout_seconds)
        due = plan.get("due") or []
        if plan.get("dryRun") or not due:
            return {
                "dispatched": 0,
                "dryRun": bool(plan.get("dryRun")),
                "due": len(due),
                "skipped": plan.get("skipped", 0),
                "success": True,
                "total": plan.get("total", 0),
            }

        handles = []
        for item in due:
            handles.append(
                await _start_child(
                    "task/schedule-execute",
                    {"taskId": item["taskId"], "userId": item["userId"]},
                    input_,
                    f"task:{item['taskId']}",
                )
            )

        failures = await _collect_child_failures([item["taskId"] for item in due], handles, "taskId")
        return {
            "dispatched": len(due) - len(failures),
            "due": len(due),
            "failures": failures,
            "skipped": plan.get("skipped", 0),
            "success": not failures,
            "total": plan.get("total", 0),
        }


    async def _cancel_requested(payload: dict[str, Any], timeout_seconds: int) -> bool:
        return bool(
            await _run_plan(
                {"name": "memory-user-memory/cancel-check", "payload": payload},
                timeout_seconds,
            )
        )


    async def _run_agent_eval_run_benchmark_workflow(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        payload = input_.get("payload") or {}
        plan = await _run_plan({"name": "agent-eval-run/test-cases:plan", "payload": payload}, timeout_seconds)
        test_case_ids = [case_id for case_id in plan.get("testCaseIds") or [] if case_id]
        if not test_case_ids:
            return await _run_activity(input_, timeout_seconds)

        handles = []
        for index, test_case_id in enumerate(test_case_ids):
            child_payload = {**payload, "testCaseId": test_case_id}
            handles.append(
                await _start_child(
                    "agent-eval-run/execute-test-case",
                    child_payload,
                    input_,
                    f"case:{test_case_id}:{index}",
                )
            )

        failures: list[dict[str, str]] = []
        completed = 0
        passed = 0
        total_score = 0.0
        for test_case_id, handle in zip(test_case_ids, handles):
            try:
                result = await _await_child_result(handle)
                completed += 1
                passed += 1 if result.get("passed") else 0
                total_score += float(result.get("score") or 0)
            except Exception as exc:
                failures.append({"error": str(exc), "testCaseId": test_case_id})
        summary = {
            "avg_score": round(total_score / len(test_case_ids), 4) if test_case_ids else 0,
            "completed": completed,
            "failed": len(test_case_ids) - passed,
            "failures": failures,
            "passed": passed,
            "run_id": payload.get("runId") or payload.get("run_id"),
            "status": "completed" if not failures else "failed",
            "success": not failures,
            "total": len(test_case_ids),
        }
        await _run_activity(
            _child_input(
                "agent-eval-run/finalize-run",
                {
                    **payload,
                    "status": summary["status"],
                },
                input_,
            ),
            timeout_seconds,
        )
        return summary


    async def _run_memory_process_users_workflow(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        payload = input_.get("payload") or {}
        user_ids = [user_id for user_id in payload.get("userIds") or [payload.get("userId")] if user_id]
        if not user_ids:
            return await _run_activity(input_, timeout_seconds)
        if await _cancel_requested({**payload, "userId": user_ids[0]}, timeout_seconds):
            return {"message": "Memory extraction task cancellation requested, skip processing users."}

        handles = []
        for index in range(0, len(user_ids), 10):
            batch = user_ids[index : index + 10]
            child_payload = {**payload, "userId": batch[0], "userIds": batch, "topicCursor": None}
            handles.append(
                await _start_child(
                    "memory-user-memory/pipelines/chat-topic/process-user-topics",
                    child_payload,
                    input_,
                    f"users:{index}",
                )
            )
        failures = await _collect_child_failures([str(index) for index in range(len(handles))], handles, "batch")
        return {
            "batches": len(handles),
            "failures": failures,
            "processedUsers": len(user_ids),
            "success": not failures,
        }


    async def _run_memory_process_user_topics_workflow(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        payload = input_.get("payload") or {}
        user_ids = [user_id for user_id in payload.get("userIds") or [payload.get("userId")] if user_id]
        topic_ids = [topic_id for topic_id in payload.get("topicIds") or [payload.get("topicId")] if topic_id]
        if not user_ids or not topic_ids:
            return await _run_activity(input_, timeout_seconds)

        handles = []
        for user_id in user_ids:
            if await _cancel_requested({**payload, "userId": user_id}, timeout_seconds):
                continue
            for index in range(0, len(topic_ids), 4):
                batch = topic_ids[index : index + 4]
                child_payload = {**payload, "topicIds": batch, "userId": user_id, "userIds": [user_id]}
                handles.append(
                    await _start_child(
                        "memory-user-memory/pipelines/chat-topic/process-topics",
                        child_payload,
                        input_,
                        f"user:{user_id}:topics:{index}",
                    )
                )
        failures = await _collect_child_failures([str(index) for index in range(len(handles))], handles, "batch")
        return {
            "failures": failures,
            "processedUsers": len(user_ids),
            "scheduledBatches": len(handles),
            "success": not failures,
        }


    async def _run_memory_process_topics_workflow(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        payload = input_.get("payload") or {}
        user_id = payload.get("userId") or (payload.get("userIds") or [None])[0]
        topic_ids = [topic_id for topic_id in payload.get("topicIds") or [payload.get("topicId")] if topic_id]
        if not user_id or not topic_ids:
            return {"message": "No topic ids provided for extraction.", "processedTopics": 0, "processedUsers": 0}
        if await _cancel_requested({**payload, "userId": user_id}, timeout_seconds):
            return {"message": "Memory extraction task cancellation requested, skip topic batch.", "processedTopics": 0}

        handles = []
        for index, topic_id in enumerate(topic_ids):
            child_payload = {
                **payload,
                "topicId": topic_id,
                "topicIds": [topic_id],
                "userId": user_id,
                "userIds": [user_id],
            }
            handles.append(
                await _start_child(
                    "memory-user-memory/pipelines/chat-topic/process-topic",
                    child_payload,
                    input_,
                    f"topic:{topic_id}:{index}",
                )
            )
        failures = await _collect_child_failures([str(topic_id) for topic_id in topic_ids], handles, "topicId")
        if failures:
            return {
                "failures": failures,
                "processedTopics": len(topic_ids) - len(failures),
                "processedUsers": 1,
                "success": False,
            }

        persona_handle = await _start_child(
            "memory-user-memory/pipelines/persona/update-writing",
            {"userId": user_id, "userIds": [user_id]},
            input_,
            f"persona:{user_id}",
        )
        await _await_child_result(persona_handle)
        return {"processedTopics": len(topic_ids), "processedUsers": 1, "success": True}


    async def _run_memory_process_topic_workflow(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        payload = input_.get("payload") or {}
        user_id = payload.get("userId") or (payload.get("userIds") or [None])[0]
        if await _cancel_requested({**payload, "userId": user_id}, timeout_seconds):
            return {"message": "Memory extraction task cancellation requested, skip topic."}
        result = await _run_activity(input_, timeout_seconds)
        if await _cancel_requested({**payload, "userId": user_id}, timeout_seconds):
            return {"message": "Memory extraction task cancellation requested after topic extraction."}
        return result


else:

    class EthosWorkflow:
        async def run(self, _input_: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("temporalio is not installed")
