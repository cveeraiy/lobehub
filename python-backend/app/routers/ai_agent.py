"""AI Agent Service HTTP router.

Exposes the AiAgentService via REST endpoints, mirroring the TS tRPC
``aiAgent.execAgent`` / ``aiAgent.execGroupAgent`` / ``aiAgent.execSubAgentTask``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth import get_current_user_id
from app.services.ai_agent import (
    AiAgentService,
    ExecAgentParams,
    ExecGroupAgentParams,
    ExecSubAgentTaskParams,
)
from app.services.ai_agent.types import AppContext, ResumeApproval

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-agent", tags=["ai-agent"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AppContextBody(BaseModel):
    session_id: Optional[str] = None
    topic_id: Optional[str] = None
    thread_id: Optional[str] = None
    group_id: Optional[str] = None
    scope: Optional[str] = None
    document_id: Optional[str] = None
    task_id: Optional[str] = None
    default_task_assignee_agent_id: Optional[str] = None

    def to_app_context(self) -> AppContext:
        return AppContext(
            session_id=self.session_id,
            topic_id=self.topic_id,
            thread_id=self.thread_id,
            group_id=self.group_id,
            scope=self.scope,
            document_id=self.document_id,
            task_id=self.task_id,
            default_task_assignee_agent_id=self.default_task_assignee_agent_id,
        )


class ResumeApprovalBody(BaseModel):
    decision: str  # 'approved' | 'rejected' | 'rejected_continue'
    parent_message_id: str
    tool_call_id: str
    rejection_reason: Optional[str] = None

    def to_resume_approval(self) -> ResumeApproval:
        return ResumeApproval(
            decision=self.decision,  # type: ignore[arg-type]
            parent_message_id=self.parent_message_id,
            tool_call_id=self.tool_call_id,
            rejection_reason=self.rejection_reason,
        )


class ExecAgentBody(BaseModel):
    prompt: str
    agent_id: Optional[str] = None
    slug: Optional[str] = None
    app_context: Optional[AppContextBody] = None
    auto_start: bool = True
    model: Optional[str] = None
    provider: Optional[str] = None
    instructions: Optional[str] = None
    file_ids: Optional[list[str]] = None
    stream: Optional[bool] = True
    title: Optional[str] = None
    trigger: Optional[str] = None
    cron_job_id: Optional[str] = None
    task_id: Optional[str] = None
    max_steps: Optional[int] = None
    disable_tools: bool = False
    resume: bool = False
    resume_approval: Optional[ResumeApprovalBody] = None
    parent_message_id: Optional[str] = None
    existing_message_ids: Optional[list[str]] = None
    function_tools: Optional[list[dict[str, Any]]] = None


class ExecGroupAgentBody(BaseModel):
    agent_id: str
    group_id: str
    message: str
    topic_id: Optional[str] = None
    new_topic: Optional[dict[str, Any]] = None


class ExecSubAgentTaskBody(BaseModel):
    agent_id: str
    topic_id: str
    instruction: str
    parent_message_id: str
    group_id: Optional[str] = None
    title: Optional[str] = None
    parent_operation_id: Optional[str] = None


class InterruptTaskBody(BaseModel):
    thread_id: Optional[str] = None
    operation_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/exec")
async def exec_agent(
    body: ExecAgentBody,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Execute an agent with a prompt.

    Mirrors TS ``aiAgent.execAgent``.
    """
    service = AiAgentService(user_id)

    params = ExecAgentParams(
        prompt=body.prompt,
        agent_id=body.agent_id,
        slug=body.slug,
        app_context=body.app_context.to_app_context() if body.app_context else None,
        auto_start=body.auto_start,
        model=body.model,
        provider=body.provider,
        instructions=body.instructions,
        file_ids=body.file_ids,
        stream=body.stream,
        title=body.title,
        trigger=body.trigger,
        cron_job_id=body.cron_job_id,
        task_id=body.task_id,
        max_steps=body.max_steps,
        disable_tools=body.disable_tools,
        resume=body.resume,
        resume_approval=(
            body.resume_approval.to_resume_approval() if body.resume_approval else None
        ),
        parent_message_id=body.parent_message_id,
        existing_message_ids=body.existing_message_ids,
        function_tools=body.function_tools,
    )

    try:
        result = await service.exec_agent(params)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("exec_agent failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/exec/stream")
async def exec_agent_stream(
    body: ExecAgentBody,
    user_id: str = Depends(get_current_user_id),
) -> EventSourceResponse:
    """Execute an agent and stream SSE events.

    Creates the operation and then streams events from the runtime.
    """
    from app.services.agent_runtime import agent_runtime

    service = AiAgentService(user_id)

    params = ExecAgentParams(
        prompt=body.prompt,
        agent_id=body.agent_id,
        slug=body.slug,
        app_context=body.app_context.to_app_context() if body.app_context else None,
        auto_start=False,  # We'll stream manually
        model=body.model,
        provider=body.provider,
        instructions=body.instructions,
        file_ids=body.file_ids,
        stream=True,
        title=body.title,
        trigger=body.trigger,
        cron_job_id=body.cron_job_id,
        task_id=body.task_id,
        max_steps=body.max_steps,
        disable_tools=body.disable_tools,
        resume=body.resume,
        resume_approval=(
            body.resume_approval.to_resume_approval() if body.resume_approval else None
        ),
        parent_message_id=body.parent_message_id,
        existing_message_ids=body.existing_message_ids,
        function_tools=body.function_tools,
    )

    # Create the operation first
    result = await service.exec_agent(params)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    import json

    async def event_generator():
        # Yield the creation event
        yield {
            "event": "agent_created",
            "data": json.dumps(result.to_dict()),
        }

        # Stream runtime events
        async for event in agent_runtime.stream_operation(result.operation_id):
            yield {
                "event": event.get("type", "message"),
                "data": json.dumps(event),
            }

    return EventSourceResponse(event_generator())


@router.post("/exec-group")
async def exec_group_agent(
    body: ExecGroupAgentBody,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Execute Group Agent (Supervisor)."""
    service = AiAgentService(user_id)

    params = ExecGroupAgentParams(
        agent_id=body.agent_id,
        group_id=body.group_id,
        message=body.message,
        topic_id=body.topic_id,
        new_topic=body.new_topic,
    )

    try:
        result = await service.exec_group_agent(params)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("exec_group_agent failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/exec-sub-agent")
async def exec_sub_agent_task(
    body: ExecSubAgentTaskBody,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Execute SubAgent task with Thread isolation."""
    service = AiAgentService(user_id)

    params = ExecSubAgentTaskParams(
        agent_id=body.agent_id,
        topic_id=body.topic_id,
        instruction=body.instruction,
        parent_message_id=body.parent_message_id,
        group_id=body.group_id,
        title=body.title,
        parent_operation_id=body.parent_operation_id,
    )

    try:
        result = await service.exec_sub_agent_task(params)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("exec_sub_agent_task failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/interrupt")
async def interrupt_task(
    body: InterruptTaskBody,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Interrupt a running task."""
    service = AiAgentService(user_id)

    try:
        return await service.interrupt_task(
            thread_id=body.thread_id,
            operation_id=body.operation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("interrupt_task failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
