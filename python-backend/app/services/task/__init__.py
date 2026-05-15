"""Task system — scheduling, running, and lifecycle management.

Architecture mirrors the TS task layer:
- ``TaskService``      — CRUD + status transitions for tasks
- ``TaskRunnerService`` — orchestrates a single task run via the agent runtime
- ``TaskScheduler``    — abstract scheduler with local (asyncio) backend
- ``TaskLifecycleService`` — handles post-topic-complete state machine
"""

from app.services.task.service import TaskService
from app.services.task.runner import TaskRunnerService
from app.services.task.scheduler import TaskScheduler, LocalTaskScheduler
from app.services.task.lifecycle import TaskLifecycleService

__all__ = [
    "TaskService",
    "TaskRunnerService",
    "TaskScheduler",
    "LocalTaskScheduler",
    "TaskLifecycleService",
]
