"""Chat router — SSE streaming chat endpoint with tool loop."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services import chat_service, llm_service, tool_execution
from app.services.ai_infra_service import get_runtime_state
from app.services.key_vault import KeyVaultService
from app.services.skill_engine import resolve_agent_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ── Schemas ──────────────────────────────────────────────────────────

class ChatRequestBody(BaseModel):
    messages: list[dict[str, Any]]
    model: Optional[str] = None
    provider: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = True
    tools: Optional[list[dict[str, Any]]] = None
    kb_ids: Optional[list[str]] = None
    enable_memory: bool = True


# ── SSE helper ───────────────────────────────────────────────────────

def _sse_encode(data: Any) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_response(response):
    """Yield SSE events from a litellm streaming response."""
    async for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta:
            payload: dict[str, Any] = {}
            if delta.content:
                payload["content"] = delta.content
            if delta.reasoning_content:
                payload["reasoning_content"] = delta.reasoning_content
            if getattr(delta, "tool_calls", None):
                payload["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in delta.tool_calls
                    if tc.function
                ]
            if payload:
                yield _sse_encode(payload)

        # Check for usage in final chunk
        if hasattr(chunk, "usage") and chunk.usage:
            yield _sse_encode({
                "usage": {
                    "input_tokens": getattr(chunk.usage, "prompt_tokens", None),
                    "output_tokens": getattr(chunk.usage, "completion_tokens", None),
                }
            })

    yield "data: [DONE]\n\n"


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("")
async def chat_endpoint(
    body: ChatRequestBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Primary chat endpoint.  Returns SSE stream or JSON."""
    # Resolve model from request or agent config
    model = body.model or "openai/gpt-4o"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    system_prompt: Optional[str] = None
    tools = body.tools
    kb_ids = body.kb_ids

    # If agent_id provided, resolve context from agent config
    if body.agent_id:
        try:
            ctx = await resolve_agent_context(session, user_id, body.agent_id)
            system_prompt = ctx.get("system_prompt")
            if ctx.get("tools"):
                tools = (tools or []) + ctx["tools"]
            if ctx.get("kb_ids"):
                kb_ids = (kb_ids or []) + ctx["kb_ids"]
        except Exception:
            logger.warning("Failed to resolve agent context", exc_info=True)

    # Resolve provider credentials
    if body.provider:
        try:
            vault = KeyVaultService.from_env()
        except RuntimeError:
            vault = None
        runtime = await get_runtime_state(session, user_id, vault)
        creds = await llm_service.resolve_provider_credentials(
            runtime.get("runtimeConfig", {}), body.provider
        )
        api_key = creds.get("api_key")
        api_base = creds.get("api_base")

    extra_kwargs: dict[str, Any] = {}
    if tools:
        extra_kwargs["tools"] = tools

    response = await chat_service.chat(
        session, user_id, body.messages,
        model=model,
        stream=body.stream,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        system_prompt=system_prompt,
        kb_ids=kb_ids,
        enable_memory=body.enable_memory,
        api_key=api_key,
        api_base=api_base,
        extra_kwargs=extra_kwargs if extra_kwargs else None,
    )

    if body.stream:
        return StreamingResponse(
            _stream_response(response),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming: return full response
    choice = response.choices[0] if response.choices else None
    result: dict[str, Any] = {
        "content": choice.message.content if choice else None,
        "model": response.model,
    }
    if choice and getattr(choice.message, "tool_calls", None):
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in choice.message.tool_calls
        ]
    if response.usage:
        result["usage"] = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }
    return result
