"""OpenAPI v1 message translation routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.message import Message
from app.models.message_ext import MessageTranslate
from app.services.system_agent.service import SystemAgentService

router = APIRouter(prefix="/api/v1/message-translations", tags=["OpenAPI Message Translations"])


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _success(data: Any = None, message: str | None = None) -> dict[str, Any]:
    return {"data": data, "message": message, "success": True, "timestamp": _now().isoformat()}


class TranslationTriggerBody(BaseModel):
    from_: str | None = Field(None, alias="from")
    model: str | None = None
    provider: str | None = None
    to: str

    model_config = {"populate_by_name": True}


class TranslationUpdateBody(BaseModel):
    content: str | None = None
    from_: str | None = Field(None, alias="from")
    model: str | None = None
    provider: str | None = None
    to: str | None = None

    model_config = {"populate_by_name": True}


async def _find_message(session: AsyncSession, user_id: str, message_id: str) -> Message:
    message = (
        await session.execute(select(Message).where(and_(Message.id == message_id, Message.user_id == user_id)))
    ).scalar_one_or_none()
    if not message:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return message


async def _find_translate(session: AsyncSession, message_id: str) -> MessageTranslate | None:
    return (
        await session.execute(select(MessageTranslate).where(MessageTranslate.id == message_id))
    ).scalar_one_or_none()


def _translate_dict(row: MessageTranslate | None, *, message_id: str, user_id: str) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "clientId": None,
        "content": row.content,
        "from": row.from_,
        "id": message_id,
        "messageId": message_id,
        "to": row.to,
        "userId": user_id,
    }


@router.get("/{message_id}")
async def get_message_translation(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await _find_message(session, user_id, message_id)
    row = await _find_translate(session, message_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Translation not found")
    return _success(
        _translate_dict(row, message_id=message_id, user_id=user_id),
        "Get message translation successfully",
    )


@router.patch("/{message_id}")
async def update_message_translation(
    message_id: str,
    body: TranslationUpdateBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await _find_message(session, user_id, message_id)
    row = await _find_translate(session, message_id)
    if row:
        values: dict[str, Any] = {}
        if body.content is not None:
            values["content"] = body.content
        if body.from_ is not None:
            values["from_"] = body.from_
        if body.to is not None:
            values["to"] = body.to
        await session.execute(update(MessageTranslate).where(MessageTranslate.id == row.id).values(**values))
        await session.flush()
        row = await _find_translate(session, message_id)
    else:
        row = MessageTranslate(
            content=body.content,
            from_=body.from_,
            id=message_id,
            to=body.to,
            user_id=user_id,
        )
        session.add(row)
        await session.flush()
    return _success(
        _translate_dict(row, message_id=message_id, user_id=user_id),
        "Update message translation successfully",
    )


@router.post("/{message_id}")
async def translate_message(
    message_id: str,
    body: TranslationTriggerBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    message = await _find_message(session, user_id, message_id)
    content = message.content or ""
    translated = None
    try:
        translated = await SystemAgentService(session, user_id).translate_text(
            content,
            target_locale=body.to,
            source_locale=body.from_,
        )
    except Exception:
        translated = None
    if translated is None:
        translated = content
    update_body = TranslationUpdateBody(content=translated, from_=body.from_, to=body.to)
    return await update_message_translation(message_id, update_body, user_id, session)


@router.delete("/{message_id}")
async def delete_message_translation(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await _find_message(session, user_id, message_id)
    await session.execute(delete(MessageTranslate).where(MessageTranslate.id == message_id))
    return _success({"deleted": True, "messageId": message_id}, "Delete message translation successfully")
