"""Agent Stream Router — SSE endpoint for real-time Agent execution events.

Mirrors TypeScript: src/handlers/api/agent/stream/route.ts
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user_id
from app.services.stream_event import (
    StreamEvent,
    StreamEventType,
    get_stream_event_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/stream-events", tags=["Agent Stream"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "text/event-stream",
    "X-Accel-Buffering": "no",
}

HEARTBEAT_INTERVAL = 30  # seconds


def _sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _sse_connection(operation_id: str, last_event_id: str) -> str:
    return _sse_data({
        "type": "connection",
        "operationId": operation_id,
        "lastEventId": last_event_id,
        "timestamp": int(time.time() * 1000),
    })


@router.get("")
async def agent_stream_sse(
    operation_id: str = Query(..., alias="operationId"),
    last_event_id: str = Query("0", alias="lastEventId"),
    include_history: bool = Query(False, alias="includeHistory"),
    user_id: str = Depends(get_current_user_id),
):
    """Server-Sent Events endpoint for real-time Agent execution event stream.

    Query params:
    - ``operationId`` — required, the operation to subscribe to.
    - ``lastEventId`` — resume from this event ID (default ``"0"``).
    - ``includeHistory`` — if ``true``, replay historical events first.
    """
    manager = get_stream_event_manager()

    async def _generate():
        stream_ended = False
        abort = asyncio.Event()

        # 1. Send connection confirmation
        yield _sse_connection(operation_id, last_event_id)

        # 2. Replay history if requested
        if include_history:
            try:
                history = await manager.get_stream_history(operation_id, 50)
                # history comes newest-first from the manager; reverse for chronological
                for ev in reversed(history):
                    if (
                        not last_event_id
                        or last_event_id == "0"
                        or (ev.id and ev.id > last_event_id)
                    ):
                        sse_payload = ev.to_dict()
                        sse_payload["operationId"] = operation_id
                        yield _sse_data(sse_payload)
            except Exception:
                logger.exception("Failed to load history for %s", operation_id)

        # 3. Subscribe to live events
        event_queue: asyncio.Queue[list[StreamEvent]] = asyncio.Queue()

        def _on_events(events: list[StreamEvent]) -> None:
            event_queue.put_nowait(events)

        # Start subscription in background
        sub_task = asyncio.create_task(
            manager.subscribe_stream_events(
                operation_id, last_event_id, _on_events, abort
            )
        )

        # 4. Heartbeat + event dispatch loop
        try:
            while not stream_ended:
                try:
                    events = await asyncio.wait_for(
                        event_queue.get(), timeout=HEARTBEAT_INTERVAL
                    )
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield _sse_data({
                        "type": "heartbeat",
                        "operationId": operation_id,
                        "timestamp": int(time.time() * 1000),
                    })
                    continue

                for ev in events:
                    sse_payload = ev.to_dict()
                    sse_payload["operationId"] = operation_id
                    yield _sse_data(sse_payload)

                    if ev.type == StreamEventType.AGENT_RUNTIME_END:
                        stream_ended = True
                        break
        finally:
            abort.set()
            sub_task.cancel()
            try:
                await sub_task
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
