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

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.ai_agent import (
    AiAgentService,
    ExecAgentParams,
    ExecGroupAgentParams,
    ExecSubAgentTaskParams,
)
from app.services.ai_agent.types import AppContext, ResumeApproval

logger = logging.getLogger(__name__)

# Thread status enum values matching TS ThreadStatus
THREAD_STATUS_COMPLETED = "completed"
THREAD_STATUS_FAILED = "failed"
THREAD_STATUS_CANCEL = "cancel"
THREAD_STATUS_PROCESSING = "processing"

# Map thread status → task status
_THREAD_TO_TASK = {
    "active": "processing",
    "processing": "processing",
    "pending": "processing",
    "inReview": "processing",
    "todo": "pending",
    "cancel": "cancelled",
    "completed": "completed",
    "failed": "failed",
}

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


class CreateOperationBody(BaseModel):
    agent_id: Optional[str] = None
    agent_config: Optional[dict[str, Any]] = None
    auto_start: bool = True
    messages: Optional[list[dict[str, Any]]] = None
    model_runtime_config: Optional[dict[str, Any]] = None
    thread_id: Optional[str] = None
    topic_id: Optional[str] = None
    tools: Optional[list[Any]] = None
    tool_manifest_map: Optional[dict[str, Any]] = None


class ProcessHumanInterventionBody(BaseModel):
    operation_id: str
    action: str  # 'approve' | 'reject' | 'reject_continue' | 'input' | 'select'
    data: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    step_index: int = 0
    tool_message_id: Optional[str] = None


class CreateClientTaskThreadBody(BaseModel):
    agent_id: str
    group_id: Optional[str] = None
    instruction: str
    parent_message_id: Optional[str] = None
    title: Optional[str] = None
    topic_id: str


class CreateClientGroupAgentTaskThreadBody(BaseModel):
    group_id: str
    instruction: str
    parent_message_id: Optional[str] = None
    sub_agent_id: str
    title: Optional[str] = None
    topic_id: str


class UpdateClientTaskThreadStatusBody(BaseModel):
    thread_id: str
    completion_reason: str  # 'done' | 'error' | 'interrupted'
    error: Optional[str] = None
    result_content: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


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


# ---------------------------------------------------------------------------
# Advanced endpoints (mirrors TS aiAgent TRPC router)
# ---------------------------------------------------------------------------

