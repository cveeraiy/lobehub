"""Message CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message, MessageFile, MessagePlugin, MessageQuery, MessageQueryChunk
from app.models.message_ext import MessageGroup, MessageTranslate, MessageTts

router = APIRouter(prefix="/api/messages", tags=["Messages"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateMessageBody(BaseModel):
    role: str  # user | assistant | system | tool
    content: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = None
    summary: Optional[str] = None
    reasoning: Optional[dict[str, Any]] = None
    search: Optional[dict[str, Any]] = None
    session_id: Optional[str] = None
    topic_id: Optional[str] = None
    agent_id: Optional[str] = None
    group_id: Optional[str] = None
    thread_id: Optional[str] = None
    parent_id: Optional[str] = None
    quota_id: Optional[str] = None
    target_id: Optional[str] = None
    message_group_id: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    favorite: Optional[bool] = None
    tools: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    reasoning_content: Optional[str] = None
    trace_id: Optional[str] = None
    observation_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None


class UpdateMessageBody(BaseModel):
    content: Optional[str] = None
    editor_data: Optional[dict[str, Any]] = None
    summary: Optional[str] = None
    reasoning: Optional[dict[str, Any]] = None
    search: Optional[dict[str, Any]] = None
    reasoning_content: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    favorite: Optional[bool] = None
    trace_id: Optional[str] = None
    observation_id: Optional[str] = None
    quota_id: Optional[str] = None
    target_id: Optional[str] = None
    group_id: Optional[str] = None
    message_group_id: Optional[str] = None
    tools: Optional[list[dict[str, Any]]] = None
    error: Optional[dict[str, Any]] = None
    token_count: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_price: Optional[float] = None


class RemoveMessagesBody(BaseModel):
    ids: list[str]


class AddFilesBody(BaseModel):
    file_ids: list[str]


class UpdatePluginBody(BaseModel):
    type: Optional[str] = None
    api_name: Optional[str] = None
    arguments: Optional[str] = None
    identifier: Optional[str] = None
    state: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    tool_call_id: Optional[str] = None


class UpdateToolMessageBody(BaseModel):
    content: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    plugin_state: Optional[dict[str, Any]] = None
    plugin_error: Optional[Any] = None


class UpdateToolArgsBody(BaseModel):
    tool_call_id: str
    value: Any  # str or dict


class UpdateTTSBody(BaseModel):
    content_md5: Optional[str] = None
    file: Optional[str] = None
    voice: Optional[str] = None


class UpdateTranslateBody(BaseModel):
    content: Optional[str] = None
    from_lang: Optional[str] = None
    to: str


class CompressionGroupBody(BaseModel):
    agent_id: str
    topic_id: str
    message_ids: list[str]
    group_id: Optional[str] = None
    thread_id: Optional[str] = None


class FinalizeCompressionBody(BaseModel):
    agent_id: str
    topic_id: str
    message_group_id: str
    content: str
    group_id: Optional[str] = None
    thread_id: Optional[str] = None


class CancelCompressionBody(BaseModel):
    agent_id: str
    topic_id: str
    message_group_id: str
    group_id: Optional[str] = None
    thread_id: Optional[str] = None


class DateRangeParams(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class MessageContextParams(BaseModel):
    agent_id: Optional[str] = None
    group_id: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    topic_id: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_messages(
    session_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    group_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await _query_messages(
        session,
        user_id,
        MessageContextParams(
            agent_id=agent_id,
            group_id=group_id,
            session_id=session_id,
            thread_id=thread_id,
            topic_id=topic_id,
        ),
        limit=limit,
        offset=offset,
    )


@router.get("/{message_id}")
async def get_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    msg = await _find_msg(session, user_id, message_id)
    if not msg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return _msg_dict(msg)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_message(
    body: CreateMessageBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    metadata = data.pop("metadata", None)
    msg = Message(user_id=user_id, metadata_=metadata, **data)
    session.add(msg)
    await session.flush()
    context = MessageContextParams(
        agent_id=body.agent_id,
        group_id=body.group_id,
        session_id=body.session_id,
        thread_id=body.thread_id,
        topic_id=body.topic_id,
    )
    return {"id": msg.id, "messages": await _query_messages(session, user_id, context)}


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def create_messages_batch(
    messages: list[CreateMessageBody],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    objs: list[Message] = []
    for body in messages:
        msg = Message(user_id=user_id, **body.model_dump(exclude_none=True))
        session.add(msg)
        objs.append(msg)
    await session.flush()  # single round-trip instead of N
    return {"ids": [m.id for m in objs]}


@router.put("/{message_id}")
async def update_message(
    message_id: str,
    body: UpdateMessageBody,
    agent_id: Optional[str] = None,
    group_id: Optional[str] = None,
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    values["updated_at"] = _now()
    stmt = (
        update(Message)
        .where(and_(Message.id == message_id, Message.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return await _mutation_result(
        session,
        user_id,
        MessageContextParams(
            agent_id=agent_id,
            group_id=group_id,
            session_id=session_id,
            thread_id=thread_id,
            topic_id=topic_id,
        ),
    )


@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    agent_id: Optional[str] = None,
    group_id: Optional[str] = None,
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Remove file links
    await session.execute(
        delete(MessageFile).where(
            and_(MessageFile.message_id == message_id, MessageFile.user_id == user_id)
        )
    )
    await session.execute(
        delete(Message).where(and_(Message.id == message_id, Message.user_id == user_id))
    )
    return await _mutation_result(
        session,
        user_id,
        MessageContextParams(
            agent_id=agent_id,
            group_id=group_id,
            session_id=session_id,
            thread_id=thread_id,
            topic_id=topic_id,
        ),
    )


@router.delete("")
async def batch_delete_messages(
    session_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = delete(Message).where(Message.user_id == user_id)
    if session_id:
        stmt = stmt.where(Message.session_id == session_id)
    if topic_id:
        stmt = stmt.where(Message.topic_id == topic_id)
    await session.execute(stmt)
    return {"ok": True}


# ── Frontend path aliases ────────────────────────────────────────────

@router.post("/batch-delete")
async def batch_delete_messages_alias(
    body: RemoveMessagesBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /batch-delete — frontend path."""
    return await remove_messages_batch(body, user_id=user_id, session=session)


