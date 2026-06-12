"""Queue service — abstract interface + in-memory asyncio implementation.

Used by the task scheduler, agent signal pipeline, and other subsystems
that need reliable async job dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class QueueJob:
    """A single queued job."""

    id: str
    queue: str
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    delay_until: float = 0.0  # unix timestamp; 0 = immediate
    attempts: int = 0
    max_retries: int = 3
    status: str = "pending"  # pending | processing | completed | failed


class QueueService(ABC):
    """Abstract queue interface."""

    @abstractmethod
    async def enqueue(
        self,
        queue_name: str,
        payload: dict[str, Any],
        *,
        delay_seconds: int = 0,
        max_retries: int = 3,
    ) -> str:
        """Add a job and return its ID."""
        ...

    @abstractmethod
    async def process(
        self, queue_name: str, handler: JobHandler, *, concurrency: int = 1
    ) -> None:
        """Start processing jobs from the given queue."""
        ...

    @abstractmethod
    async def cancel(self, job_id: str) -> bool:
        """Cancel a pending job. Returns True if found and cancelled."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shut down all processing."""
        ...


class InMemoryQueue(QueueService):
    """Asyncio-based in-memory queue for development / single-process deployments."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[QueueJob]] = defaultdict(asyncio.Queue)
        self._jobs: dict[str, QueueJob] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._counter = 0
        self._shutting_down = False

    async def enqueue(
        self,
        queue_name: str,
        payload: dict[str, Any],
        *,
        delay_seconds: int = 0,
        max_retries: int = 3,
    ) -> str:
        self._counter += 1
        job_id = f"job-{queue_name}-{self._counter}-{int(time.time() * 1000)}"

        job = QueueJob(
            id=job_id,
            queue=queue_name,
            payload=payload,
            delay_until=time.time() + delay_seconds if delay_seconds > 0 else 0,
            max_retries=max_retries,
        )
        self._jobs[job_id] = job

        if delay_seconds > 0:
            asyncio.create_task(self._delayed_enqueue(job))
        else:
            await self._queues[queue_name].put(job)

        logger.debug("Enqueued job %s on %s", job_id, queue_name)
        return job_id

    async def _delayed_enqueue(self, job: QueueJob) -> None:
        wait = job.delay_until - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
        if job.status == "pending":  # not cancelled
            await self._queues[job.queue].put(job)

    async def process(
        self, queue_name: str, handler: JobHandler, *, concurrency: int = 1
    ) -> None:
        for _ in range(concurrency):
            task = asyncio.create_task(
                self._worker(queue_name, handler)
            )
            self._workers.append(task)

    async def _worker(self, queue_name: str, handler: JobHandler) -> None:
        q = self._queues[queue_name]
        while not self._shutting_down:
            try:
                job = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if job.status != "pending":
                continue

            job.status = "processing"
            job.attempts += 1
            try:
                await handler(job.payload)
                job.status = "completed"
            except Exception:
                logger.exception("Job %s failed (attempt %d)", job.id, job.attempts)
                if job.attempts < job.max_retries:
                    job.status = "pending"
                    await q.put(job)
                else:
                    job.status = "failed"

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status == "pending":
            job.status = "failed"
            return True
        return False

    async def shutdown(self) -> None:
        self._shutting_down = True
        for w in self._workers:
            w.cancel()
        self._workers.clear()


# ── Module-level singleton ────────────────────────────────────────────
_queue: QueueService | None = None


def get_queue() -> QueueService:
    global _queue
    if _queue is None:
        _queue = InMemoryQueue()
    return _queue
