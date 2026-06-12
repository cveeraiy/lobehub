"""OpenAPI v1 Responses API route."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user_id
from app.models._helpers import id_generator
from app.services.llm_service import chat

router = APIRouter(prefix="/api/v1/responses", tags=["OpenAPI Responses"])


def _extract_prompt(input_value: Any) -> str:
    if isinstance(input_value, str):
        return input_value
    if not isinstance(input_value, list):
        return ""
    for item in reversed(input_value):
        if not isinstance(item, dict) or item.get("type") != "message" or item.get("role") != "user":
            continue
        content = item.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _extract_instructions(input_value: Any, request_instructions: str | None) -> str | None:
    parts: list[str] = []
    if isinstance(input_value, list):
        for item in input_value:
            if (
                not isinstance(item, dict)
                or item.get("type") != "message"
                or item.get("role") not in {"system", "developer"}
            ):
                continue
            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                if text:
                    parts.append(text)
    if request_instructions:
        parts.append(request_instructions)
    return "\n\n".join(parts) or None


def _response_object(
    body: dict[str, Any],
    response_id: str,
    output_text: str,
    *,
    status: str = "completed",
) -> dict[str, Any]:
    created_at = int(time.time())
    return {
        "completed_at": created_at if status == "completed" else None,
        "created_at": created_at,
        "error": None,
        "id": response_id,
        "instructions": body.get("instructions"),
        "max_output_tokens": body.get("max_output_tokens"),
        "metadata": body.get("metadata"),
        "model": body["model"],
        "object": "response",
        "output": [
            {
                "content": [{"annotations": [], "logprobs": [], "text": output_text, "type": "output_text"}],
                "id": f"msg_{response_id}_0",
                "role": "assistant",
                "status": status,
                "type": "message",
            }
        ],
        "output_text": output_text,
        "parallel_tool_calls": body.get("parallel_tool_calls"),
        "previous_response_id": body.get("previous_response_id"),
        "reasoning": body.get("reasoning"),
        "status": status,
        "temperature": body.get("temperature"),
        "tool_choice": body.get("tool_choice"),
        "tools": body.get("tools") or [],
        "top_p": body.get("top_p"),
        "truncation": body.get("truncation", {}).get("type") if isinstance(body.get("truncation"), dict) else None,
        "usage": None,
        "user": body.get("user"),
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("")
async def create_response(request: Request, _user_id: str = Depends(get_current_user_id)):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Request body must be an object")
    if not body.get("model"):
        raise HTTPException(400, "model is required")
    if "input" not in body:
        raise HTTPException(400, "input is required")

    response_id = id_generator("resp")
    prompt = _extract_prompt(body["input"])
    instructions = _extract_instructions(body["input"], body.get("instructions"))
    messages = []
    if instructions:
        messages.append({"content": instructions, "role": "system"})
    messages.append({"content": prompt, "role": "user"})

    if body.get("stream"):
        async def stream() -> AsyncIterator[str]:
            initial = _response_object(body, response_id, "", status="in_progress")
            yield _sse("response.created", {"response": initial})
            chunks: list[str] = []
            try:
                result = await chat(
                    messages,
                    max_tokens=body.get("max_output_tokens"),
                    model=body["model"],
                    stream=True,
                    temperature=body.get("temperature"),
                )
                async for chunk in result:
                    delta = chunk.choices[0].delta.content or ""
                    if not delta:
                        continue
                    chunks.append(delta)
                    yield _sse("response.output_text.delta", {"delta": delta, "item_id": f"msg_{response_id}_0"})
                final = _response_object(body, response_id, "".join(chunks))
                yield _sse("response.completed", {"response": final})
            except Exception as exc:
                failed = _response_object(body, response_id, "", status="failed")
                failed["error"] = {"code": "model_error", "message": str(exc)}
                yield _sse("response.failed", {"response": failed})

        return StreamingResponse(stream(), media_type="text/event-stream")

    try:
        result = await chat(
            messages,
            max_tokens=body.get("max_output_tokens"),
            model=body["model"],
            temperature=body.get("temperature"),
        )
        content = result.choices[0].message.content or ""
    except Exception as exc:
        raise HTTPException(500, str(exc))
    return _response_object(body, response_id, content)
