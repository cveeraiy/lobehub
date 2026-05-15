"""Task scheduler — abstract interface + local asyncio implementation.

Mirrors TS ``TaskSchedulerImpl`` interface and ``LocalTaskScheduler``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

TaskExecutionCallback = Callable[[str, str], Awaitable[None]]


class TaskScheduler(ABC):
    """Abstract scheduler for task next-topic scheduling."""

    @abstractmethod
    async def schedule_next_topic(
        self, *, task_id: str, user_id: str, delay: int = 0
    ) -> str:
        """Schedule next topic run. Returns a schedule ID."""
        ...

    @abstractmethod
    async def cancel_scheduled(self, schedule_id: str) -> None:
        """Cancel a previously scheduled invocation."""
        ...


class LocalTaskScheduler(TaskScheduler):
    """Asyncio-based local scheduler for development."""

    def __init__(self) -> None:
        self._callback: TaskExecutionCallback | None = None
        self._pending: dict[str, asyncio.Task[None]] = {}

    def set_execution_callback(self, callback: TaskExecutionCallback) -> None:
        self._callback = callback

    async def schedule_next_topic(
        self, *, task_id: str, user_id: str, delay: int = 0
    ) -> str:
        schedule_id = f"local-task-{task_id}-{int(time.time() * 1000)}"
        logger.debug("Scheduling next topic for task %s (delay: %ds)", task_id, delay)

        async def _run() -> None:
            if delay > 0:
                await asyncio.sleep(delay)
            self._pending.pop(schedule_id, None)
            if not self._callback:
                logger.warning("No execution callback set for scheduler")
                return
            try:
                logger.debug("Executing next topic for task %s", task_id)
                await self._callback(task_id, user_id)
            except Exception:
                logger.exception("Failed to execute next topic for task %s", task_id)

        self._pending[schedule_id] = asyncio.create_task(_run())
        return schedule_id

    async def cancel_scheduled(self, schedule_id: str) -> None:
        task = self._pending.pop(schedule_id, None)
        if task and not task.done():
            task.cancel()
            logger.debug("Canceled schedule %s", schedule_id)


# ── Module-level singleton ────────────────────────────────────────────
_scheduler: TaskScheduler | None = None


def get_task_scheduler() -> TaskScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = LocalTaskScheduler()
    return _scheduler