@router.post("/compression-group")
async def compression_group_alias(
    body: CompressionGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /compression-group — frontend path."""
    return await create_compression_group(body, user_id=user_id, session=session)


@router.post("/compression-group/cancel")
async def compression_group_cancel_alias(
    body: CancelCompressionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /compression-group/cancel — frontend path."""
    return await cancel_compression(body, user_id=user_id, session=session)


@router.post("/compression-group/finalize")
async def compression_group_finalize_alias(
    body: FinalizeCompressionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: POST /compression-group/finalize — frontend path."""
    return await finalize_compression(body, user_id=user_id, session=session)


@router.put("/tool-arguments")
async def update_tool_arguments_alias(
    body: UpdateToolArgsBody,
    agent_id: Optional[str] = None,
    group_id: Optional[str] = None,
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: PUT /tool-arguments — frontend path updates by toolCallId."""
    stmt = select(MessagePlugin).where(MessagePlugin.tool_call_id == body.tool_call_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        args_str = body.value if isinstance(body.value, str) else str(body.value)
        await session.execute(
            update(MessagePlugin).where(MessagePlugin.id == existing.id).values(arguments=args_str)
        )
    return await _mutation_result(
        session,
        user_id,
        MessageContextParams(
            agent_id=agent_id,
            group_id=group_id,
            session_id=session_id,
            thread_id=thread_id,
            topic_id=topic_id,
        ),
    )


# ── Batch / bulk deletes ─────────────────────────────────────────────

@router.post("/remove-all")
async def remove_all_messages(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(delete(Message).where(Message.user_id == user_id))
    return {"ok": True}


@router.post("/remove-batch")
async def remove_messages_batch(
    body: RemoveMessagesBody,
    agent_id: Optional[str] = None,
    group_id: Optional[str] = None,
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if body.ids:
        await session.execute(
            delete(Message).where(and_(Message.id.in_(body.ids), Message.user_id == user_id))
        )
    return await _mutation_result(
        session,
        user_id,
        MessageContextParams(
            agent_id=agent_id,
            group_id=group_id,
            session_id=session_id,
            thread_id=thread_id,
            topic_id=topic_id,
        ),
    )


@router.post("/remove-by-assistant")
async def remove_messages_by_assistant(
    session_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    group_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = delete(Message).where(Message.user_id == user_id)
    if session_id:
        stmt = stmt.where(Message.session_id == session_id)
    if topic_id:
        stmt = stmt.where(Message.topic_id == topic_id)
    if group_id:
        stmt = stmt.where(Message.message_group_id == group_id)
    await session.execute(stmt)
    return {"ok": True}


@router.post("/remove-by-group")
async def remove_messages_by_group(
    group_id: str = Query(...),
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = delete(Message).where(
        and_(Message.user_id == user_id, Message.message_group_id == group_id)
    )
    if topic_id:
        stmt = stmt.where(Message.topic_id == topic_id)
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/query/{query_id}")
async def remove_message_query(
    query_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        delete(MessageQueryChunk).where(MessageQueryChunk.query_id == query_id)
    )
    await session.execute(
        delete(MessageQuery).where(
            and_(MessageQuery.id == query_id, MessageQuery.user_id == user_id)
        )
    )
    return {"ok": True}


# ── Search & stats ───────────────────────────────────────────────────

@router.get("/search")
async def search_messages(
    keywords: str = Query(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    pattern = f"%{keywords}%"
    stmt = (
        select(Message)
        .where(and_(Message.user_id == user_id, Message.content.ilike(pattern)))
        .order_by(desc(Message.created_at))
        .limit(50)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_msg_dict(r) for r in rows]


@router.get("/count")
async def count_messages(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    stmt = select(func.count()).select_from(Message).where(Message.user_id == user_id)
    if start_date:
        stmt = stmt.where(Message.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Message.created_at <= end_date)
    count = (await session.execute(stmt)).scalar_one()
    return {"count": count}


@router.get("/count-words")
async def count_words(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    stmt = (
        select(func.coalesce(func.sum(func.length(Message.content)), 0))
        .where(Message.user_id == user_id)
    )
    if start_date:
        stmt = stmt.where(Message.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Message.created_at <= end_date)
    total = (await session.execute(stmt)).scalar_one()
    return {"words": total}


@router.get("/heatmaps")
async def get_heatmaps(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import Date, cast, func
    stmt = (
        select(
            cast(Message.created_at, Date).label("date"),
            func.count().label("count"),
        )
        .where(Message.user_id == user_id)
        .group_by("date")
        .order_by("date")
    )
    rows = (await session.execute(stmt)).all()
    return [{"date": str(r.date), "count": r.count} for r in rows]


@router.get("/rank-models")
async def rank_models(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    stmt = (
        select(Message.model, func.count().label("count"))
        .where(and_(Message.user_id == user_id, Message.model.isnot(None)))
        .group_by(Message.model)
        .order_by(desc("count"))
    )
    rows = (await session.execute(stmt)).all()
    return [{"model": r.model, "count": r.count} for r in rows]


@router.get("/all")
async def list_all_messages(
    current: int = 0,
    page_size: int = 50,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(desc(Message.created_at))
        .offset(current * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_msg_dict(r) for r in rows]


# ── Compression ──────────────────────────────────────────────────────

@router.post("/compression/create")
async def create_compression_group(
    body: CompressionGroupBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    group = MessageGroup(
        content="",
        metadata_={"expanded": True},
        type="compression",
        user_id=user_id,
        topic_id=body.topic_id,
    )
    session.add(group)
    await session.flush()
    # Mark messages as belonging to this compression group
    if body.message_ids:
        await session.execute(
            update(Message)
            .where(and_(Message.id.in_(body.message_ids), Message.user_id == user_id))
            .values(message_group_id=group.id)
        )
    context = MessageContextParams(
        agent_id=body.agent_id,
        group_id=body.group_id,
        thread_id=body.thread_id,
        topic_id=body.topic_id,
    )
    return {
        "message_group_id": group.id,
        "messages": await _query_messages(session, user_id, context),
        "messages_to_summarize": await _query_messages_by_ids(session, user_id, body.message_ids),
        "success": True,
    }


@router.post("/compression/cancel")
async def cancel_compression(
    body: CancelCompressionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Unset message_group_id on affected messages
    await session.execute(
        update(Message)
        .where(and_(Message.message_group_id == body.message_group_id, Message.user_id == user_id))
        .values(message_group_id=None)
    )
    # Delete the group
    await session.execute(
        delete(MessageGroup).where(
            and_(MessageGroup.id == body.message_group_id, MessageGroup.user_id == user_id)
        )
    )
    context = MessageContextParams(
        agent_id=body.agent_id,
        group_id=body.group_id,
        thread_id=body.thread_id,
        topic_id=body.topic_id,
    )
    return {"messages": await _query_messages(session, user_id, context), "success": True}


@router.post("/compression/finalize")
async def finalize_compression(
    body: FinalizeCompressionBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(MessageGroup)
        .where(and_(MessageGroup.id == body.message_group_id, MessageGroup.user_id == user_id))
        .values(content=body.content, updated_at=_now())
    )
    context = MessageContextParams(
        agent_id=body.agent_id,
        group_id=body.group_id,
        thread_id=body.thread_id,
        topic_id=body.topic_id,
    )
    return {"messages": await _query_messages(session, user_id, context), "success": True}


# ── File links ───────────────────────────────────────────────────────

@router.post("/{message_id}/files/{file_id}", status_code=status.HTTP_201_CREATED)
async def link_file(
    message_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    link = MessageFile(message_id=message_id, file_id=file_id, user_id=user_id)
    session.add(link)
    await session.flush()
    return {"ok": True}


@router.post("/{message_id}/files")
async def add_files_to_message(
    message_id: str,
    body: AddFilesBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    for fid in body.file_ids:
        link = MessageFile(message_id=message_id, file_id=fid, user_id=user_id)
        session.add(link)
    await session.flush()
    return {"ok": True}


# ── Plugin / Tool updates ────────────────────────────────────────────

@router.put("/{message_id}/plugin")
async def update_message_plugin(
    message_id: str,
    body: UpdatePluginBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Find existing plugin row or create
    stmt = select(MessagePlugin).where(MessagePlugin.id == message_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        values = body.model_dump(exclude_none=True)
        if values:
            await session.execute(
                update(MessagePlugin).where(MessagePlugin.id == existing.id).values(**values)
            )
    else:
        plugin = MessagePlugin(id=message_id, user_id=user_id, **body.model_dump(exclude_none=True))
        session.add(plugin)
        await session.flush()
    return {"ok": True}


@router.put("/{message_id}/plugin-state")
async def update_plugin_state(
    message_id: str,
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(MessagePlugin).where(MessagePlugin.id == message_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        merged = {**(existing.state or {}), **body}
        await session.execute(
            update(MessagePlugin).where(MessagePlugin.id == existing.id).values(state=merged)
        )
    else:
        plugin = MessagePlugin(id=message_id, user_id=user_id, state=body)
        session.add(plugin)
        await session.flush()
    return {"ok": True}


@router.put("/{message_id}/plugin-error")
async def update_plugin_error(
    message_id: str,
    body: Optional[dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(MessagePlugin).where(MessagePlugin.id == message_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        await session.execute(
            update(MessagePlugin).where(MessagePlugin.id == existing.id).values(error=body)
        )
    return {"ok": True}


@router.put("/{message_id}/tool-arguments")
async def update_tool_arguments(
    message_id: str,
    body: UpdateToolArgsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(MessagePlugin).where(MessagePlugin.tool_call_id == body.tool_call_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        args_str = body.value if isinstance(body.value, str) else str(body.value)
        await session.execute(
            update(MessagePlugin).where(MessagePlugin.id == existing.id).values(arguments=args_str)
        )
    return {"ok": True}


@router.put("/{message_id}/tool-message")
async def update_tool_message(
    message_id: str,
    body: UpdateToolMessageBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Update message content/metadata
    msg_values: dict[str, Any] = {"updated_at": _now()}
    if body.content is not None:
        msg_values["content"] = body.content
    if body.metadata is not None:
        msg_values["metadata_"] = body.metadata
    await session.execute(
        update(Message)
        .where(and_(Message.id == message_id, Message.user_id == user_id))
        .values(**msg_values)
    )
    # Update plugin state/error if provided
    if body.plugin_state is not None or body.plugin_error is not None:
        stmt = select(MessagePlugin).where(MessagePlugin.id == message_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            plugin_vals: dict[str, Any] = {}
            if body.plugin_state is not None:
                plugin_vals["state"] = body.plugin_state
            if body.plugin_error is not None:
                plugin_vals["error"] = body.plugin_error
            await session.execute(
                update(MessagePlugin).where(MessagePlugin.id == existing.id).values(**plugin_vals)
            )
    return {"ok": True}


@router.put("/{message_id}/rag")
async def update_message_rag(
    message_id: str,
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    rag_vals: dict[str, Any] = {"updated_at": _now()}
    if "rag_query_id" in body:
        rag_vals["rag_query_id"] = body["rag_query_id"]
    if "search_query_id" in body:
        rag_vals["search_query_id"] = body["search_query_id"]
    await session.execute(
        update(Message)
        .where(and_(Message.id == message_id, Message.user_id == user_id))
        .values(**rag_vals)
    )
    return {"ok": True}


@router.delete("/{message_id}/rag-query")
async def delete_message_rag_query(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a message's RAG query and its chunks."""
    # Get the message's rag_query_id
    msg = (await session.execute(
        select(Message).where(and_(Message.id == message_id, Message.user_id == user_id))
    )).scalar_one_or_none()
    if not msg:
        return {"ok": True}
    query_id = getattr(msg, "rag_query_id", None)
    if query_id:
        await session.execute(delete(MessageQueryChunk).where(MessageQueryChunk.query_id == query_id))
        await session.execute(delete(MessageQuery).where(MessageQuery.id == query_id))
        await session.execute(
            update(Message)
            .where(and_(Message.id == message_id, Message.user_id == user_id))
            .values(rag_query_id=None, updated_at=_now())
        )
    return {"ok": True}


@router.put("/{message_id}/metadata")
async def update_message_metadata(
    message_id: str,
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        update(Message)
        .where(and_(Message.id == message_id, Message.user_id == user_id))
        .values(metadata_=body, updated_at=_now())
    )
    return {"ok": True}


@router.put("/{message_id}/group-metadata")
async def update_message_group_metadata(
    message_id: str,
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # body may contain: {expanded: bool, context: {agentId, topicId, ...}}
    expanded = body.get("expanded")
    if expanded is not None:
        metadata = {"expanded": expanded}
        await session.execute(
            update(MessageGroup)
            .where(and_(MessageGroup.id == message_id, MessageGroup.user_id == user_id))
            .values(metadata_=metadata, updated_at=_now())
        )
    context_body = body.get("context") or {}
    context = MessageContextParams(
        agent_id=context_body.get("agentId") or context_body.get("agent_id"),
        group_id=context_body.get("groupId") or context_body.get("group_id"),
        thread_id=context_body.get("threadId") or context_body.get("thread_id"),
        topic_id=context_body.get("topicId") or context_body.get("topic_id"),
    )
    return {"messages": await _query_messages(session, user_id, context)}


# ── TTS / Translate ──────────────────────────────────────────────────

@router.put("/{message_id}/tts")
async def update_tts(
    message_id: str,
    body: Optional[UpdateTTSBody] = None,
    remove: bool = False,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if remove or body is None:
        await session.execute(
            delete(MessageTts).where(MessageTts.id == message_id)
        )
        return {"ok": True}
    existing = (await session.execute(
        select(MessageTts).where(MessageTts.id == message_id)
    )).scalar_one_or_none()
    if existing:
        body_values = body.model_dump(exclude_none=True)
        vals = {
            ("file_id" if key == "file" else key): value
            for key, value in body_values.items()
        }
        await session.execute(
            update(MessageTts).where(MessageTts.id == existing.id).values(**vals)
        )
    else:
        body_values = body.model_dump(exclude_none=True)
        vals = {
            ("file_id" if key == "file" else key): value
            for key, value in body_values.items()
        }
        tts = MessageTts(id=message_id, user_id=user_id, **vals)
        session.add(tts)
        await session.flush()
    return {"ok": True}


@router.put("/{message_id}/translate")
async def update_translate(
    message_id: str,
    body: Optional[UpdateTranslateBody] = None,
    remove: bool = False,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if remove or body is None:
        await session.execute(
            delete(MessageTranslate).where(MessageTranslate.id == message_id)
        )
        return {"ok": True}
    existing = (await session.execute(
        select(MessageTranslate).where(MessageTranslate.id == message_id)
    )).scalar_one_or_none()
    if existing:
        vals: dict[str, Any] = {}
        if body.content is not None:
            vals["content"] = body.content
        if body.from_lang is not None:
            vals["from_"] = body.from_lang
        if body.to is not None:
            vals["to"] = body.to
        await session.execute(
            update(MessageTranslate).where(MessageTranslate.id == existing.id).values(**vals)
        )
    else:
        tr = MessageTranslate(
            content=body.content,
            from_=body.from_lang,
            id=message_id,
            to=body.to,
            user_id=user_id,
        )
        session.add(tr)
        await session.flush()
    return {"ok": True}


# ── Helpers ──────────────────────────────────────────────────────────

def _has_query_context(ctx: MessageContextParams) -> bool:
    return any([ctx.agent_id, ctx.group_id, ctx.session_id, ctx.thread_id, ctx.topic_id])


async def _mutation_result(
    session: AsyncSession,
    user_id: str,
    ctx: MessageContextParams,
) -> dict[str, Any]:
    if not _has_query_context(ctx):
        return {"success": True}
    return {"messages": await _query_messages(session, user_id, ctx), "success": True}


async def _query_messages_by_ids(
    session: AsyncSession,
    user_id: str,
    ids: list[str],
) -> list[dict[str, Any]]:
    if not ids:
        return []
    rows = (
        await session.execute(
            select(Message)
            .where(and_(Message.id.in_(ids), Message.user_id == user_id))
            .order_by(Message.created_at)
        )
    ).scalars().all()
    return [_msg_dict(row) for row in rows]


async def _query_messages(
    session: AsyncSession,
    user_id: str,
    ctx: MessageContextParams,
    limit: int = 1000,
    offset: int = 0,
) -> list[dict[str, Any]]:
    stmt = select(Message).where(and_(Message.user_id == user_id, Message.message_group_id.is_(None)))
    if ctx.session_id:
        stmt = stmt.where(Message.session_id == ctx.session_id)
    if ctx.topic_id:
        stmt = stmt.where(Message.topic_id == ctx.topic_id)
    if ctx.agent_id:
        stmt = stmt.where(Message.agent_id == ctx.agent_id)
    if ctx.thread_id:
        stmt = stmt.where(Message.thread_id == ctx.thread_id)

    rows = (await session.execute(stmt.order_by(Message.created_at).offset(offset).limit(limit))).scalars().all()
    items = [_msg_dict(row) for row in rows]

    if ctx.topic_id:
        groups = (
            await session.execute(
                select(MessageGroup)
                .where(and_(MessageGroup.user_id == user_id, MessageGroup.topic_id == ctx.topic_id))
                .order_by(MessageGroup.created_at)
            )
        ).scalars().all()

        for group in groups:
            group_messages = await _query_group_messages(session, user_id, group.id)
            items.append(
                {
                    "compressedMessages": group_messages,
                    "content": group.content or "",
                    "created_at": group.created_at.isoformat() if group.created_at else None,
                    "id": group.id,
                    "lastMessageId": group_messages[-1]["id"] if group_messages else None,
                    "metadata": group.metadata_ or {"expanded": True},
                    "role": "compressedGroup",
                    "topic_id": group.topic_id,
                    "updated_at": group.updated_at.isoformat() if group.updated_at else None,
                }
            )

    return sorted(items, key=lambda item: item.get("created_at") or "")


async def _query_group_messages(
    session: AsyncSession,
    user_id: str,
    group_id: str,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(Message)
            .where(and_(Message.user_id == user_id, Message.message_group_id == group_id))
            .order_by(Message.created_at)
        )
    ).scalars().all()
    return [_msg_dict(row) for row in rows]


async def _find_msg(db: AsyncSession, user_id: str, message_id: str) -> Message | None:
    stmt = select(Message).where(and_(Message.id == message_id, Message.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _msg_dict(m: Message) -> dict[str, Any]:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "editor_data": m.editor_data,
        "summary": m.summary,
        "reasoning": m.reasoning,
        "search": m.search,
        "reasoning_content": m.reasoning_content,
        "model": m.model,
        "provider": m.provider,
        "favorite": m.favorite,
        "session_id": m.session_id,
        "topic_id": m.topic_id,
        "agent_id": m.agent_id,
        "parent_id": m.parent_id,
        "quota_id": m.quota_id,
        "group_id": m.group_id,
        "target_id": m.target_id,
        "thread_id": m.thread_id,
        "message_group_id": m.message_group_id,
        "tool_call_id": m.tool_call_id,
        "tools": m.tools,
        "metadata": m.metadata_,
        "error": m.error,
        "trace_id": m.trace_id,
        "observation_id": m.observation_id,
        "token_count": m.token_count,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "total_price": m.total_price,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
