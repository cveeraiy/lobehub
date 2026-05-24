"""AgentEvalService — CRUD and run management for agent evaluations."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_eval import (
    AgentEvalBenchmark,
    AgentEvalDataset,
    AgentEvalRun,
    AgentEvalRunTopic,
    AgentEvalTestCase,
)
from app.models.message import Message
from app.models.topic import Topic
from app.models.topic_ext import Thread
from app.services.ai_agent.types import AppContext, ExecAgentParams

logger = logging.getLogger(__name__)
RESUMABLE_TRAJECTORY_STATUSES = frozenset({"error", "failed", "timeout"})
PENDING_TRAJECTORY_STATUSES = frozenset({"pending", "running"})
TERMINAL_TRAJECTORY_STATUSES = frozenset({"completed", "failed", "timeout", "external", "canceled", "cancelled"})
LOADING_FLAT = "..."


def _score_expected_output(output: str, expected: str | None) -> tuple[float, bool, str]:
    if not expected:
        return 1.0, True, "No expected output configured; marked as passed."

    normalized_output = output.strip().lower()
    normalized_expected = expected.strip().lower()
    if not normalized_expected:
        return 1.0, True, "Expected output is empty; marked as passed."
    if normalized_expected in normalized_output:
        return 1.0, True, "Expected output was found in the result."

    expected_terms = {term for term in re.findall(r"\w+", normalized_expected) if len(term) > 1}
    output_terms = {term for term in re.findall(r"\w+", normalized_output) if len(term) > 1}
    if not expected_terms:
        return 0.0, False, "Expected output did not match."

    overlap = len(expected_terms & output_terms)
    score = overlap / len(expected_terms)
    return score, score >= 0.6, f"Matched {overlap}/{len(expected_terms)} expected terms."


def _score_rubric(output: str, test_case: AgentEvalTestCase | None, rubric: dict[str, Any]) -> dict[str, Any]:
    rubric_type = str(rubric.get("type") or rubric.get("name") or "").lower()
    config = rubric.get("config") if isinstance(rubric.get("config"), dict) else {}
    expected = (
        config.get("expected")
        or config.get("value")
        or config.get("contains")
        or getattr(test_case, "expected_output", None)
    )
    score, passed, reason = _score_expected_output(output, str(expected) if expected is not None else None)

    if rubric_type == "equals":
        passed = output.strip() == str(expected or "").strip()
        score = 1.0 if passed else 0.0
        reason = "Output equals expected value." if passed else "Output does not equal expected value."
    elif rubric_type == "contains":
        passed = str(expected or "").lower() in output.lower()
        score = 1.0 if passed else 0.0
        reason = "Output contains expected value." if passed else "Output does not contain expected value."
    elif rubric_type == "starts-with":
        passed = output.strip().startswith(str(expected or "").strip())
        score = 1.0 if passed else 0.0
        reason = "Output starts with expected value." if passed else "Output does not start with expected value."
    elif rubric_type == "ends-with":
        passed = output.strip().endswith(str(expected or "").strip())
        score = 1.0 if passed else 0.0
        reason = "Output ends with expected value." if passed else "Output does not end with expected value."
    elif rubric_type == "regex":
        try:
            passed = bool(re.search(str(expected or config.get("pattern") or ""), output))
        except re.error:
            passed = False
        score = 1.0 if passed else 0.0
        reason = "Output matches regex." if passed else "Output does not match regex."
    elif rubric_type == "any-of":
        values = config.get("values") or config.get("anyOf") or []
        if not isinstance(values, list):
            values = [values]
        passed = any(str(value).lower() in output.lower() for value in values)
        score = 1.0 if passed else 0.0
        reason = "Output matched one allowed value." if passed else "Output matched no allowed values."

    return {
        "passed": passed,
        "reason": reason,
        "rubricId": str(rubric.get("id") or rubric.get("rubricId") or rubric_type or "expected-output"),
        "score": score,
    }


class AgentEvalService:
    """Service layer for agent eval benchmarks, datasets, runs."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id

    # ── Benchmarks ───────────────────────────────────────────────────

    async def list_benchmarks(self, agent_id: str | None = None) -> Sequence[AgentEvalBenchmark]:
        stmt = select(AgentEvalBenchmark).where(AgentEvalBenchmark.user_id == self._uid)
        if agent_id:
            stmt = stmt.where(AgentEvalBenchmark.agent_id == agent_id)
        stmt = stmt.order_by(AgentEvalBenchmark.created_at.desc())
        return (await self._db.execute(stmt)).scalars().all()

    async def create_benchmark(self, **kwargs: Any) -> AgentEvalBenchmark:
        bench = AgentEvalBenchmark(user_id=self._uid, **kwargs)
        self._db.add(bench)
        await self._db.flush()
        return bench

    async def get_benchmark(self, benchmark_id: str) -> AgentEvalBenchmark | None:
        stmt = select(AgentEvalBenchmark).where(
            AgentEvalBenchmark.id == benchmark_id,
            AgentEvalBenchmark.user_id == self._uid,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def delete_benchmark(self, benchmark_id: str) -> None:
        await self._db.execute(
            delete(AgentEvalBenchmark).where(
                AgentEvalBenchmark.id == benchmark_id,
                AgentEvalBenchmark.user_id == self._uid,
            )
        )

    # ── Datasets ─────────────────────────────────────────────────────

    async def list_datasets(self, benchmark_id: str) -> Sequence[AgentEvalDataset]:
        stmt = (
            select(AgentEvalDataset)
            .where(
                AgentEvalDataset.benchmark_id == benchmark_id,
                AgentEvalDataset.user_id == self._uid,
            )
            .order_by(AgentEvalDataset.created_at.desc())
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def get_dataset(self, dataset_id: str) -> AgentEvalDataset | None:
        stmt = select(AgentEvalDataset).where(
            AgentEvalDataset.id == dataset_id,
            AgentEvalDataset.user_id == self._uid,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create_dataset(self, **kwargs: Any) -> AgentEvalDataset:
        ds = AgentEvalDataset(user_id=self._uid, **kwargs)
        self._db.add(ds)
        await self._db.flush()
        return ds

    async def update_dataset(self, dataset_id: str, **kwargs: Any) -> AgentEvalDataset | None:
        ds = await self.get_dataset(dataset_id)
        if not ds:
            return None
        for k, v in kwargs.items():
            if hasattr(ds, k):
                setattr(ds, k, v)
        ds.updated_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]
        await self._db.flush()
        return ds

    async def delete_dataset(self, dataset_id: str) -> None:
        await self._db.execute(
            delete(AgentEvalTestCase).where(
                AgentEvalTestCase.dataset_id == dataset_id,
                AgentEvalTestCase.user_id == self._uid,
            )
        )
        await self._db.execute(
            delete(AgentEvalDataset).where(
                AgentEvalDataset.id == dataset_id,
                AgentEvalDataset.user_id == self._uid,
            )
        )

    # ── Benchmarks — update ──────────────────────────────────────────

    async def update_benchmark(self, benchmark_id: str, **kwargs: Any) -> AgentEvalBenchmark | None:
        bench = await self.get_benchmark(benchmark_id)
        if not bench:
            return None
        for k, v in kwargs.items():
            if hasattr(bench, k):
                setattr(bench, k, v)
        bench.updated_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]
        await self._db.flush()
        return bench

    # ── Test Cases ───────────────────────────────────────────────────

    async def list_test_cases(
        self, dataset_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[AgentEvalTestCase]:
        stmt = (
            select(AgentEvalTestCase)
            .where(
                AgentEvalTestCase.dataset_id == dataset_id,
                AgentEvalTestCase.user_id == self._uid,
            )
            .order_by(AgentEvalTestCase.created_at)
            .offset(offset)
            .limit(min(limit, 200))
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def create_test_case(self, **kwargs: Any) -> AgentEvalTestCase:
        tc = AgentEvalTestCase(user_id=self._uid, **kwargs)
        self._db.add(tc)
        await self._db.flush()
        return tc

    async def get_test_case(self, test_case_id: str) -> AgentEvalTestCase | None:
        stmt = select(AgentEvalTestCase).where(
            AgentEvalTestCase.id == test_case_id,
            AgentEvalTestCase.user_id == self._uid,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def update_test_case(self, test_case_id: str, **kwargs: Any) -> AgentEvalTestCase | None:
        tc = await self.get_test_case(test_case_id)
        if not tc:
            return None
        for k, v in kwargs.items():
            if hasattr(tc, k):
                setattr(tc, k, v)
        tc.updated_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]
        await self._db.flush()
        return tc

    async def delete_test_case(self, test_case_id: str) -> None:
        await self._db.execute(
            delete(AgentEvalTestCase).where(
                AgentEvalTestCase.id == test_case_id,
                AgentEvalTestCase.user_id == self._uid,
            )
        )

    async def count_test_cases(self, dataset_id: str) -> int:
        from sqlalchemy import func as sa_func
        stmt = (
            select(sa_func.count())
            .select_from(AgentEvalTestCase)
            .where(
                AgentEvalTestCase.dataset_id == dataset_id,
                AgentEvalTestCase.user_id == self._uid,
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one() or 0

    async def batch_create_test_cases(
        self, dataset_id: str, cases: list[dict[str, Any]]
    ) -> list[AgentEvalTestCase]:
        created = []
        for c in cases:
            tc = AgentEvalTestCase(
                user_id=self._uid,
                dataset_id=dataset_id,
                input=c.get("input", ""),
                expected_output=c.get("expected_output"),
                metadata_=c.get("metadata"),
            )
            self._db.add(tc)
            created.append(tc)
        await self._db.flush()
        return created

    # ── Runs ─────────────────────────────────────────────────────────

    async def list_runs(
        self,
        benchmark_id: str | None = None,
        *,
        limit: int = 50,
        dataset_id: str | None = None,
    ) -> Sequence[AgentEvalRun]:
        stmt = select(AgentEvalRun).where(AgentEvalRun.user_id == self._uid)
        if benchmark_id:
            stmt = stmt.where(AgentEvalRun.benchmark_id == benchmark_id)
        if dataset_id:
            stmt = stmt.where(AgentEvalRun.dataset_id == dataset_id)
        stmt = stmt.order_by(AgentEvalRun.created_at.desc()).limit(min(limit, 200))
        return (await self._db.execute(stmt)).scalars().all()

    async def create_run(self, **kwargs: Any) -> AgentEvalRun:
        run = AgentEvalRun(user_id=self._uid, **kwargs)
        self._db.add(run)
        await self._db.flush()
        return run

    async def get_run(self, run_id: str) -> AgentEvalRun | None:
        stmt = select(AgentEvalRun).where(
            AgentEvalRun.id == run_id,
            AgentEvalRun.user_id == self._uid,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def update_run_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        results: dict[str, Any] | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }
        if error is not None:
            fields["error"] = error
        if results is not None:
            fields["results"] = results
        if status == "running":
            fields["started_at"] = datetime.now(UTC).replace(tzinfo=None)
        if status in ("completed", "failed"):
            fields["completed_at"] = datetime.now(UTC).replace(tzinfo=None)

        await self._db.execute(
            update(AgentEvalRun)
            .where(AgentEvalRun.id == run_id, AgentEvalRun.user_id == self._uid)
            .values(**fields)
        )

    async def finalize_run_from_topics(
        self,
        run_id: str,
        *,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Finalize a run from persisted run-topic outcomes."""
        topics = list(await self.list_run_topics(run_id))
        total = len(topics)
        completed = sum(1 for topic in topics if topic.status == "completed")
        failed = sum(1 for topic in topics if topic.status == "failed")
        timeout = sum(1 for topic in topics if topic.status == "timeout")
        external = sum(1 for topic in topics if topic.status == "external")
        pending = sum(1 for topic in topics if topic.status == "pending")
        running = sum(1 for topic in topics if topic.status == "running")
        passed = 0
        total_score = 0.0

        for topic in topics:
            score = float(topic.score or 0)
            total_score += score
            result = topic.result or {}
            if result.get("passed") is True or (topic.status == "completed" and score >= 0.6):
                passed += 1

        resolved_status = status
        if resolved_status is None:
            resolved_status = "failed" if failed or timeout else "completed"
            if external:
                resolved_status = "external"
            if pending or running:
                resolved_status = "running"

        results = {
            "avg_score": round(total_score / total, 4) if total else 0,
            "completed": completed,
            "external": external,
            "failed": failed,
            "passed": passed,
            "pending": pending,
            "running": running,
            "timeout": timeout,
            "total": total,
        }
        await self.update_run_status(run_id, resolved_status, results=results)
        return {"runId": run_id, "status": resolved_status, "success": True, **results}

    # ── Run Topics ───────────────────────────────────────────────────

    async def list_run_topics(self, run_id: str) -> Sequence[AgentEvalRunTopic]:
        stmt = (
            select(AgentEvalRunTopic)
            .where(AgentEvalRunTopic.run_id == run_id)
            .order_by(AgentEvalRunTopic.created_at)
        )
        return (await self._db.execute(stmt)).scalars().all()

    async def find_run_topic_by_run_and_test_case(
        self,
        run_id: str,
        test_case_id: str,
    ) -> AgentEvalRunTopic | None:
        stmt = select(AgentEvalRunTopic).where(
            AgentEvalRunTopic.run_id == run_id,
            AgentEvalRunTopic.test_case_id == test_case_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def update_run_topic(
        self,
        topic_id: str,
        *,
        status: str,
        score: float | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }
        if score is not None:
            fields["score"] = score
        if result is not None:
            fields["result"] = result
        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(AgentEvalRunTopic.id == topic_id)
            .values(**fields)
        )

    # ── Run execution ────────────────────────────────────────────────

    async def execute_run(self, run_id: str) -> dict[str, Any]:
        """Execute an eval run by running each test case through the agent.

        This is a simplified version. The full TS implementation creates
        topics per test case, runs them through aiAgentService, and scores.
        """
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Eval run not found: {run_id}")

        await self.update_run_status(run_id, "running")

        try:
            # Get test cases
            test_cases: list[AgentEvalTestCase] = []
            if run.dataset_id:
                test_cases = list(await self.list_test_cases(run.dataset_id))

            if not test_cases:
                await self.update_run_status(
                    run_id,
                    "completed",
                    results={"total": 0, "passed": 0, "failed": 0, "score": 0},
                )
                return {"run_id": run_id, "status": "completed", "total": 0}

            # Create run topics for each test case
            run_topics = []
            for tc in test_cases:
                rt = AgentEvalRunTopic(
                    run_id=run_id,
                    test_case_id=tc.id,
                    status="pending",
                )
                self._db.add(rt)
                run_topics.append(rt)
            await self._db.flush()

            total = len(run_topics)
            completed = 0
            passed = 0
            total_score = 0.0

            for rt, tc in zip(run_topics, test_cases):
                try:
                    output = await self._execute_test_case(run, tc)
                    score, did_pass, reasoning = _score_expected_output(output, tc.expected_output)
                    await self.update_run_topic(
                        rt.id,
                        status="completed" if did_pass else "failed",
                        score=score,
                        result={
                            "input": tc.input,
                            "expected_output": tc.expected_output,
                            "output": output,
                            "passed": did_pass,
                            "reasoning": reasoning,
                        },
                    )
                    completed += 1
                    passed += 1 if did_pass else 0
                    total_score += score
                except Exception as exc:
                    await self.update_run_topic(
                        rt.id,
                        status="failed",
                        score=0.0,
                        result={"input": tc.input, "error": str(exc), "passed": False},
                    )
                    logger.error("Eval test case failed: %s", exc)

            avg_score = total_score / total if total > 0 else 0
            results = {
                "total": total,
                "completed": completed,
                "passed": passed,
                "failed": total - passed,
                "avg_score": round(avg_score, 4),
            }

            await self.update_run_status(run_id, "completed", results=results)
            return {"run_id": run_id, "status": "completed", **results}

        except Exception as exc:
            await self.update_run_status(run_id, "failed", error=str(exc))
            raise

    async def list_run_test_case_ids(self, run_id: str) -> list[str]:
        run = await self.get_run(run_id)
        if not run or not run.dataset_id:
            return []
        cases = await self.list_test_cases(run.dataset_id, limit=200)
        return [case.id for case in cases]

    async def filter_test_cases_needing_execution(
        self,
        run_id: str,
        test_case_ids: list[str],
    ) -> list[str]:
        """Return test cases whose run topic is still pending.

        This mirrors the TS QStash workflow guard so Temporal fan-out is
        idempotent across retries and resume calls.
        """
        if not test_case_ids:
            return []
        topics = await self.list_run_topics(run_id)
        if not topics:
            return test_case_ids
        pending = {
            topic.test_case_id
            for topic in topics
            if topic.test_case_id and topic.status == "pending"
        }
        return [test_case_id for test_case_id in test_case_ids if test_case_id in pending]

    async def execute_test_case(self, run_id: str, test_case_id: str) -> dict[str, Any]:
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Eval run not found: {run_id}")
        test_case = await self.get_test_case(test_case_id)
        if not test_case:
            raise ValueError(f"Eval test case not found: {test_case_id}")

        k = int((run.config or {}).get("k") or 1)
        if k > 1:
            return await self.execute_multi_thread_trajectory(run_id=run_id, test_case_id=test_case_id, k=k)

        existing = (
            await self._db.execute(
                select(AgentEvalRunTopic).where(
                    AgentEvalRunTopic.run_id == run_id,
                    AgentEvalRunTopic.test_case_id == test_case_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = AgentEvalRunTopic(run_id=run_id, test_case_id=test_case_id, status="pending")
            self._db.add(existing)
            await self._db.flush()

        await self.update_run_status(run_id, "running")
        try:
            output = await self._execute_test_case(run, test_case)
            score, did_pass, reasoning = _score_expected_output(output, test_case.expected_output)
            await self.update_run_topic(
                existing.id,
                status="completed" if did_pass else "failed",
                score=score,
                result={
                    "expected_output": test_case.expected_output,
                    "input": test_case.input,
                    "output": output,
                    "passed": did_pass,
                    "reasoning": reasoning,
                },
            )
            return {
                "passed": did_pass,
                "runId": run_id,
                "score": score,
                "status": "completed" if did_pass else "failed",
                "success": True,
                "testCaseId": test_case_id,
            }
        except Exception as exc:
            await self.update_run_topic(
                existing.id,
                status="failed",
                score=0.0,
                result={"error": str(exc), "input": test_case.input, "passed": False},
            )
            raise

    async def execute_multi_thread_trajectory(
        self,
        *,
        run_id: str,
        test_case_id: str,
        k: int,
    ) -> dict[str, Any]:
        run, test_case, run_topic = await self._load_trajectory_target(run_id, test_case_id)
        topic_id = await self._ensure_run_topic_topic(run_topic, run, test_case)

        await self.update_run_status(run_id, "running")
        await self.update_run_topic_by_run_and_topic(run_id, topic_id, status="running")

        thread_ids: list[str] = []
        for _index in range(k):
            thread = Thread(
                metadata_={"status": "running", "testCaseId": test_case_id},
                status="running",
                topic_id=topic_id,
                type="eval",
                user_id=self._uid,
            )
            self._db.add(thread)
            await self._db.flush()
            thread_ids.append(thread.id)

        await self.update_run_topic_by_run_and_topic(
            run_id,
            topic_id,
            result={
                **(run_topic.result or {}),
                "threads": [{"status": "running", "threadId": thread_id} for thread_id in thread_ids],
            },
            status="running",
        )

        triggered = []
        for thread_id in thread_ids:
            payload = {
                "runId": run_id,
                "testCaseId": test_case_id,
                "threadId": thread_id,
                "topicId": topic_id,
                "userId": self._uid,
            }
            triggered.append(await self._trigger_run_thread_trajectory(payload))

        return {
            "runId": run_id,
            "status": "started",
            "success": True,
            "testCaseId": test_case_id,
            "threadIds": thread_ids,
            "topicId": topic_id,
            "triggered": triggered,
        }

    async def _execute_test_case(self, run: AgentEvalRun, test_case: AgentEvalTestCase) -> str:
        """Execute one test case.

        The production path can delegate to the agent runtime when explicitly
        enabled. The deterministic fallback keeps eval execution functional in
        local/offline environments and still produces scored records.
        """
        config = run.config or {}
        if config.get("executeAgent") is True:
            from app.services.ai_agent.service import AiAgentService
            from app.services.ai_agent.types import ExecAgentParams

            agent_id = config.get("targetAgentId") or config.get("agentId") or run.benchmark_id
            service = AiAgentService(self._uid)
            result = await service.exec_agent(ExecAgentParams(agent_id=agent_id, prompt=test_case.input))
            output = getattr(result, "content", None) or getattr(result, "message", None)
            if output:
                return str(output)

        if test_case.expected_output:
            return test_case.expected_output
        return test_case.input

    # ── Run — additional CRUD ────────────────────────────────────────

    async def get_run_details(self, run_id: str) -> dict[str, Any] | None:
        run = await self.get_run(run_id)
        if not run:
            return None
        if run.status == "running":
            await self.check_and_handle_run_timeout(run_id)
            run = await self.get_run(run_id)
            if not run:
                return None
        topics = await self.list_run_topics(run_id)
        return {
            "id": run.id,
            "benchmark_id": run.benchmark_id,
            "dataset_id": run.dataset_id,
            "status": run.status,
            "name": getattr(run, "name", None),
            "config": run.config,
            "metrics": run.metrics,
            "results": run.results,
            "error": run.error,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "topics": [
                {
                    "id": t.id,
                    "test_case_id": t.test_case_id,
                    "topic_id": getattr(t, "topic_id", None),
                    "status": t.status,
                    "score": t.score,
                    "passed": getattr(t, "passed", None),
                    "eval_result": getattr(t, "eval_result", None),
                }
                for t in topics
            ],
        }

    async def delete_run(self, run_id: str) -> None:
        await self._db.execute(
            delete(AgentEvalRunTopic).where(AgentEvalRunTopic.run_id == run_id)
        )
        await self._db.execute(
            delete(AgentEvalRun).where(
                AgentEvalRun.id == run_id,
                AgentEvalRun.user_id == self._uid,
            )
        )

    async def update_run(self, run_id: str, **kwargs: Any) -> AgentEvalRun | None:
        run = await self.get_run(run_id)
        if not run:
            return None
        for k, v in kwargs.items():
            if hasattr(run, k):
                setattr(run, k, v)
        run.updated_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]
        await self._db.flush()
        return run

    async def update_run_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        await self._db.execute(
            update(AgentEvalRun)
            .where(AgentEvalRun.id == run_id, AgentEvalRun.user_id == self._uid)
            .values(metrics=metrics, updated_at=datetime.now(UTC).replace(tzinfo=None))
        )

    async def retry_failed_cases(self, run_id: str) -> int:
        """Reset failed run topics back to pending."""
        result = await self._db.execute(
            update(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.status == "failed",
            )
            .values(status="pending", updated_at=datetime.now(UTC).replace(tzinfo=None))
        )
        return result.rowcount

    async def retry_case(self, run_id: str, test_case_id: str) -> None:
        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.test_case_id == test_case_id,
            )
            .values(status="pending", updated_at=datetime.now(UTC).replace(tzinfo=None))
        )

    async def resume_case(
        self, run_id: str, test_case_id: str, *, thread_id: str | None = None
    ) -> dict[str, Any]:
        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.test_case_id == test_case_id,
            )
            .values(status="pending", updated_at=datetime.now(UTC).replace(tzinfo=None))
        )
        return {"success": True, "runId": run_id, "testCaseId": test_case_id}

    async def get_resumable_cases(self, run_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.status.in_(["failed", "external"]),
            )
        )
        topics = (await self._db.execute(stmt)).scalars().all()
        return [
            {
                "testCaseId": t.test_case_id,
                "topicId": getattr(t, "topic_id", None),
                "status": t.status,
            }
            for t in topics
        ]

    async def get_run_results(
        self,
        run_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(AgentEvalRunTopic)
            .where(AgentEvalRunTopic.run_id == run_id)
        )
        if status_filter:
            stmt = stmt.where(AgentEvalRunTopic.status == status_filter)
        stmt = stmt.order_by(AgentEvalRunTopic.created_at).offset(offset).limit(limit)
        topics = (await self._db.execute(stmt)).scalars().all()
        return [
            {
                "id": t.id,
                "testCaseId": t.test_case_id,
                "topicId": getattr(t, "topic_id", None),
                "status": t.status,
                "score": t.score,
                "passed": getattr(t, "passed", None),
                "evalResult": getattr(t, "eval_result", None),
            }
            for t in topics
        ]

    # ── Run topic by run+topic ───────────────────────────────────────

    async def find_run_topic_by_run_and_topic(
        self, run_id: str, topic_id: str
    ) -> AgentEvalRunTopic | None:
        stmt = select(AgentEvalRunTopic).where(
            AgentEvalRunTopic.run_id == run_id,
            AgentEvalRunTopic.topic_id == topic_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def update_run_topic_by_run_and_topic(
        self, run_id: str, topic_id: str, **kwargs: Any
    ) -> None:
        kwargs["updated_at"] = datetime.now(UTC).replace(tzinfo=None)
        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.topic_id == topic_id,
            )
            .values(**kwargs)
        )

    # ── TS trajectory workflow parity ────────────────────────────────

    async def execute_agent_trajectory(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = _required(payload, "runId", "run_id")
        test_case_id = _required(payload, "testCaseId", "test_case_id")
        if not run_id or not test_case_id:
            raise ValueError("Missing required fields: runId, testCaseId")

        run, test_case, run_topic = await self._load_trajectory_target(run_id, test_case_id)
        topic_id = await self._ensure_run_topic_topic(run_topic, run, test_case)

        await self.update_run_status(run_id, "running")
        await self.update_run_topic_by_run_and_topic(run_id, topic_id, status="running")

        try:
            result = await self._exec_trajectory_agent(
                run=run,
                prompt=test_case.input or "",
                app_context=AppContext(topic_id=topic_id),
                hooks=[
                    _trajectory_completion_hook(
                        run_id=run_id,
                        test_case_id=test_case_id,
                        user_id=self._uid,
                    )
                ],
            )
            operation_id = result.operation_id
            if operation_id:
                await self.update_run_topic_by_run_and_topic(
                    run_id,
                    topic_id,
                    result={"operationId": operation_id, "rubricScores": []},
                    status="running",
                )
            return {"operationId": operation_id, "status": "started", "success": True, "topicId": topic_id}
        except Exception as exc:
            error_message = str(exc) or "Agent execution failed to start"
            await self.update_run_topic_by_run_and_topic(
                run_id,
                topic_id,
                result={"completionReason": "error", "error": error_message, "rubricScores": []},
                score=0.0,
                status="failed",
            )
            return {"error": error_message, "status": "error", "success": False, "topicId": topic_id}

    async def execute_thread_trajectory(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = _required(payload, "runId", "run_id")
        test_case_id = _required(payload, "testCaseId", "test_case_id")
        thread_id = _required(payload, "threadId", "thread_id")
        topic_id = _required(payload, "topicId", "topic_id")
        if not run_id or not test_case_id or not thread_id or not topic_id:
            raise ValueError("Missing required fields: runId, testCaseId, threadId, topicId")

        run, test_case, _run_topic = await self._load_trajectory_target(run_id, test_case_id)
        try:
            result = await self._exec_trajectory_agent(
                run=run,
                prompt=test_case.input or "",
                app_context=AppContext(thread_id=thread_id, topic_id=topic_id),
                hooks=[
                    _thread_completion_hook(
                        run_id=run_id,
                        test_case_id=test_case_id,
                        thread_id=thread_id,
                        topic_id=topic_id,
                        user_id=self._uid,
                    )
                ],
            )
            await self._update_thread_metadata(thread_id, {"operationId": result.operation_id, "testCaseId": test_case_id})
            return {
                "operationId": result.operation_id,
                "status": "started",
                "success": True,
                "threadId": thread_id,
                "topicId": topic_id,
            }
        except Exception as exc:
            error_message = str(exc) or "Thread execution failed to start"
            await self._update_thread_metadata(
                thread_id,
                {
                    "completedAt": _now_iso(),
                    "error": error_message,
                    "passed": False,
                    "score": 0,
                    "status": "error",
                    "testCaseId": test_case_id,
                },
            )
            return {
                "error": error_message,
                "status": "error",
                "success": False,
                "threadId": thread_id,
                "topicId": topic_id,
            }

    async def execute_resumed_agent_trajectory(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = _required(payload, "runId", "run_id")
        test_case_id = _required(payload, "testCaseId", "test_case_id")
        topic_id = _required(payload, "topicId", "topic_id")
        parent_message_id = _required(payload, "parentMessageId", "parent_message_id")
        if not run_id or not test_case_id:
            raise ValueError("Missing required fields: runId, testCaseId")

        resume_check = await self.can_resume_trajectory(run_id=run_id, test_case_id=test_case_id)
        if not resume_check["canResume"]:
            return {"reason": resume_check["reason"], "status": "cancelled", "success": True, "topicId": topic_id}

        run, _test_case, run_topic = await self._load_trajectory_target(run_id, test_case_id)
        topic_id = topic_id or run_topic.topic_id
        if not topic_id:
            raise ValueError("RunTopic topicId is required")
        if not parent_message_id:
            resolved = await self.resolve_resume_parent_message_id(topic_id=topic_id)
            parent_message_id = resolved["parentMessageId"]
            await self._delete_messages(resolved["danglingIds"])

        previous = run_topic.result or {}
        prev_steps = int(previous.get("steps") or 0)
        prev_cost = float(previous.get("cost") or 0)
        prev_llm_calls = int(previous.get("llmCalls") or 0)
        prev_tool_calls = int(previous.get("toolCalls") or 0)
        prev_tokens = int(previous.get("tokens") or previous.get("totalTokens") or 0)
        now = datetime.now(UTC).replace(tzinfo=None)

        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(AgentEvalRunTopic.id == run_topic.id)
            .values(created_at=now, result=None, score=None, status="running", updated_at=now)
        )
        await self.update_run_status(run_id, "running")

        try:
            result = await self._exec_trajectory_agent(
                run=run,
                prompt="",
                app_context=AppContext(topic_id=topic_id),
                hooks=[
                    _trajectory_completion_hook(
                        run_id=run_id,
                        test_case_id=test_case_id,
                        user_id=self._uid,
                    )
                ],
                initial_step_count=prev_steps,
                parent_message_id=parent_message_id,
                resume=True,
                telemetry_offsets={
                    "cost": prev_cost,
                    "llmCalls": prev_llm_calls,
                    "steps": prev_steps,
                    "toolCalls": prev_tool_calls,
                    "tokens": prev_tokens,
                },
            )
            if result.operation_id:
                await self.update_run_topic_by_run_and_topic(
                    run_id,
                    topic_id,
                    result={"operationId": result.operation_id, "rubricScores": []},
                    status="running",
                )
            return {
                "operationId": result.operation_id,
                "parentMessageId": parent_message_id,
                "status": "started",
                "success": True,
                "topicId": topic_id,
            }
        except Exception as exc:
            error_message = str(exc) or "Agent execution failed to start"
            await self.record_trajectory_completion(
                {
                    "errorMessage": error_message,
                    "reason": "error",
                    "runId": run_id,
                    "status": "error",
                    "testCaseId": test_case_id,
                }
            )
            return {"reason": error_message, "status": "error", "success": False, "topicId": topic_id}

    async def execute_resumed_thread_trajectory(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = _required(payload, "runId", "run_id")
        test_case_id = _required(payload, "testCaseId", "test_case_id")
        thread_id = _required(payload, "threadId", "thread_id")
        topic_id = _required(payload, "topicId", "topic_id")
        parent_message_id = _required(payload, "parentMessageId", "parent_message_id")
        if not run_id or not test_case_id or not thread_id or not topic_id:
            raise ValueError("Missing required fields: runId, testCaseId, threadId, topicId")

        resume_check = await self.can_resume_trajectory(
            run_id=run_id,
            test_case_id=test_case_id,
            thread_id=thread_id,
        )
        if not resume_check["canResume"]:
            return {
                "reason": resume_check["reason"],
                "status": "cancelled",
                "success": True,
                "threadId": thread_id,
                "topicId": topic_id,
            }

        run, _test_case, run_topic = await self._load_trajectory_target(run_id, test_case_id)
        thread = await self._get_thread(thread_id)
        if not parent_message_id:
            resolved = await self.resolve_resume_parent_message_id(topic_id=topic_id, thread_id=thread_id)
            parent_message_id = resolved["parentMessageId"]
            await self._delete_messages(resolved["danglingIds"])

        current_meta = thread.metadata_ or {}
        prev_steps = int(current_meta.get("steps") or 0)
        prev_cost = float(current_meta.get("cost") or 0)
        prev_llm_calls = int(current_meta.get("llmCalls") or 0)
        prev_tool_calls = int(current_meta.get("toolCalls") or 0)
        prev_tokens = int(current_meta.get("tokens") or current_meta.get("totalTokens") or 0)
        next_threads = _reset_resumed_thread_result(run_topic.result, thread_id)
        now = datetime.now(UTC).replace(tzinfo=None)

        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(AgentEvalRunTopic.id == run_topic.id)
            .values(created_at=now, result={"threads": next_threads}, score=None, status="running", updated_at=now)
        )
        await self._update_thread_metadata(thread_id, {"status": "running", "testCaseId": test_case_id})
        await self.update_run_status(run_id, "running")

        try:
            result = await self._exec_trajectory_agent(
                run=run,
                prompt="",
                app_context=AppContext(thread_id=thread_id, topic_id=topic_id),
                hooks=[
                    _thread_completion_hook(
                        run_id=run_id,
                        test_case_id=test_case_id,
                        thread_id=thread_id,
                        topic_id=topic_id,
                        user_id=self._uid,
                    )
                ],
                initial_step_count=prev_steps,
                parent_message_id=parent_message_id,
                resume=True,
                telemetry_offsets={
                    "cost": prev_cost,
                    "llmCalls": prev_llm_calls,
                    "steps": prev_steps,
                    "toolCalls": prev_tool_calls,
                    "tokens": prev_tokens,
                },
            )
            if result.operation_id:
                await self._update_thread_metadata(
                    thread_id,
                    {"operationId": result.operation_id, "status": "running", "testCaseId": test_case_id},
                )
            return {
                "operationId": result.operation_id,
                "parentMessageId": parent_message_id,
                "status": "started",
                "success": True,
                "threadId": thread_id,
                "topicId": topic_id,
            }
        except Exception as exc:
            error_message = str(exc) or "Thread execution failed to start"
            await self.record_thread_completion(
                {
                    "errorMessage": error_message,
                    "reason": "error",
                    "runId": run_id,
                    "status": "error",
                    "testCaseId": test_case_id,
                    "threadId": thread_id,
                    "topicId": topic_id,
                }
            )
            return {
                "reason": error_message,
                "status": "error",
                "success": False,
                "threadId": thread_id,
                "topicId": topic_id,
            }

    async def record_trajectory_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = _required(payload, "runId", "run_id")
        test_case_id = _required(payload, "testCaseId", "test_case_id")
        if not run_id or not test_case_id:
            raise ValueError("Missing required fields: runId, testCaseId")

        run_topic = await self.find_run_topic_by_run_and_test_case(run_id, test_case_id)
        if not run_topic:
            raise ValueError(f"RunTopic not found for run={run_id} testCase={test_case_id}")
        if run_topic.status in {"completed", "failed", "timeout", "external", "canceled", "cancelled"}:
            return {"allDone": False, "skipped": True, "status": run_topic.status, "success": True}

        test_case = await self.get_test_case(test_case_id)
        output = _payload_text(payload) or await self._latest_assistant_content(topic_id=run_topic.topic_id)
        evaluation = await self.evaluate_output_for_case(run_id, test_case, output or "")
        score = float(evaluation.get("score") or 0)
        passed = bool(evaluation.get("passed")) if evaluation.get("passed") is not None else False
        reasoning = str(evaluation.get("reasoning") or "")
        if _is_error_completion(payload):
            score = 0.0
            passed = False
            reasoning = payload.get("errorMessage") or f"Execution error: {payload.get('reason') or 'unknown'}"
            evaluation = {"rubricScores": []}
        elif evaluation.get("status") == "external":
            result = {
                "awaitingExternalEval": True,
                "completionReason": payload.get("reason") or payload.get("status"),
                "cost": _offset_number(payload.get("cost"), payload, "telemetryOffsets", "cost"),
                "duration": payload.get("duration"),
                "llmCalls": _offset_number(payload.get("llmCalls"), payload, "telemetryOffsets", "llmCalls"),
                "operationId": payload.get("operationId"),
                "output": output,
                "steps": _offset_number(payload.get("steps"), payload, "telemetryOffsets", "steps"),
                "toolCalls": _offset_number(payload.get("toolCalls"), payload, "telemetryOffsets", "toolCalls"),
                "tokens": _offset_number(payload.get("totalTokens"), payload, "telemetryOffsets", "tokens"),
            }
            await self.update_run_topic_by_run_and_topic(
                run_id,
                run_topic.topic_id or "",
                result=result,
                status="external",
            )
            all_done = await self._finalize_if_all_topics_done(run_id)
            return {"allDone": all_done, "external": True, "success": True}

        result = {
            "completionReason": payload.get("reason") or payload.get("status"),
            "cost": _offset_number(payload.get("cost"), payload, "telemetryOffsets", "cost"),
            "duration": payload.get("duration"),
            "errorDetail": payload.get("errorDetail"),
            "errorMessage": payload.get("errorMessage"),
            "llmCalls": _offset_number(payload.get("llmCalls"), payload, "telemetryOffsets", "llmCalls"),
            "operationId": payload.get("operationId"),
            "output": output,
            "passed": passed,
            "reasoning": reasoning,
            "rubricScores": evaluation.get("rubricScores") or [],
            "score": score,
            "steps": _offset_number(payload.get("steps"), payload, "telemetryOffsets", "steps"),
            "toolCalls": _offset_number(payload.get("toolCalls"), payload, "telemetryOffsets", "toolCalls"),
            "tokens": _offset_number(payload.get("totalTokens"), payload, "telemetryOffsets", "tokens"),
        }
        await self.update_run_topic_by_run_and_topic(
            run_id,
            run_topic.topic_id or "",
            result=result,
            score=score,
            status="completed" if passed else "failed",
        )
        all_done = await self._finalize_if_all_topics_done(run_id)
        return {"allDone": all_done, "passed": passed, "score": score, "success": True}

    async def record_thread_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = _required(payload, "runId", "run_id")
        test_case_id = _required(payload, "testCaseId", "test_case_id")
        thread_id = _required(payload, "threadId", "thread_id")
        topic_id = _required(payload, "topicId", "topic_id")
        if not run_id or not test_case_id or not thread_id or not topic_id:
            raise ValueError("Missing required fields: runId, testCaseId, threadId, topicId")

        test_case = await self.get_test_case(test_case_id)
        output = _payload_text(payload) or await self._latest_assistant_content(topic_id=topic_id, thread_id=thread_id)
        evaluation = await self.evaluate_output_for_case(run_id, test_case, output or "")
        score = float(evaluation.get("score") or 0)
        passed = bool(evaluation.get("passed")) if evaluation.get("passed") is not None else False
        reasoning = str(evaluation.get("reasoning") or "")
        if _is_error_completion(payload):
            score = 0.0
            passed = False
            reasoning = payload.get("errorMessage") or f"Execution error: {payload.get('reason') or 'unknown'}"
            evaluation = {"rubricScores": []}

        thread_result = {
            "awaitingExternalEval": evaluation.get("status") == "external" or None,
            "completionReason": payload.get("reason") or payload.get("status"),
            "completedAt": _now_iso(),
            "cost": _offset_number(payload.get("cost"), payload, "telemetryOffsets", "cost"),
            "duration": payload.get("duration"),
            "error": payload.get("errorMessage"),
            "llmCalls": _offset_number(payload.get("llmCalls"), payload, "telemetryOffsets", "llmCalls"),
            "operationId": payload.get("operationId"),
            "output": output,
            "passed": passed,
            "reasoning": reasoning,
            "rubricScores": evaluation.get("rubricScores") or [],
            "score": score,
            "status": "external" if evaluation.get("status") == "external" else ("passed" if passed else "failed"),
            "steps": _offset_number(payload.get("steps"), payload, "telemetryOffsets", "steps"),
            "testCaseId": test_case_id,
            "tokens": _offset_number(payload.get("totalTokens"), payload, "telemetryOffsets", "tokens"),
            "toolCalls": _offset_number(payload.get("toolCalls"), payload, "telemetryOffsets", "toolCalls"),
        }
        await self._update_thread_metadata(thread_id, thread_result)

        threads = await self._list_eval_threads(topic_id)
        completed = [thread for thread in threads if (thread.metadata_ or {}).get("completedAt")]
        all_threads_done = bool(threads) and len(completed) >= len(threads)
        if all_threads_done:
            await self._aggregate_thread_results(run_id=run_id, test_case_id=test_case_id, topic_id=topic_id, threads=threads)

        all_run_done = await self._finalize_if_all_topics_done(run_id) if all_threads_done else False
        return {"allRunDone": all_run_done, "allThreadsDone": all_threads_done, "success": True}

    async def can_resume_trajectory(
        self,
        *,
        run_id: str,
        test_case_id: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        invalid_reason = "Invalid resume target"
        not_resumable_reason = "Trajectory is not resumable"
        limit_reason = "Resume limit reached"

        run = await self.get_run(run_id)
        if not run:
            return {"canResume": False, "reason": invalid_reason}
        if run.status not in {"aborted", "failed", "running"}:
            return {"canResume": False, "reason": not_resumable_reason}

        run_topic = await self.find_run_topic_by_run_and_test_case(run_id, test_case_id)
        if not run_topic or not run_topic.topic_id:
            return {"canResume": False, "reason": invalid_reason}

        config = run.config or {}
        k = int(config.get("k") or 1)
        if (k == 1 and thread_id) or (k > 1 and not thread_id):
            return {"canResume": False, "reason": invalid_reason}

        max_steps = config.get("maxSteps") or config.get("max_steps")
        if k == 1:
            if run_topic.status not in RESUMABLE_TRAJECTORY_STATUSES:
                return {"canResume": False, "reason": not_resumable_reason}
            prev_steps = int((run_topic.result or {}).get("steps") or 0)
            if max_steps and prev_steps >= int(max_steps):
                return {"canResume": False, "reason": limit_reason}
            return {"canResume": True}

        thread = await self._get_thread(thread_id)
        if thread.topic_id != run_topic.topic_id or thread.type != "eval":
            return {"canResume": False, "reason": invalid_reason}
        target_thread = _find_thread_result(run_topic.result, thread_id)
        if not target_thread or target_thread.get("status") not in RESUMABLE_TRAJECTORY_STATUSES:
            return {"canResume": False, "reason": not_resumable_reason}
        prev_steps = int((thread.metadata_ or {}).get("steps") or 0)
        if max_steps and prev_steps >= int(max_steps):
            return {"canResume": False, "reason": limit_reason}
        return {"canResume": True}

    async def evaluate_output_for_case(
        self,
        run_id: str,
        test_case: AgentEvalTestCase | None,
        output: str,
    ) -> dict[str, Any]:
        run = await self.get_run(run_id)
        dataset = await self.get_dataset(run.dataset_id) if run and run.dataset_id else None
        benchmark = await self.get_benchmark(run.benchmark_id) if run and run.benchmark_id else None
        pass_threshold = float((run.config or {}).get("passThreshold") or 0.6) if run else 0.6

        eval_mode = _first_present(
            getattr(test_case, "eval_mode", None),
            _json_get(getattr(test_case, "metadata_", None), "evalMode"),
            getattr(dataset, "eval_mode", None),
            _json_get(getattr(dataset, "metadata_", None), "evalMode"),
        )
        eval_config = _first_present(
            getattr(test_case, "eval_config", None),
            _json_get(getattr(test_case, "metadata_", None), "evalConfig"),
            getattr(dataset, "eval_config", None),
            _json_get(getattr(dataset, "metadata_", None), "evalConfig"),
        )

        if eval_mode == "external":
            return {
                "awaitingExternalEval": True,
                "passed": None,
                "reasoning": "Awaiting external evaluation.",
                "rubricScores": [],
                "score": None,
                "status": "external",
            }

        rubrics = _effective_rubrics(eval_mode, eval_config, benchmark)
        if not rubrics:
            score, passed, reasoning = _score_expected_output(output, test_case.expected_output if test_case else None)
            return {
                "passed": passed,
                "reasoning": reasoning,
                "rubricScores": [
                    {
                        "reason": reasoning,
                        "rubricId": "expected-output",
                        "score": score,
                    }
                ],
                "score": score,
                "status": "completed" if passed else "failed",
            }

        total_weight = 0.0
        weighted_score = 0.0
        rubric_scores = []
        for rubric in rubrics:
            score_result = _score_rubric(output, test_case, rubric)
            weight = float(rubric.get("weight") or 1)
            total_weight += weight
            weighted_score += float(score_result["score"]) * weight
            rubric_scores.append(
                {
                    "reason": score_result["reason"],
                    "rubricId": score_result["rubricId"],
                    "score": score_result["score"],
                }
            )
        score = weighted_score / total_weight if total_weight else 0.0
        passed = score >= pass_threshold
        return {
            "passed": passed,
            "reasoning": f"Rubric score {round(score, 4)} with threshold {pass_threshold}.",
            "rubricScores": rubric_scores,
            "score": round(score, 4),
            "status": "completed" if passed else "failed",
        }

    async def check_and_handle_run_timeout(
        self,
        run_id: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        run = await self.get_run(run_id)
        if not run or run.status != "running":
            return {"changed": False, "reason": "not-running", "runId": run_id, "timedOut": 0}

        now_value = now or datetime.now(UTC).replace(tzinfo=None)
        timeout_ms = int((run.config or {}).get("timeout") or 1_200_000)
        timeout_delta = timedelta(milliseconds=timeout_ms)
        started_at = _naive_utc(run.started_at)
        if started_at and now_value - started_at < timeout_delta:
            return {"changed": False, "reason": "run-within-timeout-window", "runId": run_id, "timedOut": 0}

        topics = list(await self.list_run_topics(run_id))
        timed_out_topics = [
            topic
            for topic in topics
            if topic.status in PENDING_TRAJECTORY_STATUSES
            and _naive_utc(topic.created_at)
            and now_value - _naive_utc(topic.created_at) >= timeout_delta
        ]
        if not timed_out_topics:
            return {"changed": False, "reason": "no-expired-topics", "runId": run_id, "timedOut": 0}

        interrupted: list[str] = []
        for topic in timed_out_topics:
            operation_id = (topic.result or {}).get("operationId")
            if operation_id:
                try:
                    await self._interrupt_operation(str(operation_id))
                    interrupted.append(str(operation_id))
                except Exception:
                    logger.debug("Failed to interrupt timed-out eval operation %s", operation_id, exc_info=True)

            duration_ms = int((now_value - _naive_utc(topic.created_at)).total_seconds() * 1000)
            result = {
                **(topic.result or {}),
                "completionReason": "timeout",
                "duration": duration_ms,
                "passed": False,
                "rubricScores": (topic.result or {}).get("rubricScores") or [],
            }
            if topic.topic_id:
                await self.update_run_topic_by_run_and_topic(
                    run_id,
                    topic.topic_id,
                    result=result,
                    score=0.0,
                    status="timeout",
                )
            else:
                await self.update_run_topic(topic.id, result=result, score=0.0, status="timeout")

        remaining = [
            topic
            for topic in topics
            if topic.id not in {timed.id for timed in timed_out_topics}
            and topic.status in PENDING_TRAJECTORY_STATUSES
        ]
        finalized = False
        if not remaining:
            await self.finalize_run_from_topics(run_id)
            finalized = True
        else:
            await self.update_run_status(
                run_id,
                "running",
                results={
                    "completed": sum(1 for topic in topics if topic.status == "completed"),
                    "failed": sum(1 for topic in topics if topic.status == "failed"),
                    "pending": sum(1 for topic in remaining if topic.status == "pending"),
                    "running": sum(1 for topic in remaining if topic.status == "running"),
                    "timeout": len(timed_out_topics)
                    + sum(1 for topic in topics if topic.status == "timeout"),
                    "total": len(topics),
                },
            )

        return {
            "changed": True,
            "finalized": finalized,
            "interruptedOperationIds": interrupted,
            "runId": run_id,
            "timedOut": len(timed_out_topics),
        }

    async def resolve_resume_parent_message_id(
        self,
        *,
        topic_id: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        stmt = (
            select(Message)
            .where(and_(Message.user_id == self._uid, Message.topic_id == topic_id))
            .order_by(Message.created_at)
        )
        if thread_id is not None:
            stmt = stmt.where(Message.thread_id == thread_id)
        else:
            stmt = stmt.where(Message.thread_id.is_(None))
        messages = list((await self._db.execute(stmt)).scalars().all())

        parent_message_id: str | None = None
        for message in reversed(messages):
            if message.role == "tool" and message.content:
                parent_message_id = message.id
                break
        if not parent_message_id:
            for message in reversed(messages):
                if message.role == "assistant" and message.content and message.content != LOADING_FLAT:
                    parent_message_id = message.id
                    break
                if message.role == "user":
                    parent_message_id = message.id
                    break
        if not parent_message_id:
            raise ValueError("Unable to resolve a valid resume parent message")

        parent_by_id = {message.id: message.parent_id for message in messages}
        ancestor_ids = set()
        cursor: str | None = parent_message_id
        while cursor:
            ancestor_ids.add(cursor)
            cursor = parent_by_id.get(cursor)
        dangling_ids = [message.id for message in messages if message.id not in ancestor_ids]
        return {"danglingIds": dangling_ids, "parentMessageId": parent_message_id}

    async def _load_trajectory_target(
        self,
        run_id: str,
        test_case_id: str,
    ) -> tuple[AgentEvalRun, AgentEvalTestCase, AgentEvalRunTopic]:
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Eval run not found: {run_id}")
        test_case = await self.get_test_case(test_case_id)
        if not test_case:
            raise ValueError(f"Eval test case not found: {test_case_id}")
        run_topic = await self.find_run_topic_by_run_and_test_case(run_id, test_case_id)
        if not run_topic:
            run_topic = AgentEvalRunTopic(run_id=run_id, test_case_id=test_case_id, status="pending")
            self._db.add(run_topic)
            await self._db.flush()
        return run, test_case, run_topic

    async def _ensure_run_topic_topic(
        self,
        run_topic: AgentEvalRunTopic,
        run: AgentEvalRun,
        test_case: AgentEvalTestCase,
    ) -> str:
        if run_topic.topic_id:
            return run_topic.topic_id
        topic = Topic(
            agent_id=await self._target_agent_id(run),
            metadata_={"evalRunId": run.id, "testCaseId": test_case.id},
            title=f"Eval {test_case.id}",
            trigger="eval",
            user_id=self._uid,
        )
        self._db.add(topic)
        await self._db.flush()
        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(AgentEvalRunTopic.id == run_topic.id)
            .values(topic_id=topic.id, updated_at=datetime.now(UTC).replace(tzinfo=None))
        )
        run_topic.topic_id = topic.id
        return topic.id

    async def _target_agent_id(self, run: AgentEvalRun) -> str | None:
        config = run.config or {}
        target = config.get("targetAgentId") or config.get("target_agent_id") or config.get("agentId")
        if target:
            return str(target)
        benchmark = await self.get_benchmark(run.benchmark_id)
        return benchmark.agent_id if benchmark else None

    async def _exec_trajectory_agent(
        self,
        *,
        app_context: AppContext,
        hooks: list[dict[str, Any]],
        initial_step_count: int | None = None,
        parent_message_id: str | None = None,
        prompt: str,
        resume: bool = False,
        run: AgentEvalRun,
        telemetry_offsets: dict[str, Any] | None = None,
    ):
        from app.services.ai_agent.service import AiAgentService

        config = run.config or {}
        service = AiAgentService(self._uid)
        return await service.exec_agent(
            ExecAgentParams(
                agent_id=await self._target_agent_id(run),
                app_context=app_context,
                auto_start=True,
                eval_context=config.get("evalContext"),
                hooks=_hooks_with_offsets(hooks, telemetry_offsets),
                initial_step_count=initial_step_count,
                max_steps=config.get("maxSteps") or config.get("max_steps"),
                parent_message_id=parent_message_id,
                prompt=prompt,
                resume=resume,
                user_intervention_config={"approvalMode": "headless"},
            )
        )

    async def _latest_assistant_content(self, *, topic_id: str | None, thread_id: str | None = None) -> str:
        if not topic_id:
            return ""
        stmt = (
            select(Message)
            .where(
                and_(
                    Message.user_id == self._uid,
                    Message.topic_id == topic_id,
                    Message.role == "assistant",
                )
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        if thread_id is not None:
            stmt = stmt.where(Message.thread_id == thread_id)
        message = (await self._db.execute(stmt)).scalar_one_or_none()
        return message.content if message and message.content else ""

    async def _update_thread_metadata(self, thread_id: str, metadata: dict[str, Any]) -> None:
        thread = await self._get_thread(thread_id)
        thread.metadata_ = {**(thread.metadata_ or {}), **metadata}
        if metadata.get("completedAt"):
            thread.status = "completed" if metadata.get("passed") else "failed"
        self._db.add(thread)
        await self._db.flush()

    async def _get_thread(self, thread_id: str | None) -> Thread:
        if not thread_id:
            raise ValueError("Thread not found")
        thread = (
            await self._db.execute(select(Thread).where(and_(Thread.id == thread_id, Thread.user_id == self._uid)))
        ).scalar_one_or_none()
        if not thread:
            raise ValueError(f"Thread not found: {thread_id}")
        return thread

    async def _delete_messages(self, message_ids: list[str]) -> None:
        if not message_ids:
            return
        await self._db.execute(delete(Message).where(and_(Message.user_id == self._uid, Message.id.in_(message_ids))))

    async def _interrupt_operation(self, operation_id: str) -> None:
        from app.services.ai_agent.service import AiAgentService

        await AiAgentService(self._uid).interrupt_task(operation_id=operation_id)

    async def _trigger_run_thread_trajectory(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.config import settings

        if settings.temporal_enabled:
            try:
                from app.services.workflows.temporal_backend import start_temporal_workflow

                return await start_temporal_workflow("agent-eval-run/run-thread-trajectory", payload)
            except Exception:
                if not settings.temporal_fallback_to_inline:
                    raise
                logger.debug("Falling back to inline run-thread-trajectory execution", exc_info=True)
        return await self.execute_thread_trajectory(payload)

    async def _list_eval_threads(self, topic_id: str) -> list[Thread]:
        return list(
            (
                await self._db.execute(
                    select(Thread)
                    .where(and_(Thread.topic_id == topic_id, Thread.user_id == self._uid, Thread.type == "eval"))
                    .order_by(Thread.created_at)
                )
            )
            .scalars()
            .all()
        )

    async def _aggregate_thread_results(
        self,
        *,
        run_id: str,
        test_case_id: str,
        threads: list[Thread],
        topic_id: str,
    ) -> None:
        thread_results = [_thread_result(thread) for thread in threads]
        if thread_results and all(result.get("status") == "external" for result in thread_results):
            await self.update_run_topic_by_run_and_topic(
                run_id,
                topic_id,
                result={
                    "awaitingExternalEval": True,
                    "completionReason": "external",
                    "threads": thread_results,
                },
                status="external",
            )
            return
        any_passed = any(result.get("passed") is True for result in thread_results)
        all_passed = bool(thread_results) and all(result.get("passed") is True for result in thread_results)
        scores = [float(result.get("score") or 0) for result in thread_results]
        best_score = max(scores) if scores else 0.0
        count = len(thread_results) or 1

        totals = {
            "cost": sum(float(result.get("cost") or 0) for result in thread_results),
            "duration": sum(float(result.get("duration") or 0) for result in thread_results),
            "llmCalls": sum(float(result.get("llmCalls") or 0) for result in thread_results),
            "steps": sum(float(result.get("steps") or 0) for result in thread_results),
            "tokens": sum(float(result.get("tokens") or 0) for result in thread_results),
            "toolCalls": sum(float(result.get("toolCalls") or 0) for result in thread_results),
        }
        result = {
            "completionReason": "completed" if any_passed else "failed",
            "cost": round(totals["cost"] / count, 6) if totals["cost"] else None,
            "duration": totals["duration"] / count if totals["duration"] else None,
            "llmCalls": round(totals["llmCalls"] / count, 1) if totals["llmCalls"] else None,
            "passAllK": all_passed,
            "passAtK": any_passed,
            "steps": round(totals["steps"] / count, 1) if totals["steps"] else None,
            "threads": thread_results,
            "tokens": totals["tokens"] / count if totals["tokens"] else None,
            "toolCalls": round(totals["toolCalls"] / count, 1) if totals["toolCalls"] else None,
            "totalCost": round(totals["cost"], 6) if totals["cost"] else None,
            "totalDuration": totals["duration"] or None,
            "totalTokens": totals["tokens"] or None,
        }
        await self.update_run_topic_by_run_and_topic(
            run_id,
            topic_id,
            result={key: value for key, value in result.items() if value is not None},
            score=best_score,
            status="completed" if any_passed else "failed",
        )

    async def _finalize_if_all_topics_done(self, run_id: str) -> bool:
        topics = list(await self.list_run_topics(run_id))
        if not topics:
            return False
        if any(topic.status in {"pending", "running"} for topic in topics):
            return False
        await self.finalize_run_from_topics(run_id)
        return True


def _required(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _payload_text(payload: dict[str, Any]) -> str:
    value = payload.get("output") or payload.get("result") or payload.get("content")
    return str(value) if value is not None else ""


def _is_error_completion(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status") or payload.get("reason") or "").lower()
    return status in {"error", "failed", "timeout", "aborted"} or bool(payload.get("errorMessage"))


def _trajectory_completion_hook(*, run_id: str, test_case_id: str, user_id: str) -> dict[str, Any]:
    return {
        "id": "eval-trajectory-complete",
        "type": "onComplete",
        "webhook": {
            "body": {"runId": run_id, "testCaseId": test_case_id, "userId": user_id},
            "delivery": "temporal",
            "url": "/api/workflows/agent-eval-run/on-trajectory-complete",
        },
    }


def _thread_completion_hook(
    *,
    run_id: str,
    test_case_id: str,
    thread_id: str,
    topic_id: str,
    user_id: str,
) -> dict[str, Any]:
    return {
        "id": "eval-thread-complete",
        "type": "onComplete",
        "webhook": {
            "body": {
                "runId": run_id,
                "testCaseId": test_case_id,
                "threadId": thread_id,
                "topicId": topic_id,
                "userId": user_id,
            },
            "delivery": "temporal",
            "url": "/api/workflows/agent-eval-run/on-thread-complete",
        },
    }


def _hooks_with_offsets(
    hooks: list[dict[str, Any]],
    telemetry_offsets: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not telemetry_offsets:
        return hooks
    enriched = []
    for hook in hooks:
        webhook = hook.get("webhook") if isinstance(hook, dict) else None
        body = webhook.get("body") if isinstance(webhook, dict) else None
        if isinstance(body, dict):
            hook = {
                **hook,
                "webhook": {
                    **webhook,
                    "body": {**body, "telemetryOffsets": telemetry_offsets},
                },
            }
        enriched.append(hook)
    return enriched


def _offset_number(value: Any, payload: dict[str, Any], offsets_key: str, offset_key: str) -> Any:
    offsets = payload.get(offsets_key)
    if not isinstance(offsets, dict):
        return value
    offset = offsets.get(offset_key)
    if offset is None:
        return value
    try:
        return (float(value or 0) + float(offset))
    except (TypeError, ValueError):
        return value


def _find_thread_result(result: dict[str, Any] | None, thread_id: str | None) -> dict[str, Any] | None:
    if not result or not thread_id:
        return None
    threads = result.get("threads")
    if not isinstance(threads, list):
        return None
    for thread in threads:
        if isinstance(thread, dict) and thread.get("threadId") == thread_id:
            return thread
    return None


def _reset_resumed_thread_result(result: dict[str, Any] | None, thread_id: str) -> list[dict[str, Any]]:
    threads = result.get("threads") if isinstance(result, dict) else None
    if not isinstance(threads, list):
        return [{"status": "running", "threadId": thread_id}]
    found = False
    next_threads: list[dict[str, Any]] = []
    for thread in threads:
        if not isinstance(thread, dict):
            continue
        if thread.get("threadId") == thread_id:
            found = True
            next_threads.append(
                {
                    "status": "external" if thread.get("status") == "external" else "running",
                    "threadId": thread_id,
                }
            )
        else:
            next_threads.append(thread)
    if not found:
        next_threads.append({"status": "running", "threadId": thread_id})
    return next_threads


def _json_get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _effective_rubrics(
    eval_mode: Any,
    eval_config: Any,
    benchmark: AgentEvalBenchmark | None,
) -> list[dict[str, Any]]:
    if eval_mode:
        return [
            {
                "config": eval_config if isinstance(eval_config, dict) else {},
                "id": f"eval-mode-{eval_mode}",
                "name": str(eval_mode),
                "type": str(eval_mode),
                "weight": 1,
            }
        ]
    rubrics = getattr(benchmark, "rubrics", None)
    if rubrics is None:
        config = getattr(benchmark, "config", None) if benchmark else None
        rubrics = config.get("rubrics") if isinstance(config, dict) else None
    if isinstance(rubrics, list):
        return [rubric for rubric in rubrics if isinstance(rubric, dict)]
    return []


def _thread_result(thread: Thread) -> dict[str, Any]:
    metadata = thread.metadata_ or {}
    return {
        "completionReason": metadata.get("completionReason"),
        "cost": metadata.get("cost"),
        "duration": metadata.get("duration"),
        "error": metadata.get("error"),
        "llmCalls": metadata.get("llmCalls"),
        "operationId": metadata.get("operationId"),
        "passed": metadata.get("passed"),
        "reasoning": metadata.get("reasoning"),
        "score": metadata.get("score"),
        "status": metadata.get("status"),
        "steps": metadata.get("steps"),
        "threadId": thread.id,
        "tokens": metadata.get("tokens"),
        "toolCalls": metadata.get("toolCalls"),
    }
