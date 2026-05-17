"""Stream Event Managers — InMemory (default) and abstract interface.

Mirrors TypeScript:
- src/server/modules/AgentRuntime/types.ts  (IStreamEventManager)
- src/server/modules/AgentRuntime/InMemoryStreamEventManager.ts
- src/server/modules/AgentRuntime/StreamEventManager.ts  (Redis, optional)
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Callable, Optional

from .types import StreamChunkData, StreamEvent, StreamEventType

logger = logging.getLogger(__name__)

EventCallback = Callable[[list[StreamEvent]], None]


def _extract_reason_from_error(error: Any) -> Optional[str]:
    """Best-effort extraction of a human-readable reason from error payloads."""
    if not error:
        return None
    if isinstance(error, dict):
        body = error.get("body", {})
        if isinstance(body, dict):
            inner = body.get("error", {})
            if isinstance(inner, dict) and inner.get("message"):
                return inner["message"]
            if body.get("message"):
                return body["message"]
        err = error.get("error", {})
        if isinstance(err, dict):
            inner2 = err.get("error", {})
            if isinstance(inner2, dict) and inner2.get("message"):
                return inner2["message"]
            if err.get("message"):
                return err["message"]
        msg = error.get("message")
        if msg and msg not in ("[object Object]", "error"):
            return msg
        return error.get("type") or error.get("errorType")
    if isinstance(error, Exception):
        return str(error) or None
    return None


def _default_reason_detail(final_state: Any, reason: Optional[str] = None) -> str:
    if reason == "error":
        err = final_state.get("error") if isinstance(final_state, dict) else None
        return _extract_reason_from_error(err) or "Agent runtime failed"
    if reason == "interrupted":
        err = final_state.get("error") if isinstance(final_state, dict) else None
        return _extract_reason_from_error(err) or "Agent runtime interrupted"
    return "Agent runtime completed successfully"


# ── Abstract interface ──────────────────────────────────────────────

class IStreamEventManager(ABC):
    """Protocol matching TypeScript IStreamEventManager."""

    @abstractmethod
    async def publish_stream_event(
        self,
        operation_id: str,
        event: dict[str, Any],
    ) -> str:
        ...

    @abstractmethod
    async def publish_stream_chunk(
        self,
        operation_id: str,
        step_index: int,
        chunk_data: StreamChunkData,
    ) -> str:
        ...

    @abstractmethod
    async def publish_agent_runtime_init(
        self, operation_id: str, initial_state: Any
    ) -> str:
        ...

    @abstractmethod
    async def publish_agent_runtime_end(
        self,
        operation_id: str,
        step_index: int,
        final_state: Any,
        reason: Optional[str] = None,
        reason_detail: Optional[str] = None,
    ) -> str:
        ...

    @abstractmethod
    async def subscribe_stream_events(
        self,
        operation_id: str,
        last_event_id: str,
        on_events: EventCallback,
        signal: Optional[asyncio.Event] = None,
    ) -> None:
        ...

    @abstractmethod
    async def get_stream_history(
        self, operation_id: str, count: int = 100
    ) -> list[StreamEvent]:
        ...

    @abstractmethod
    async def cleanup_operation(self, operation_id: str) -> None:
        ...

    @abstractmethod
    async def get_active_operations_count(self) -> int:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...


# ── In-Memory implementation ────────────────────────────────────────

class InMemoryStreamEventManager(IStreamEventManager):
    """In-memory stream event manager for local / single-process deployments.

    Production systems should swap in a Redis-backed implementation.
    """

    def __init__(self) -> None:
        self._streams: dict[str, list[StreamEvent]] = defaultdict(list)
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)
        self._counter: int = 0

    def _generate_event_id(self) -> str:
        self._counter += 1
        return f"{int(time.time() * 1000)}-{self._counter}"

    # -- publish --

    async def publish_stream_event(
        self,
        operation_id: str,
        event: dict[str, Any],
    ) -> str:
        event_id = self._generate_event_id()
        ev = StreamEvent(
            type=StreamEventType(event["type"]),
            step_index=event.get("step_index", event.get("stepIndex", 0)),
            operation_id=operation_id,
            data=event.get("data"),
            timestamp=int(time.time() * 1000),
            id=event_id,
        )

        stream = self._streams[operation_id]
        stream.append(ev)
        if len(stream) > 1000:
            stream.pop(0)

        logger.debug(
            "Published event %s for operation %s:%d",
            ev.type.value, operation_id, ev.step_index,
        )

        for cb in self._subscribers.get(operation_id, []):
            try:
                cb([ev])
            except Exception:
                logger.exception("Subscriber callback error")

        return event_id

    async def publish_stream_chunk(
        self,
        operation_id: str,
        step_index: int,
        chunk_data: StreamChunkData,
    ) -> str:
        return await self.publish_stream_event(operation_id, {
            "type": StreamEventType.STREAM_CHUNK.value,
            "stepIndex": step_index,
            "data": chunk_data.to_dict(),
        })

    async def publish_agent_runtime_init(
        self, operation_id: str, initial_state: Any
    ) -> str:
        return await self.publish_stream_event(operation_id, {
            "type": StreamEventType.AGENT_RUNTIME_INIT.value,
            "stepIndex": 0,
            "data": initial_state,
        })

    async def publish_agent_runtime_end(
        self,
        operation_id: str,
        step_index: int,
        final_state: Any,
        reason: Optional[str] = None,
        reason_detail: Optional[str] = None,
    ) -> str:
        return await self.publish_stream_event(operation_id, {
            "type": StreamEventType.AGENT_RUNTIME_END.value,
            "stepIndex": step_index,
            "data": {
                "finalState": final_state,
                "operationId": operation_id,
                "phase": "execution_complete",
                "reason": reason or "completed",
                "reasonDetail": reason_detail or _default_reason_detail(final_state, reason),
            },
        })

    # -- subscribe --

    async def subscribe_stream_events(
        self,
        operation_id: str,
        last_event_id: str,
        on_events: EventCallback,
        signal: Optional[asyncio.Event] = None,
    ) -> None:
        """Block until ``agent_runtime_end`` is received or *signal* is set."""
        done = asyncio.Event()

        def _on_event(events: list[StreamEvent]) -> None:
            on_events(events)
            if any(e.type == StreamEventType.AGENT_RUNTIME_END for e in events):
                done.set()

        subs = self._subscribers[operation_id]
        subs.append(_on_event)

        try:
            if signal:
                signal_task = asyncio.ensure_future(_wait_event(signal))
                done_task = asyncio.ensure_future(_wait_event(done))
                finished, pending = await asyncio.wait(
                    {signal_task, done_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
            else:
                await done.wait()
        finally:
            if _on_event in subs:
                subs.remove(_on_event)

    # -- history --

    async def get_stream_history(
        self, operation_id: str, count: int = 100
    ) -> list[StreamEvent]:
        stream = self._streams.get(operation_id, [])
        return list(reversed(stream[-count:]))

    # -- cleanup --

    async def cleanup_operation(self, operation_id: str) -> None:
        self._streams.pop(operation_id, None)
        self._subscribers.pop(operation_id, None)
        logger.debug("Cleaned up operation %s", operation_id)

    async def get_active_operations_count(self) -> int:
        return len(self._streams)

    async def disconnect(self) -> None:
        logger.debug("InMemoryStreamEventManager disconnected")

    # -- test helpers --

    def clear(self) -> None:
        self._streams.clear()
        self._subscribers.clear()
        self._counter = 0

    def get_all_events(self, operation_id: str) -> list[StreamEvent]:
        return list(self._streams.get(operation_id, []))

    async def wait_for_event(
        self,
        operation_id: str,
        event_type: StreamEventType,
        timeout: float = 5.0,
    ) -> StreamEvent:
        """Wait for a specific event type. Raises TimeoutError on expiry."""
        found: asyncio.Future[StreamEvent] = asyncio.get_event_loop().create_future()

        def _check(events: list[StreamEvent]) -> None:
            for ev in events:
                if ev.type == event_type and not found.done():
                    found.set_result(ev)

        subs = self._subscribers[operation_id]
        subs.append(_check)
        try:
            # Check existing events first
            for ev in self._streams.get(operation_id, []):
                if ev.type == event_type and not found.done():
                    found.set_result(ev)
            return await asyncio.wait_for(found, timeout=timeout)
        finally:
            if _check in subs:
                subs.remove(_check)


# ── Singleton ───────────────────────────────────────────────────────

_manager: Optional[IStreamEventManager] = None


def get_stream_event_manager() -> IStreamEventManager:
    """Return the singleton stream event manager (InMemory by default)."""
    global _manager
    if _manager is None:
        _manager = InMemoryStreamEventManager()
    return _manager


# ── asyncio helpers ─────────────────────────────────────────────────

async def _wait_event(event: asyncio.Event) -> None:
    await event.wait()
