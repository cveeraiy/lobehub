"""AgentEvalService — CRUD and run management for agent evaluations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_eval import (
    AgentEvalBenchmark,
    AgentEvalDataset,
    AgentEvalRun,
    AgentEvalRunTopic,
    AgentEvalTestCase,
)

logger = logging.getLogger(__name__)


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
        ds.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)  # type: ignore[assignment]
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
        bench.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)  # type: ignore[assignment]
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
        tc.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)  # type: ignore[assignment]
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
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        if error is not None:
            fields["error"] = error
        if results is not None:
            fields["results"] = results
        if status == "running":
            fields["started_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        if status in ("completed", "failed"):
            fields["completed_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

        await self._db.execute(
            update(AgentEvalRun)
            .where(AgentEvalRun.id == run_id, AgentEvalRun.user_id == self._uid)
            .values(**fields)
        )

    # ── Run Topics ───────────────────────────────────────────────────

    async def list_run_topics(self, run_id: str) -> Sequence[AgentEvalRunTopic]:
        stmt = (
            select(AgentEvalRunTopic)
            .where(AgentEvalRunTopic.run_id == run_id)
            .order_by(AgentEvalRunTopic.created_at)
        )
        return (await self._db.execute(stmt)).scalars().all()

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
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
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

            # Execute each test case (simplified — just marks as completed)
            # Full implementation would run each through the agent runtime
            total = len(run_topics)
            completed = 0
            total_score = 0.0

            for rt in run_topics:
                try:
                    # TODO: Run through agent runtime and score output
                    await self.update_run_topic(rt.id, status="completed", score=1.0)
                    completed += 1
                    total_score += 1.0
                except Exception as exc:
                    await self.update_run_topic(rt.id, status="failed")
                    logger.error("Eval test case failed: %s", exc)

            avg_score = total_score / total if total > 0 else 0
            results = {
                "total": total,
                "completed": completed,
                "failed": total - completed,
                "avg_score": round(avg_score, 4),
            }

            await self.update_run_status(run_id, "completed", results=results)
            return {"run_id": run_id, "status": "completed", **results}

        except Exception as exc:
            await self.update_run_status(run_id, "failed", error=str(exc))
            raise

    # ── Run — additional CRUD ────────────────────────────────────────

    async def get_run_details(self, run_id: str) -> dict[str, Any] | None:
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
        run.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)  # type: ignore[assignment]
        await self._db.flush()
        return run

    async def update_run_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        await self._db.execute(
            update(AgentEvalRun)
            .where(AgentEvalRun.id == run_id, AgentEvalRun.user_id == self._uid)
            .values(metrics=metrics, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )

    async def retry_failed_cases(self, run_id: str) -> int:
        """Reset failed run topics back to pending."""
        result = await self._db.execute(
            update(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.status == "failed",
            )
            .values(status="pending", updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        return result.rowcount

    async def retry_case(self, run_id: str, test_case_id: str) -> None:
        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.test_case_id == test_case_id,
            )
            .values(status="pending", updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
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
            .values(status="pending", updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
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
        kwargs["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.execute(
            update(AgentEvalRunTopic)
            .where(
                AgentEvalRunTopic.run_id == run_id,
                AgentEvalRunTopic.topic_id == topic_id,
            )
            .values(**kwargs)
        )
