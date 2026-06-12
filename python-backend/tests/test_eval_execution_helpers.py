from types import SimpleNamespace
from datetime import datetime, timedelta

import pytest

from app.routers.rag_eval import _parse_import_records_content, _score_answer
from app.services.agent_eval.service import AgentEvalService
from app.services.agent_eval.service import _score_expected_output
from app.services.agent_eval.service import _reset_resumed_thread_result
from app.services.workflows import handlers


def test_agent_eval_scores_exact_expected_output():
    score, passed, reasoning = _score_expected_output("The answer is Paris.", "Paris")

    assert score == 1
    assert passed is True
    assert "found" in reasoning


def test_agent_eval_scores_partial_term_overlap():
    score, passed, reasoning = _score_expected_output("retrieval generation", "retrieval augmented generation")

    assert score == 2 / 3
    assert passed is True
    assert "2/3" in reasoning


@pytest.mark.asyncio
async def test_agent_eval_evaluates_contains_rubric_from_benchmark(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    run = SimpleNamespace(benchmark_id="bench_1", config={"passThreshold": 0.8}, dataset_id="dataset_1")
    benchmark = SimpleNamespace(
        config={
            "rubrics": [
                {
                    "config": {"expected": "Paris"},
                    "id": "rubric_contains",
                    "type": "contains",
                    "weight": 1,
                }
            ]
        }
    )
    test_case = SimpleNamespace(expected_output="Paris", metadata_=None)

    async def fake_get_run(_run_id):
        return run

    async def fake_get_dataset(_dataset_id):
        return SimpleNamespace(metadata_=None)

    async def fake_get_benchmark(_benchmark_id):
        return benchmark

    monkeypatch.setattr(service, "get_run", fake_get_run)
    monkeypatch.setattr(service, "get_dataset", fake_get_dataset)
    monkeypatch.setattr(service, "get_benchmark", fake_get_benchmark)

    assert await service.evaluate_output_for_case("run_1", test_case, "The answer is Paris.") == {
        "passed": True,
        "reasoning": "Rubric score 1.0 with threshold 0.8.",
        "rubricScores": [
            {"reason": "Output contains expected value.", "rubricId": "rubric_contains", "score": 1.0}
        ],
        "score": 1.0,
        "status": "completed",
    }


@pytest.mark.asyncio
async def test_agent_eval_external_mode_defers_scoring(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    run = SimpleNamespace(benchmark_id="bench_1", config={}, dataset_id="dataset_1")
    test_case = SimpleNamespace(expected_output="Paris", metadata_={"evalMode": "external"})

    async def fake_get_run(_run_id):
        return run

    async def fake_get_dataset(_dataset_id):
        return SimpleNamespace(metadata_=None)

    async def fake_get_benchmark(_benchmark_id):
        return SimpleNamespace(config={"rubrics": []})

    monkeypatch.setattr(service, "get_run", fake_get_run)
    monkeypatch.setattr(service, "get_dataset", fake_get_dataset)
    monkeypatch.setattr(service, "get_benchmark", fake_get_benchmark)

    assert await service.evaluate_output_for_case("run_1", test_case, "The answer is Paris.") == {
        "awaitingExternalEval": True,
        "passed": None,
        "reasoning": "Awaiting external evaluation.",
        "rubricScores": [],
        "score": None,
        "status": "external",
    }


def test_rag_eval_scores_answer_against_ideal_terms():
    score, passed, reasoning = _score_answer("retrieval augmented generation uses context", "retrieval generation")

    assert score == 1
    assert passed is True
    assert "2/2" in reasoning


def test_rag_eval_import_parser_accepts_jsonl_records():
    records = _parse_import_records_content(
        '{"question":"Q1","ideal":"A1","referenceFiles":"doc.md"}\n'
        '{"question":"Q2","referenceFiles":["a.md","b.md"]}\n'
    )

    assert records == [
        {"question": "Q1", "ideal": "A1", "referenceFiles": "doc.md"},
        {"question": "Q2", "referenceFiles": ["a.md", "b.md"]},
    ]


def test_rag_eval_import_parser_accepts_json_array_records():
    records = _parse_import_records_content('[{"question":"Q1","ideal":"A1"}]')

    assert records == [{"question": "Q1", "ideal": "A1"}]


@pytest.mark.asyncio
async def test_agent_eval_filters_only_pending_run_topics(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")

    async def fake_list_run_topics(_run_id):
        return [
            SimpleNamespace(test_case_id="case_1", status="completed"),
            SimpleNamespace(test_case_id="case_2", status="pending"),
            SimpleNamespace(test_case_id="case_3", status="failed"),
        ]

    monkeypatch.setattr(service, "list_run_topics", fake_list_run_topics)

    assert await service.filter_test_cases_needing_execution(
        "run_1",
        ["case_1", "case_2", "case_3", "case_4"],
    ) == ["case_2"]


@pytest.mark.asyncio
async def test_agent_eval_keeps_all_candidates_when_no_run_topics_exist(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")

    async def fake_list_run_topics(_run_id):
        return []

    monkeypatch.setattr(service, "list_run_topics", fake_list_run_topics)

    assert await service.filter_test_cases_needing_execution("run_1", ["case_1", "case_2"]) == [
        "case_1",
        "case_2",
    ]


@pytest.mark.asyncio
async def test_agent_eval_workflow_plan_filters_completed_cases(monkeypatch):
    class FakeAgentEvalService:
        def __init__(self, _session, _user_id):
            pass

        async def filter_test_cases_needing_execution(self, _run_id, test_case_ids):
            return [case_id for case_id in test_case_ids if case_id == "case_2"]

        async def list_run_test_case_ids(self, _run_id):
            return ["case_1", "case_2", "case_3"]

    monkeypatch.setattr(handlers, "AgentEvalService", FakeAgentEvalService)

    result = await handlers.agent_eval_test_case_plan(
        {"runId": "run_1", "userId": "user_1"},
        session=None,
    )

    assert result == {
        "filtered": 2,
        "runId": "run_1",
        "testCaseIds": ["case_2"],
        "totalCandidates": 3,
        "userId": "user_1",
    }


@pytest.mark.asyncio
async def test_agent_eval_finalize_summarizes_run_topics(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    updates = []

    async def fake_list_run_topics(_run_id):
        return [
            SimpleNamespace(score=1.0, result={"passed": True}, status="completed"),
            SimpleNamespace(score=0.25, result={"passed": False}, status="failed"),
            SimpleNamespace(score=None, result=None, status="pending"),
        ]

    async def fake_update_run_status(run_id, status, *, error=None, results=None):
        updates.append({"results": results, "run_id": run_id, "status": status})

    monkeypatch.setattr(service, "list_run_topics", fake_list_run_topics)
    monkeypatch.setattr(service, "update_run_status", fake_update_run_status)

    result = await service.finalize_run_from_topics("run_1")

    assert result == {
        "avg_score": 0.4167,
        "completed": 1,
        "external": 0,
        "failed": 1,
        "passed": 1,
        "pending": 1,
        "runId": "run_1",
        "running": 0,
        "status": "running",
        "success": True,
        "timeout": 0,
        "total": 3,
    }
    assert updates == [
        {
            "results": {
                "avg_score": 0.4167,
                "completed": 1,
                "external": 0,
                "failed": 1,
                "passed": 1,
                "pending": 1,
                "running": 0,
                "timeout": 0,
                "total": 3,
            },
            "run_id": "run_1",
            "status": "running",
        }
    ]


@pytest.mark.asyncio
async def test_finalize_eval_workflow_uses_topic_summary(monkeypatch):
    class FakeAgentEvalService:
        def __init__(self, _session, _user_id):
            pass

        async def finalize_run_from_topics(self, run_id, *, status=None):
            return {"runId": run_id, "status": status or "completed", "success": True, "total": 2}

    monkeypatch.setattr(handlers, "AgentEvalService", FakeAgentEvalService)

    assert await handlers.finalize_eval_workflow({"runId": "run_1", "userId": "user_1"}, None) == {
        "runId": "run_1",
        "status": "completed",
        "success": True,
        "total": 2,
    }


@pytest.mark.asyncio
async def test_trajectory_workflow_routes_to_dedicated_agent_executor(monkeypatch):
    calls = []

    class FakeAgentEvalService:
        def __init__(self, _session, user_id):
            calls.append({"user_id": user_id})

        async def execute_agent_trajectory(self, payload):
            calls.append({"payload": payload, "type": "agent"})
            return {"status": "started", "success": True, "topicId": "topic_1"}

    monkeypatch.setattr(handlers, "AgentEvalService", FakeAgentEvalService)

    result = await handlers.run_agent_trajectory_workflow(
        {"runId": "run_1", "testCaseId": "case_1", "userId": "user_1"},
        None,
    )

    assert result == {"status": "started", "success": True, "topicId": "topic_1"}
    assert calls == [
        {"user_id": "user_1"},
        {
            "payload": {"runId": "run_1", "testCaseId": "case_1", "userId": "user_1"},
            "type": "agent",
        },
    ]


@pytest.mark.asyncio
async def test_thread_workflow_routes_to_dedicated_thread_executor(monkeypatch):
    calls = []

    class FakeAgentEvalService:
        def __init__(self, _session, user_id):
            calls.append({"user_id": user_id})

        async def execute_thread_trajectory(self, payload):
            calls.append({"payload": payload, "type": "thread"})
            return {"status": "started", "success": True, "threadId": "thread_1", "topicId": "topic_1"}

    monkeypatch.setattr(handlers, "AgentEvalService", FakeAgentEvalService)

    result = await handlers.run_thread_trajectory_workflow(
        {
            "runId": "run_1",
            "testCaseId": "case_1",
            "threadId": "thread_1",
            "topicId": "topic_1",
            "userId": "user_1",
        },
        None,
    )

    assert result == {"status": "started", "success": True, "threadId": "thread_1", "topicId": "topic_1"}
    assert calls[-1]["type"] == "thread"


@pytest.mark.asyncio
async def test_completion_workflows_record_trajectory_and_thread(monkeypatch):
    calls = []

    class FakeAgentEvalService:
        def __init__(self, _session, user_id):
            calls.append({"user_id": user_id})

        async def record_trajectory_completion(self, payload):
            calls.append({"payload": payload, "type": "trajectory-complete"})
            return {"allDone": True, "success": True}

        async def record_thread_completion(self, payload):
            calls.append({"payload": payload, "type": "thread-complete"})
            return {"allRunDone": False, "allThreadsDone": True, "success": True}

    monkeypatch.setattr(handlers, "AgentEvalService", FakeAgentEvalService)

    assert await handlers.on_trajectory_complete_workflow(
        {"runId": "run_1", "testCaseId": "case_1", "userId": "user_1"},
        None,
    ) == {"allDone": True, "success": True}
    assert await handlers.on_thread_complete_workflow(
        {
            "runId": "run_1",
            "testCaseId": "case_1",
            "threadId": "thread_1",
            "topicId": "topic_1",
            "userId": "user_1",
        },
        None,
    ) == {"allRunDone": False, "allThreadsDone": True, "success": True}
    assert [call["type"] for call in calls if "type" in call] == [
        "trajectory-complete",
        "thread-complete",
    ]


@pytest.mark.asyncio
async def test_record_trajectory_completion_marks_external(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    run_topic = SimpleNamespace(status="running", test_case_id="case_1", topic_id="topic_1")
    updates = []

    async def fake_find_run_topic(_run_id, _test_case_id):
        return run_topic

    async def fake_get_test_case(_test_case_id):
        return SimpleNamespace(expected_output="Paris", metadata_={"evalMode": "external"})

    async def fake_evaluate(_run_id, _test_case, _output):
        return {
            "awaitingExternalEval": True,
            "passed": None,
            "score": None,
            "status": "external",
        }

    async def fake_update_run_topic_by_run_and_topic(run_id, topic_id, **kwargs):
        updates.append({"run_id": run_id, "topic_id": topic_id, **kwargs})

    async def fake_finalize(_run_id):
        return False

    monkeypatch.setattr(service, "find_run_topic_by_run_and_test_case", fake_find_run_topic)
    monkeypatch.setattr(service, "get_test_case", fake_get_test_case)
    monkeypatch.setattr(service, "evaluate_output_for_case", fake_evaluate)
    monkeypatch.setattr(service, "update_run_topic_by_run_and_topic", fake_update_run_topic_by_run_and_topic)
    monkeypatch.setattr(service, "_finalize_if_all_topics_done", fake_finalize)

    assert await service.record_trajectory_completion(
        {
            "operationId": "op_1",
            "output": "The answer is Paris.",
            "reason": "done",
            "runId": "run_1",
            "status": "done",
            "testCaseId": "case_1",
        }
    ) == {"allDone": False, "external": True, "success": True}
    assert updates == [
        {
            "result": {
                "awaitingExternalEval": True,
                "completionReason": "done",
                "cost": None,
                "duration": None,
                "llmCalls": None,
                "operationId": "op_1",
                "output": "The answer is Paris.",
                "steps": None,
                "tokens": None,
                "toolCalls": None,
            },
            "run_id": "run_1",
            "status": "external",
            "topic_id": "topic_1",
        }
    ]


@pytest.mark.asyncio
async def test_resume_workflows_route_to_dedicated_resume_executors(monkeypatch):
    calls = []

    class FakeAgentEvalService:
        def __init__(self, _session, user_id):
            calls.append({"user_id": user_id})

        async def execute_resumed_agent_trajectory(self, payload):
            calls.append({"payload": payload, "type": "resume-agent"})
            return {"status": "started", "success": True, "topicId": "topic_1"}

        async def execute_resumed_thread_trajectory(self, payload):
            calls.append({"payload": payload, "type": "resume-thread"})
            return {"status": "started", "success": True, "threadId": "thread_1", "topicId": "topic_1"}

    monkeypatch.setattr(handlers, "AgentEvalService", FakeAgentEvalService)

    assert await handlers.resume_agent_trajectory_workflow(
        {"runId": "run_1", "testCaseId": "case_1", "topicId": "topic_1", "userId": "user_1"},
        None,
    ) == {"status": "started", "success": True, "topicId": "topic_1"}
    assert await handlers.resume_thread_trajectory_workflow(
        {
            "runId": "run_1",
            "testCaseId": "case_1",
            "threadId": "thread_1",
            "topicId": "topic_1",
            "userId": "user_1",
        },
        None,
    ) == {"status": "started", "success": True, "threadId": "thread_1", "topicId": "topic_1"}
    assert [call["type"] for call in calls if "type" in call] == ["resume-agent", "resume-thread"]


@pytest.mark.asyncio
async def test_can_resume_agent_trajectory_enforces_status_and_max_steps(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    run = SimpleNamespace(config={"k": 1, "maxSteps": 3}, status="running")
    run_topic = SimpleNamespace(result={"steps": 2}, status="timeout", topic_id="topic_1")

    async def fake_get_run(_run_id):
        return run

    async def fake_find_run_topic(_run_id, _test_case_id):
        return run_topic

    monkeypatch.setattr(service, "get_run", fake_get_run)
    monkeypatch.setattr(service, "find_run_topic_by_run_and_test_case", fake_find_run_topic)

    assert await service.can_resume_trajectory(run_id="run_1", test_case_id="case_1") == {
        "canResume": True,
    }

    run_topic.result = {"steps": 3}
    assert await service.can_resume_trajectory(run_id="run_1", test_case_id="case_1") == {
        "canResume": False,
        "reason": "Resume limit reached",
    }


@pytest.mark.asyncio
async def test_can_resume_thread_trajectory_requires_matching_resumable_thread(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    run = SimpleNamespace(config={"k": 2, "maxSteps": 5}, status="running")
    run_topic = SimpleNamespace(
        result={"threads": [{"status": "error", "threadId": "thread_1"}]},
        status="failed",
        topic_id="topic_1",
    )
    thread = SimpleNamespace(metadata_={"steps": 4}, topic_id="topic_1", type="eval")

    async def fake_get_run(_run_id):
        return run

    async def fake_find_run_topic(_run_id, _test_case_id):
        return run_topic

    async def fake_get_thread(_thread_id):
        return thread

    monkeypatch.setattr(service, "get_run", fake_get_run)
    monkeypatch.setattr(service, "find_run_topic_by_run_and_test_case", fake_find_run_topic)
    monkeypatch.setattr(service, "_get_thread", fake_get_thread)

    assert await service.can_resume_trajectory(
        run_id="run_1",
        test_case_id="case_1",
        thread_id="thread_1",
    ) == {"canResume": True}

    run_topic.result = {"threads": [{"status": "passed", "threadId": "thread_1"}]}
    assert await service.can_resume_trajectory(
        run_id="run_1",
        test_case_id="case_1",
        thread_id="thread_1",
    ) == {"canResume": False, "reason": "Trajectory is not resumable"}


def test_reset_resumed_thread_result_only_resets_target_thread():
    result = {
        "threads": [
            {"score": 0.1, "status": "error", "threadId": "thread_1"},
            {"score": 1, "status": "passed", "threadId": "thread_2"},
        ]
    }

    assert _reset_resumed_thread_result(result, "thread_1") == [
        {"status": "running", "threadId": "thread_1"},
        {"score": 1, "status": "passed", "threadId": "thread_2"},
    ]


@pytest.mark.asyncio
async def test_execute_test_case_uses_pass_k_thread_fanout(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    run = SimpleNamespace(config={"k": 2}, id="run_1")
    test_case = SimpleNamespace(id="case_1")
    calls = []

    async def fake_get_run(_run_id):
        return run

    async def fake_get_test_case(_test_case_id):
        return test_case

    async def fake_execute_multi_thread_trajectory(**kwargs):
        calls.append(kwargs)
        return {"status": "started", "success": True, "threadIds": ["thread_1", "thread_2"]}

    monkeypatch.setattr(service, "get_run", fake_get_run)
    monkeypatch.setattr(service, "get_test_case", fake_get_test_case)
    monkeypatch.setattr(service, "execute_multi_thread_trajectory", fake_execute_multi_thread_trajectory)

    assert await service.execute_test_case("run_1", "case_1") == {
        "status": "started",
        "success": True,
        "threadIds": ["thread_1", "thread_2"],
    }
    assert calls == [{"k": 2, "run_id": "run_1", "test_case_id": "case_1"}]


@pytest.mark.asyncio
async def test_execute_multi_thread_trajectory_creates_threads_and_triggers_workflows(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, item):
            self.added.append(item)

        async def flush(self):
            return None

    session = FakeSession()
    service = AgentEvalService(session=session, user_id="user_1")
    run = SimpleNamespace(config={"k": 2}, id="run_1")
    test_case = SimpleNamespace(id="case_1")
    run_topic = SimpleNamespace(result={"operationId": "op_parent"}, topic_id="topic_1")
    updates = []
    triggers = []

    async def fake_load(_run_id, _test_case_id):
        return run, test_case, run_topic

    async def fake_ensure(_run_topic, _run, _test_case):
        return "topic_1"

    async def fake_update_run_status(run_id, status, **kwargs):
        updates.append({"run_id": run_id, "status": status, "type": "run"})

    async def fake_update_run_topic_by_run_and_topic(run_id, topic_id, **kwargs):
        updates.append({"run_id": run_id, "topic_id": topic_id, "type": "topic", **kwargs})

    async def fake_trigger(payload):
        triggers.append(payload)
        return {"accepted": True, "workflowName": "agent-eval-run/run-thread-trajectory"}

    monkeypatch.setattr(service, "_load_trajectory_target", fake_load)
    monkeypatch.setattr(service, "_ensure_run_topic_topic", fake_ensure)
    monkeypatch.setattr(service, "update_run_status", fake_update_run_status)
    monkeypatch.setattr(service, "update_run_topic_by_run_and_topic", fake_update_run_topic_by_run_and_topic)
    monkeypatch.setattr(service, "_trigger_run_thread_trajectory", fake_trigger)

    result = await service.execute_multi_thread_trajectory(run_id="run_1", test_case_id="case_1", k=2)

    assert result["status"] == "started"
    assert result["success"] is True
    assert result["topicId"] == "topic_1"
    assert len(result["threadIds"]) == 2
    assert len(session.added) == 2
    assert all(thread.type == "eval" and thread.topic_id == "topic_1" for thread in session.added)
    result_update = next(update for update in updates if update.get("result"))
    assert result_update["result"] == {
        "operationId": "op_parent",
        "threads": [
            {"status": "running", "threadId": result["threadIds"][0]},
            {"status": "running", "threadId": result["threadIds"][1]},
        ],
    }
    assert triggers == [
        {
            "runId": "run_1",
            "testCaseId": "case_1",
            "threadId": result["threadIds"][0],
            "topicId": "topic_1",
            "userId": "user_1",
        },
        {
            "runId": "run_1",
            "testCaseId": "case_1",
            "threadId": result["threadIds"][1],
            "topicId": "topic_1",
            "userId": "user_1",
        },
    ]


@pytest.mark.asyncio
async def test_timeout_handler_marks_expired_topics_and_finalizes(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    now = datetime(2026, 5, 23, 12, 0, 0)
    run = SimpleNamespace(config={"timeout": 1000}, started_at=now - timedelta(seconds=10), status="running")
    topics = [
        SimpleNamespace(
            created_at=now - timedelta(seconds=5),
            id="rt_1",
            result={"operationId": "op_1"},
            status="running",
            topic_id="topic_1",
        )
    ]
    updates = []
    finalized = []
    interrupted = []

    async def fake_get_run(_run_id):
        return run

    async def fake_list_run_topics(_run_id):
        return topics

    async def fake_update_run_topic_by_run_and_topic(run_id, topic_id, **kwargs):
        updates.append({"run_id": run_id, "topic_id": topic_id, **kwargs})

    async def fake_finalize(run_id, *, status=None):
        finalized.append({"run_id": run_id, "status": status})
        return {"runId": run_id, "status": "failed", "success": True}

    async def fake_interrupt(operation_id):
        interrupted.append({"operation_id": operation_id, "user_id": service._uid})

    monkeypatch.setattr(service, "get_run", fake_get_run)
    monkeypatch.setattr(service, "list_run_topics", fake_list_run_topics)
    monkeypatch.setattr(service, "update_run_topic_by_run_and_topic", fake_update_run_topic_by_run_and_topic)
    monkeypatch.setattr(service, "finalize_run_from_topics", fake_finalize)
    monkeypatch.setattr(service, "_interrupt_operation", fake_interrupt)

    result = await service.check_and_handle_run_timeout("run_1", now=now)

    assert result == {
        "changed": True,
        "finalized": True,
        "interruptedOperationIds": ["op_1"],
        "runId": "run_1",
        "timedOut": 1,
    }
    assert interrupted == [{"operation_id": "op_1", "user_id": "user_1"}]
    assert updates[0]["status"] == "timeout"
    assert updates[0]["score"] == 0.0
    assert updates[0]["result"]["completionReason"] == "timeout"
    assert updates[0]["result"]["duration"] == 5000
    assert finalized == [{"run_id": "run_1", "status": None}]


@pytest.mark.asyncio
async def test_timeout_handler_skips_runs_inside_timeout_window(monkeypatch):
    service = AgentEvalService(session=None, user_id="user_1")
    now = datetime(2026, 5, 23, 12, 0, 0)
    run = SimpleNamespace(config={"timeout": 10_000}, started_at=now - timedelta(seconds=1), status="running")

    async def fake_get_run(_run_id):
        return run

    monkeypatch.setattr(service, "get_run", fake_get_run)

    assert await service.check_and_handle_run_timeout("run_1", now=now) == {
        "changed": False,
        "reason": "run-within-timeout-window",
        "runId": "run_1",
        "timedOut": 0,
    }
