"""TaskLifecycleService — handles post-topic-complete state machine.

Mirrors TS ``TaskLifecycleService`` from
``src/server/services/taskLifecycle/index.ts``.

Flow: onTopicComplete → updateTopicStatus → synthesize brief →
      optionally schedule next topic
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_agent.service import SystemAgentService
from app.services.task.service import TaskService, TERMINAL_STATUSES
from app.services.task.scheduler import get_task_scheduler

logger = logging.getLogger(__name__)

HEARTBEAT_FAILURE_FUSE = 3


@dataclass
class TopicCompleteParams:
    task_id: str
    task_identifier: str
    operation_id: str
    reason: str  # 'done' | 'error' | 'interrupted'
    topic_id: str | None = None
    last_assistant_content: str | None = None
    error_message: str | None = None


class TaskLifecycleService:
    """Handles task state transitions triggered by topic completion."""

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id
        self._task_svc = TaskService(session, user_id)
        self._system_agent = SystemAgentService(session, user_id)

    async def on_topic_complete(self, params: TopicCompleteParams) -> None:
        """Core lifecycle method — called when a topic run finishes."""

        task = await self._task_svc.resolve(params.task_id)
        if task is None:
            logger.warning("on_topic_complete: task %s not found", params.task_id)
            return

        # Skip if task is in a terminal state
        if task.status in TERMINAL_STATUSES:
            logger.debug(
                "on_topic_complete: task %s already terminal (%s)",
                params.task_identifier,
                task.status,
            )
            return

        # Update heartbeat
        await self._task_svc.update_heartbeat(task.id)

        # Update topic status
        if params.topic_id:
            topic_status = "completed" if params.reason == "done" else params.reason
            await self._task_svc.update_topic_status(
                task.id, params.topic_id, topic_status
            )

        # Synthesize a brief when this topic is worth surfacing to the user.
        brief = await self._synthesize_brief(task, params)
        if brief:
            logger.info(
                "on_topic_complete: created brief '%s' for task %s",
                brief.title,
                params.task_identifier,
            )

        # Decide next action based on reason
        if params.reason == "done":
            await self._handle_done(task, params)
        elif params.reason == "error":
            await self._handle_error(task, params)
        elif params.reason == "interrupted":
            await self._task_svc.update_status(task.id, "paused")
        else:
            logger.warning(
                "on_topic_complete: unknown reason '%s' for task %s",
                params.reason,
                params.task_identifier,
            )

    async def _handle_done(self, task: Any, params: TopicCompleteParams) -> None:
        """Handle successful topic completion."""
        # Check if task has reached max topics
        if task.max_topics and (task.total_topics or 0) >= task.max_topics:
            await self._task_svc.update_status(
                task.id, "completed", completed_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            return

        # For heartbeat-mode tasks, schedule the next run
        if task.automation_mode == "heartbeat" and task.heartbeat_interval:
            scheduler = get_task_scheduler()
            await scheduler.schedule_next_topic(
                task_id=task.id,
                user_id=self._uid,
                delay=task.heartbeat_interval,
            )
            await self._task_svc.update_status(task.id, "scheduled")
        elif task.automation_mode == "schedule":
            await self._task_svc.update_status(task.id, "scheduled")
        else:
            # Non-automated task: pause after completion
            await self._task_svc.update_status(task.id, "paused")

    async def _handle_error(self, task: Any, params: TopicCompleteParams) -> None:
        """Handle topic error — count consecutive failures, pause if fuse blows."""
        # Count recent consecutive error topics
        topics = await self._task_svc.find_topics(task.id)
        recent_errors = 0
        for t in reversed(list(topics)):
            if t.status == "failed":
                recent_errors += 1
            else:
                break

        if recent_errors >= HEARTBEAT_FAILURE_FUSE:
            await self._task_svc.update_status(
                task.id,
                "paused",
                error=params.error_message or f"Consecutive failures ({recent_errors})",
            )
        elif task.automation_mode == "heartbeat" and task.heartbeat_interval:
            scheduler = get_task_scheduler()
            await scheduler.schedule_next_topic(
                task_id=task.id,
                user_id=self._uid,
                delay=task.heartbeat_interval,
            )
        else:
            await self._task_svc.update_status(
                task.id,
                "paused",
                error=params.error_message or "Topic failed",
            )

    async def _synthesize_brief(
        self, task: Any, params: TopicCompleteParams
    ) -> Any:
        """Create a user-facing brief for topic completion.

        Mirrors the TS rule layer where possible. Python does not yet persist
        the full TS briefDecision audit record, but it avoids surfacing trivial
        manual ticks and uses SystemAgentService for title/summary generation
        when available.
        """
        content = params.last_assistant_content or ""
        is_trivial = len(content.strip()) < 16

        if params.reason == "done" and task.automation_mode != "schedule" and is_trivial:
            if params.topic_id:
                await self._task_svc.update_topic_brief_decision(
                    task.id,
                    params.topic_id,
                    {
                        "emit": False,
                        "reason": "Trivial manual completion",
                        "source": "rule",
                    },
                )
            return None

        brief_type = "error" if params.reason == "error" else "result"
        priority = "urgent" if params.reason == "error" else "normal"

        title = f"{params.task_identifier} topic {params.reason}"
        summary = content[:500] if content else (params.error_message or params.reason)

        decision_source = "rule"
        if params.reason == "done" and content:
            generated = await self._system_agent.generate_brief_synthesis(
                [{"role": "assistant", "content": content}],
                task.name or params.task_identifier,
            )
            if generated:
                title = generated["title"]
                summary = generated["summary"]
                decision_source = "system-agent"

        artifacts = None
        if params.topic_id:
            topic_rows = await self._task_svc.find_topics(task.id)
            topic_link = next((t for t in topic_rows if t.topic_id == params.topic_id), None)
            since = (
                topic_link.created_at
                if topic_link
                else datetime.fromtimestamp(0, timezone.utc).replace(tzinfo=None)
            )
            documents = await self._task_svc.get_documents_pinned_since(task.id, since)
            if documents:
                artifacts = {"documents": documents}

        actions = None
        if brief_type == "error":
            actions = [
                {"key": "retry", "label": "🔄 重试", "type": "resolve"},
                {"key": "feedback", "label": "💬 反馈", "type": "comment"},
            ]

        if params.topic_id:
            await self._task_svc.update_topic_brief_decision(
                task.id,
                params.topic_id,
                {
                    "emit": True,
                    "reason": params.error_message or "Topic completion should be shown to the user",
                    "source": "rule-error" if params.reason == "error" else decision_source,
                },
            )

        return await self._task_svc.create_brief(
            task_id=task.id,
            topic_id=params.topic_id,
            agent_id=task.assignee_agent_id,
            type=brief_type,
            priority=priority,
            title=title,
            summary=summary,
            artifacts=artifacts,
            actions=actions,
            trigger="topic_complete",
        )