@router.post("/create-operation")
async def create_operation(
    body: CreateOperationBody,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Create a runtime operation. Mirrors TS ``aiAgent.createOperation``."""
    from app.services.agent_runtime import agent_runtime
    import time

    mrc = body.model_runtime_config or {}
    if not mrc.get("model") or not mrc.get("provider"):
        raise HTTPException(status_code=400, detail="modelRuntimeConfig.model and .provider required")

    ts = int(time.time() * 1000)
    agent_label = body.agent_id or "unknown"
    topic_label = body.topic_id or "none"
    import secrets
    operation_id = f"agt_{ts}_{agent_label}_{topic_label}_{secrets.token_hex(4)}"

    initial_context = {
        "payload": {},
        "phase": "user_input",
        "session": {
            "messageCount": len(body.messages or []),
            "sessionId": operation_id,
            "status": "idle",
            "stepCount": 0,
        },
    }

    result = await agent_runtime.create_operation(
        operation_id=operation_id,
        user_id=user_id,
        agent_config=body.agent_config or {},
        app_context={
            "agentId": body.agent_id,
            "threadId": body.thread_id,
            "topicId": body.topic_id,
        },
        auto_start=body.auto_start,
        initial_context=initial_context,
        initial_messages=body.messages or [],
        model_runtime_config=mrc,
        tool_set={
            "manifestMap": body.tool_manifest_map or {},
            "tools": body.tools,
        },
    )

    first_step = None
    if result.get("autoStarted"):
        first_step = {
            "context": initial_context,
            "messageId": result.get("messageId"),
            "scheduled": True,
        }

    return {
        "autoStart": body.auto_start,
        "createdAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "firstStep": first_step,
        "operationId": operation_id,
        "status": "created",
        "success": True,
    }


@router.get("/operation-status")
async def get_operation_status(
    operationId: str,
    includeHistory: bool = False,
    historyLimit: int = 10,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get operation status. Mirrors TS ``aiAgent.getOperationStatus``."""
    from app.services.agent_runtime import agent_runtime

    status = await agent_runtime.get_status(operationId)
    if status is None:
        raise HTTPException(status_code=404, detail="Operation not found")
    return status


@router.post("/process-human-intervention")
async def process_human_intervention(
    body: ProcessHumanInterventionBody,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Process human intervention. Mirrors TS ``aiAgent.processHumanIntervention``."""
    from app.services.agent_runtime import agent_runtime

    params: dict[str, Any] = {
        "action": body.action,
        "operationId": body.operation_id,
        "stepIndex": body.step_index,
        "toolMessageId": body.tool_message_id,
    }

    if body.action == "approve":
        params["approvedToolCall"] = (body.data or {}).get("approvedToolCall")
    elif body.action in ("reject", "reject_continue"):
        params["rejectionReason"] = body.reason or "Tool call rejected by user"
        params["rejectAndContinue"] = body.action == "reject_continue"
    elif body.action == "input":
        params["humanInput"] = {"response": (body.data or {}).get("input")}
    elif body.action == "select":
        params["humanInput"] = {"selection": (body.data or {}).get("selection")}

    result = await agent_runtime.resume_with_tool_result(
        body.operation_id,
        params,
    )

    return {
        "action": body.action,
        "message": "Human intervention processed successfully. Execution resumed.",
        "operationId": body.operation_id,
        "scheduledMessageId": result.get("messageId") if isinstance(result, dict) else None,
        "success": True,
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


@router.get("/refresh-gateway-token")
async def refresh_gateway_token(
    topicId: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Refresh gateway JWT token. Mirrors TS ``aiAgent.refreshGatewayToken``."""
    from sqlalchemy import select, and_
    from app.models.topic import Topic

    topic = (await session.execute(
        select(Topic).where(and_(Topic.id == topicId, Topic.user_id == user_id))
    )).scalar_one_or_none()

    if not topic or not (topic.metadata_ or {}).get("runningOperation"):
        raise HTTPException(status_code=404, detail="No running operation found on this topic")

    import jwt as pyjwt
    import time
    import os

    secret = os.getenv("SESSION_SECRET", "lobehub-dev-secret")
    token = pyjwt.encode(
        {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + 3600},
        secret,
        algorithm="HS256",
    )
    return {"token": token}


@router.get("/sub-agent-task-status")
async def get_sub_agent_task_status(
    threadId: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get sub-agent task status by threadId. Mirrors TS ``aiAgent.getSubAgentTaskStatus``."""
    from sqlalchemy import select, and_, desc
    from app.models.topic_ext import Thread
    from app.models.message import Message

    thread = (await session.execute(
        select(Thread).where(and_(Thread.id == threadId, Thread.user_id == user_id))
    )).scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    metadata = thread.metadata_ or {}
    task_status = _THREAD_TO_TASK.get(thread.status or "active", "processing")

    # Try to get real-time status from AgentRuntimeService
    realtime_status = None
    resolved_op_id = metadata.get("operationId")
    if resolved_op_id and task_status == "processing":
        try:
            from app.services.agent_runtime import agent_runtime
            realtime_status = await agent_runtime.get_status(resolved_op_id)
        except Exception:
            pass

    # Query thread messages
    msgs_result = await session.execute(
        select(Message)
        .where(and_(Message.user_id == user_id, Message.thread_id == threadId))
        .order_by(desc(Message.created_at))
    )
    thread_messages = msgs_result.scalars().all()

    result_content = None
    if task_status in ("completed", "failed") and thread_messages:
        for m in thread_messages:
            if m.role == "assistant":
                result_content = m.content
                break

    current_activity = None
    if task_status == "processing" and thread_messages:
        last_msg = thread_messages[0]
        if last_msg.role == "tool":
            current_activity = {"type": "tool_result", "contentPreview": (last_msg.content or "")[:100]}
        elif last_msg.role == "assistant":
            current_activity = {"type": "generating", "contentPreview": (last_msg.content or "")[:100]}

    task_detail = {
        "completedAt": metadata.get("completedAt"),
        "duration": metadata.get("duration"),
        "error": metadata.get("error"),
        "startedAt": metadata.get("startedAt"),
        "status": thread.status,
        "threadId": thread.id,
        "title": thread.title,
        "totalCost": metadata.get("totalCost"),
        "totalMessages": metadata.get("totalMessages"),
        "totalSteps": metadata.get("totalSteps"),
        "totalTokens": metadata.get("totalTokens"),
        "totalToolCalls": metadata.get("totalToolCalls"),
    }

    return {
        "completedAt": metadata.get("completedAt"),
        "cost": (realtime_status or {}).get("currentState", {}).get("cost") if realtime_status else (
            {"total": metadata["totalCost"]} if metadata.get("totalCost") else None
        ),
        "currentActivity": current_activity,
        "error": metadata.get("error"),
        "messages": [{"id": m.id, "role": m.role, "content": m.content} for m in thread_messages],
        "result": result_content,
        "status": task_status,
        "taskDetail": task_detail,
    }


@router.post("/create-client-task-thread")
async def create_client_task_thread(
    body: CreateClientTaskThreadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create Thread for client-side task execution. Mirrors TS ``aiAgent.createClientTaskThread``."""
    from app.models.topic_ext import Thread
    from app.models.message import Message
    from sqlalchemy import select, and_, desc
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    # 1. Create Thread
    thread = Thread(
        topic_id=body.topic_id,
        user_id=user_id,
        title=body.title or "Client Task",
        type="isolation",
        status="processing",
        agent_id=body.agent_id,
        group_id=body.group_id,
        source_message_id=body.parent_message_id,
        metadata_={"startedAt": now.isoformat()},
    )
    session.add(thread)
    await session.flush()

    # 2. Create initial user message
    user_msg = Message(
        user_id=user_id,
        topic_id=body.topic_id,
        thread_id=thread.id,
        agent_id=body.agent_id,
        role="user",
        content=body.instruction,
        parent_id=body.parent_message_id,
    )
    session.add(user_msg)
    await session.flush()

    # 3. Query thread messages and main chat messages
    thread_msgs = (await session.execute(
        select(Message)
        .where(and_(Message.user_id == user_id, Message.thread_id == thread.id))
        .order_by(desc(Message.created_at))
    )).scalars().all()

    main_msgs = (await session.execute(
        select(Message)
        .where(and_(
            Message.user_id == user_id,
            Message.topic_id == body.topic_id,
            Message.thread_id == None,  # noqa: E711
        ))
        .order_by(desc(Message.created_at))
    )).scalars().all()

    return {
        "messages": [{"id": m.id, "role": m.role, "content": m.content} for m in main_msgs],
        "threadId": thread.id,
        "threadMessages": [{"id": m.id, "role": m.role, "content": m.content} for m in thread_msgs],
        "userMessageId": user_msg.id,
    }


@router.post("/create-client-group-agent-task-thread")
async def create_client_group_agent_task_thread(
    body: CreateClientGroupAgentTaskThreadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create Thread for client-side group agent execution. Mirrors TS ``aiAgent.createClientGroupAgentTaskThread``."""
    from app.models.topic_ext import Thread
    from app.models.message import Message
    from sqlalchemy import select, and_, desc
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    thread = Thread(
        topic_id=body.topic_id,
        user_id=user_id,
        title=body.title or "Group Agent Task",
        type="isolation",
        status="processing",
        agent_id=body.sub_agent_id,
        group_id=body.group_id,
        source_message_id=body.parent_message_id,
        metadata_={"startedAt": now.isoformat()},
    )
    session.add(thread)
    await session.flush()

    user_msg = Message(
        user_id=user_id,
        topic_id=body.topic_id,
        thread_id=thread.id,
        agent_id=body.sub_agent_id,
        role="user",
        content=body.instruction,
        parent_id=body.parent_message_id,
    )
    session.add(user_msg)
    await session.flush()

    thread_msgs = (await session.execute(
        select(Message)
        .where(and_(Message.user_id == user_id, Message.thread_id == thread.id))
        .order_by(desc(Message.created_at))
    )).scalars().all()

    main_msgs = (await session.execute(
        select(Message)
        .where(and_(
            Message.user_id == user_id,
            Message.topic_id == body.topic_id,
            Message.thread_id == None,  # noqa: E711
        ))
        .order_by(desc(Message.created_at))
    )).scalars().all()

    return {
        "messages": [{"id": m.id, "role": m.role, "content": m.content} for m in main_msgs],
        "threadId": thread.id,
        "threadMessages": [{"id": m.id, "role": m.role, "content": m.content} for m in thread_msgs],
        "userMessageId": user_msg.id,
    }


@router.post("/update-client-task-thread-status")
async def update_client_task_thread_status(
    body: UpdateClientTaskThreadStatusBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update Thread status after client-side execution. Mirrors TS ``aiAgent.updateClientTaskThreadStatus``."""
    from sqlalchemy import select, and_
    from app.models.topic_ext import Thread
    from app.models.message import Message
    from datetime import datetime, timezone

    thread = (await session.execute(
        select(Thread).where(and_(Thread.id == body.thread_id, Thread.user_id == user_id))
    )).scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    completed_at = datetime.now(timezone.utc).isoformat()
    started_at = (thread.metadata_ or {}).get("startedAt")
    duration = None
    if started_at:
        try:
            duration = int(
                (datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds() * 1000
            )
        except Exception:
            pass

    status_map = {"done": THREAD_STATUS_COMPLETED, "error": THREAD_STATUS_FAILED, "interrupted": THREAD_STATUS_CANCEL}
    new_status = status_map.get(body.completion_reason, THREAD_STATUS_COMPLETED)

    merged_meta = {**(thread.metadata_ or {})}
    merged_meta["completedAt"] = completed_at
    if duration is not None:
        merged_meta["duration"] = duration
    if body.error:
        merged_meta["error"] = body.error
    if body.metadata:
        for k in ("totalCost", "totalMessages", "totalSteps", "totalTokens", "totalToolCalls"):
            if k in body.metadata:
                merged_meta[k] = body.metadata[k]

    thread.status = new_status
    thread.metadata_ = merged_meta
    session.add(thread)

    if body.result_content and thread.source_message_id:
        msg = (await session.execute(
            select(Message).where(Message.id == thread.source_message_id)
        )).scalar_one_or_none()
        if msg:
            msg.content = body.result_content
            session.add(msg)

    await session.flush()

    return {"status": new_status, "success": True, "threadId": body.thread_id}
