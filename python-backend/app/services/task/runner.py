"""TaskRunnerService — orchestrates a single task run.

Mirrors TS ``TaskRunnerService`` from ``src/server/services/taskRunner/index.ts``:
- Resolves the task, checks for running conflicts
- Times out stale topics
- Builds a task prompt
- Delegates to the agent runtime
- Updates task/topic state
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.task.service import TaskService

logger = logging.getLogger(__name__)


class TaskRunnerService:
    """Runs a task by delegating to the agent runtime."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id
        self._task_svc = TaskService(session, user_id)

    async def run_task(
        self,
        task_id: str,
        *,
        continue_topic_id: str | None = None,
        extra_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Run a task; returns operation result dict."""

        task = await self._task_svc.resolve(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        we_set_running = False

        try:
            if not task.assignee_agent_id:
                raise ValueError(
                    "Task has no assigned agent. Set assignee_agent_id before running."
                )

            existing_topics = await self._task_svc.find_topics(task.id)

            # Conflict detection
            if continue_topic_id:
                target = next(
                    (t for t in existing_topics if t.topic_id == continue_topic_id), None
                )
                if target and target.status == "running":
                    raise ValueError(
                        f"Topic {continue_topic_id} is already running."
                    )
            else:
                running = next(
                    (t for t in existing_topics if t.status == "running"), None
                )
                if running:
                    raise ValueError(
                        f"Task already has a running topic ({running.topic_id}). "
                        "Cancel it first or use continue_topic_id."
                    )

            # Auto-timeout stale topics
            if task.last_heartbeat_at and task.heartbeat_timeout:
                elapsed = (
                    datetime.now(timezone.utc) - task.last_heartbeat_at
                ).total_seconds()
                if elapsed > task.heartbeat_timeout:
                    await self._task_svc.timeout_running_topics(task.id)

            # Build prompt
            prompt = await self._build_prompt(task, extra_prompt)

            # Transition to running
            if task.status != "running":
                await self._task_svc.update_status(
                    task.id, "running", started_at=datetime.now(timezone.utc)
                )
                we_set_running = True
            elif task.error:
                await self._task_svc.update_fields(task.id, error=None)

            # ── Agent execution ──────────────────────────────────────
            # Import at runtime to avoid circular dependency
            from app.services.agent_runtime import AgentRuntimeService

            runtime = AgentRuntimeService()
            result = await runtime.create_and_run(
                agent_id=task.assignee_agent_id,
                user_id=self._uid,
                prompt=prompt,
                session=self._db,
            )

            operation_id = result.get("operation_id", "")
            topic_id = result.get("topic_id") or continue_topic_id

            # Update task/topic state
            if topic_id:
                if continue_topic_id:
                    await self._task_svc.update_topic_status(
                        task.id, continue_topic_id, "running"
                    )
                    await self._task_svc.update_current_topic(task.id, continue_topic_id)
                else:
                    await self._task_svc.increment_topic_count(task.id)
                    await self._task_svc.update_current_topic(task.id, topic_id)
                    await self._task_svc.add_topic(
                        task.id,
                        topic_id,
                        seq=(task.total_topics or 0) + 1,
                        operation_id=operation_id,
                    )

            await self._task_svc.update_heartbeat(task.id)

            return {
                **result,
                "task_id": task.id,
                "task_identifier": task.identifier,
            }

        except Exception as exc:
            if we_set_running:
                try:
                    refreshed = await self._task_svc.find_by_id(task.id)
                    if refreshed and refreshed.status == "running":
                        await self._task_svc.update_status(
                            task.id,
                            "paused",
                            error=str(exc),
                        )
                except Exception:
                    pass  # rollback itself failed
            raise

    async def _build_prompt(self, task: Any, extra_prompt: str | None) -> str:
        """Build the prompt injected into the agent runtime.

        Currently a simplified version — the full TS implementation
        pulls in briefs, comments, subtasks, dependencies, and documents.
        """
        parts: list[str] = []
        parts.append(f"## Task: {task.identifier}")
        if task.name:
            parts.append(f"**Name:** {task.name}")
        if task.description:
            parts.append(f"**Description:** {task.description}")
        parts.append(f"\n### Instruction\n{task.instruction}")

        # Context from previous topics
        topics = await self._task_svc.find_topics(task.id)
        if topics:
            parts.append("\n### Previous Topic Runs")
            for t in topics[-4:]:
                status_str = f"seq={t.seq} status={t.status}"
                parts.append(f"- Topic {t.topic_id}: {status_str}")

        # Briefs
        briefs = await self._task_svc.find_briefs(task.id)
        if briefs:
            parts.append("\n### Recent Briefs")
            for b in briefs[:5]:
                parts.append(f"- [{b.type}] {b.title}: {b.summary}")

        # Subtasks
        subtasks = await self._task_svc.find_subtasks(task.id)
        if subtasks:
            parts.append("\n### Subtasks")
            for s in subtasks:
                parts.append(f"- {s.identifier} ({s.status}): {s.name or 'unnamed'}")

        if extra_prompt:
            parts.append(f"\n### Additional Instructions\n{extra_prompt}")

        return "\n".join(parts)
