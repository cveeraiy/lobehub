"""Agent router — operation-based agent execution via LangGraph.

Endpoints:
- POST /api/agent                         — Create operation
- POST /api/agent/run                     — Run operation (non-streaming)
- GET  /api/agent/stream                  — Run operation (SSE streaming)
- GET  /api/agent/status/{operation_id}   — Poll operation status
- POST /api/agent/interrupt/{operation_id} — Interrupt running operation
- POST /api/agent/tool-result             — Submit human tool approval/rejection
- GET  /api/agent/operations              — List operations
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.agent_runtime import agent_runtime
from app.services.ai_infra_service import get_runtime_state
from app.services.key_vault import KeyVaultService
from app.services.skill_engine import resolve_agent_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent Runtime"])


# ── Schemas ──────────────────────────────────────────────────────────

class CreateOperationBody(BaseModel):
    messages: list[dict[str, Any]]
    model: Optional[str] = None
    provider: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[list[dict[str, Any]]] = None
    kb_ids: Optional[list[str]] = None
    enable_memory: bool = True
    require_human_approval: Optional[bool] = None
    max_steps: Optional[int] = None
    stream: bool = False


class RunOperationBody(BaseModel):
    operation_id: str


class ToolResultBody(BaseModel):
    operation_id: str
    approved: bool = True
    reason: Optional[str] = None
    stream: bool = False


class GatewayCallbackBody(BaseModel):
    event: Optional[str] = None
    data: Optional[dict[str, Any]] = None


# ── SSE helper ───────────────────────────────────────────────────────

def _sse_encode(data: Any) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_events(operation_id: str, resume_value: dict[str, Any] | None = None):
    """Yield SSE events from the agent runtime stream."""
    if resume_value is not None:
        event_stream = agent_runtime.stream_resume(
            operation_id,
            approved=resume_value.get("approved", True),
            reason=resume_value.get("reason"),
        )
    else:
        event_stream = agent_runtime.stream_operation(operation_id)

    async for event in event_stream:
        yield _sse_encode(event)

    yield "data: [DONE]\n\n"


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("")
async def create_operation(
    body: CreateOperationBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a new agent operation.

    If ``stream=true``, also starts execution and returns an SSE stream.
    Otherwise, returns the operation_id for later execution.
    """
    model = body.model or "openai/gpt-4o"
    api_key: str | None = None
    api_base: str | None = None
    system_prompt = body.system_prompt
    tools = body.tools
    kb_ids = body.kb_ids

    # Resolve agent context if agent_id provided
    if body.agent_id:
        try:
            ctx = await resolve_agent_context(session, user_id, body.agent_id)
            system_prompt = system_prompt or ctx.get("system_prompt")
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
        from app.services import llm_service
        runtime = await get_runtime_state(session, user_id, vault)
        creds = await llm_service.resolve_provider_credentials(
            runtime.get("runtimeConfig", {}), body.provider
        )
        api_key = creds.get("api_key")
        api_base = creds.get("api_base")

    # Create operation
    result = await agent_runtime.create_operation(
        user_id,
        body.messages,
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        kb_ids=kb_ids,
        enable_memory=body.enable_memory,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        api_key=api_key,
        api_base=api_base,
        agent_id=body.agent_id,
        session_id=body.session_id,
        require_human_approval=body.require_human_approval,
        max_steps=body.max_steps,
    )

    operation_id = result["operation_id"]

    # If streaming requested, start execution immediately
    if body.stream:
        return StreamingResponse(
            _stream_events(operation_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Operation-Id": operation_id,
            },
        )

    return result


@router.post("/run")
async def run_operation(
    body: RunOperationBody,
    user_id: str = Depends(get_current_user_id),
):
    """Run an existing operation to completion (non-streaming)."""
    try:
        result = await agent_runtime.run_operation(body.operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Operation %s failed: %s", body.operation_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "operation_id": body.operation_id,
        "status": result.get("status", "done"),
        "step_count": result.get("step_count", 0),
        "usage": result.get("usage"),
        "messages": result.get("messages", []),
    }


@router.post("/python-stream")
async def python_stream(
    body: dict[str, Any] = Body(...),
    user_id: str = Depends(get_current_user_id),
):
    """Compatibility alias for the former TS agent stream bridge."""
    from app.routers.ai_agent import ExecAgentBody, exec_agent_stream

    exec_body = body if isinstance(body, ExecAgentBody) else ExecAgentBody.model_validate(body)
    return await exec_agent_stream(exec_body, user_id)


@router.get("/gateway")
async def get_gateway_status():
    """Device gateway mode was tied to the removed TS supervisor."""
    raise HTTPException(
        status.HTTP_410_GONE,
        "Agent gateway mode is retired in the Python-only backend runtime",
    )


@router.post("/gateway/start")
async def start_gateway():
    raise HTTPException(
        status.HTTP_410_GONE,
        "Agent gateway mode is retired in the Python-only backend runtime",
    )


@router.post("/gateway/callback")
async def gateway_callback(body: GatewayCallbackBody):
    raise HTTPException(
        status.HTTP_410_GONE,
        "Agent gateway mode is retired in the Python-only backend runtime",
    )


@router.get("/stream")
async def stream_operation(
    operation_id: str = Query(..., description="Operation ID to stream"),
    user_id: str = Depends(get_current_user_id),
):
    """SSE stream for an existing operation.

    Start execution and stream events in real-time.
    """
    op_status = await agent_runtime.get_status(operation_id)
    if not op_status:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")

    return StreamingResponse(
        _stream_events(operation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{operation_id}")
async def get_operation_status(
    operation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Poll the current status of an agent operation."""
    result = await agent_runtime.get_status(operation_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
    return result


@router.post("/interrupt/{operation_id}")
async def interrupt_operation(
    operation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Interrupt a running agent operation."""
    success = await agent_runtime.interrupt_operation(operation_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Operation not found or already in terminal state",
        )
    return {"operation_id": operation_id, "status": "interrupted"}


@router.post("/tool-result")
async def submit_tool_result(
    body: ToolResultBody,
    user_id: str = Depends(get_current_user_id),
):
    """Submit human tool approval/rejection to resume an interrupted operation.

    If ``stream=true``, returns SSE stream of resumed execution.
    """
    op_status = await agent_runtime.get_status(body.operation_id)
    if not op_status:
        raise HTTPException(status_code=404, detail="Operation not found")
    if not op_status.get("needs_human_input"):
        raise HTTPException(status_code=400, detail="Operation is not waiting for human input")

    if body.stream:
        return StreamingResponse(
            _stream_events(
                body.operation_id,
                resume_value={"approved": body.approved, "reason": body.reason},
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming resume
    try:
        result = await agent_runtime.resume_with_tool_result(
            body.operation_id,
            approved=body.approved,
            reason=body.reason,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "operation_id": body.operation_id,
        "status": result.get("status", "done"),
        "step_count": result.get("step_count", 0),
        "usage": result.get("usage"),
        "messages": result.get("messages", []),
    }


@router.get("/operations")
async def list_operations(
    user_id: str = Depends(get_current_user_id),
):
    """List all operations for the current user."""
    return agent_runtime.list_operations(user_id=user_id)


@router.delete("/{operation_id}")
async def delete_operation(
    operation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Clean up an operation from memory."""
    await agent_runtime.cleanup_operation(operation_id)
    return {"ok": True}
