"""Structured SSE event types for the Python Agent Runtime streaming layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional


# ── Event type enum ─────────────────────────────────────────────────

class StreamEventType(str, Enum):
    AGENT_RUNTIME_INIT = "agent_runtime_init"
    AGENT_RUNTIME_END = "agent_runtime_end"
    STREAM_START = "stream_start"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END = "stream_end"
    STREAM_RETRY = "stream_retry"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    ERROR = "error"


# ── Chunk sub-types ─────────────────────────────────────────────────

class StreamChunkType(str, Enum):
    TEXT = "text"
    REASONING = "reasoning"
    TOOLS_CALLING = "tools_calling"
    IMAGE = "image"
    GROUNDING = "grounding"
    BASE64_IMAGE = "base64_image"
    CONTENT_PART = "content_part"
    REASONING_PART = "reasoning_part"


# ── Data classes ────────────────────────────────────────────────────

@dataclass
class StreamChunkData:
    """Payload carried by a ``stream_chunk`` event."""

    chunk_type: StreamChunkType
    content: Optional[str] = None
    reasoning: Optional[str] = None
    tools_calling: Optional[list[dict[str, Any]]] = None
    images: Optional[list[Any]] = None
    image_list: Optional[list[Any]] = None
    grounding: Optional[Any] = None
    content_parts: Optional[list[dict[str, Any]]] = None
    reasoning_parts: Optional[list[dict[str, Any]]] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"chunkType": self.chunk_type.value}
        if self.content is not None:
            d["content"] = self.content
        if self.reasoning is not None:
            d["reasoning"] = self.reasoning
        if self.tools_calling is not None:
            d["toolsCalling"] = self.tools_calling
        if self.images is not None:
            d["images"] = self.images
        if self.image_list is not None:
            d["imageList"] = self.image_list
        if self.grounding is not None:
            d["grounding"] = self.grounding
        if self.content_parts is not None:
            d["contentParts"] = self.content_parts
        if self.reasoning_parts is not None:
            d["reasoningParts"] = self.reasoning_parts
        return d


@dataclass
class StreamEvent:
    """A single event in the Agent Runtime event stream."""

    type: StreamEventType
    step_index: int
    operation_id: str
    data: Any
    timestamp: int  # epoch milliseconds
    id: Optional[str] = None  # event ID (auto-generated)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type.value,
            "stepIndex": self.step_index,
            "operationId": self.operation_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        if self.id:
            d["id"] = self.id
        return d
