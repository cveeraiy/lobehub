"""Abstract queue service with pluggable backends.

Mirrors TS ``src/server/services/queue/``.
"""

from app.services.queue.service import QueueService, InMemoryQueue, get_queue

__all__ = ["QueueService", "InMemoryQueue", "get_queue"]
