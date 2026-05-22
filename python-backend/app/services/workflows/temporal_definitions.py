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
                    retry_policy=RetryPolicy(maximum_attempts=5),
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
                retry_policy=RetryPolicy(maximum_attempts=3),
                start_to_close_timeout=timedelta(seconds=timeout_seconds),
            )


    async def _run_activity(input_: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
        return await workflow.execute_activity(
            execute_ethos_workflow_activity,
            input_,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=timedelta(seconds=timeout_seconds),
        )


    async def _run_plan(input_: dict[str, Any], timeout_seconds: int) -> Any:
        return await workflow.execute_activity(
            plan_ethos_workflow_activity,
            input_,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=timedelta(seconds=timeout_seconds),
        )


    def _child_input(name: str, payload: dict[str, Any], parent: dict[str, Any]) -> dict[str, Any]:
        return {
            "activityTimeoutSeconds": parent.get("activityTimeoutSeconds") or 900,
            "name": name,
            "payload": payload,
        }


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
                await workflow.start_child_workflow(
                    EthosWorkflow.run,
                    _child_input("task/schedule-execute", {"taskId": item["taskId"], "userId": item["userId"]}, input_),
                    id=f"{workflow.info().workflow_id}:task:{item['taskId']}",
                    task_queue=workflow.info().task_queue,
                    execution_timeout=timedelta(seconds=int(input_.get("workflowTimeoutSeconds") or 3600)),
                )
            )

        failures: list[dict[str, str]] = []
        for item, handle in zip(due, handles):
            try:
                await handle.result()
            except Exception as exc:
                failures.append({"error": str(exc), "taskId": item["taskId"]})
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
                await workflow.start_child_workflow(
                    EthosWorkflow.run,
                    _child_input("agent-eval-run/execute-test-case", child_payload, input_),
                    id=f"{workflow.info().workflow_id}:case:{test_case_id}:{index}",
                    task_queue=workflow.info().task_queue,
                )
            )

        failures: list[dict[str, str]] = []
        completed = 0
        passed = 0
        total_score = 0.0
        for test_case_id, handle in zip(test_case_ids, handles):
            try:
                result = await handle.result()
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
                await workflow.start_child_workflow(
                    EthosWorkflow.run,
                    _child_input("memory-user-memory/pipelines/chat-topic/process-user-topics", child_payload, input_),
                    id=f"{workflow.info().workflow_id}:users:{index}",
                    task_queue=workflow.info().task_queue,
                )
            )
        for handle in handles:
            await handle.result()
        return {"batches": len(handles), "processedUsers": len(user_ids), "success": True}


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
                    await workflow.start_child_workflow(
                        EthosWorkflow.run,
                        _child_input("memory-user-memory/pipelines/chat-topic/process-topics", child_payload, input_),
                        id=f"{workflow.info().workflow_id}:user:{user_id}:topics:{index}",
                        task_queue=workflow.info().task_queue,
                    )
                )
        for handle in handles:
            await handle.result()
        return {"processedUsers": len(user_ids), "scheduledBatches": len(handles), "success": True}


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
                await workflow.start_child_workflow(
                    EthosWorkflow.run,
                    _child_input("memory-user-memory/pipelines/chat-topic/process-topic", child_payload, input_),
                    id=f"{workflow.info().workflow_id}:topic:{topic_id}:{index}",
                    task_queue=workflow.info().task_queue,
                )
            )
        for handle in handles:
            await handle.result()

        await workflow.start_child_workflow(
            EthosWorkflow.run,
            _child_input(
                "memory-user-memory/pipelines/persona/update-writing",
                {"userId": user_id, "userIds": [user_id]},
                input_,
            ),
            id=f"{workflow.info().workflow_id}:persona:{user_id}",
            task_queue=workflow.info().task_queue,
        )
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
