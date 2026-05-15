"""Agent Documents router — agent-scoped document CRUD (SOUL.md, plan, skills).

Uses the agent_documents junction table to bind documents to agents with
access control and loading policy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent_ops import AgentDocument
from app.models.file import Document

router = APIRouter(prefix="/api/agents/{agent_id}/documents", tags=["Agent Documents"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LinkDocumentBody(BaseModel):
    document_id: str
    policy_load: str = "lazy"  # 'eager' | 'lazy' | 'disabled'
    access_mask: int = 0


class CreateAgentDocBody(BaseModel):
    title: str
    content: str
    file_type: str = "markdown"
    policy_load: str = "eager"


class UpdatePolicyBody(BaseModel):
    policy_load: Optional[str] = None
    access_mask: Optional[int] = None


@router.get("")
async def list_agent_documents(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List documents bound to an agent."""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(AgentDocument.agent_id == agent_id, AgentDocument.user_id == user_id, AgentDocument.deleted_at.is_(None)))
        .order_by(desc(AgentDocument.created_at))
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": ad.id,
            "document_id": ad.document_id,
            "policy_load": ad.policy_load,
            "access_mask": ad.access_mask,
            "title": doc.title,
            "file_type": doc.file_type,
            "total_char_count": doc.total_char_count,
            "created_at": ad.created_at.isoformat() if ad.created_at else None,
        }
        for ad, doc in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent_document(
    agent_id: str,
    body: CreateAgentDocBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a new document and bind it to the agent."""
    doc = Document(
        user_id=user_id,
        title=body.title,
        content=body.content,
        file_type=body.file_type,
        source="agent",
        source_type="api",
        total_char_count=len(body.content),
        total_line_count=body.content.count("\n") + 1,
    )
    session.add(doc)
    await session.flush()

    link = AgentDocument(
        agent_id=agent_id,
        document_id=doc.id,
        user_id=user_id,
        policy_load=body.policy_load,
    )
    session.add(link)
    await session.flush()
    return {"id": link.id, "document_id": doc.id}


@router.post("/link", status_code=status.HTTP_201_CREATED)
async def link_existing_document(
    agent_id: str,
    body: LinkDocumentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Link an existing document to an agent."""
    link = AgentDocument(
        agent_id=agent_id,
        document_id=body.document_id,
        user_id=user_id,
        policy_load=body.policy_load,
        access_mask=body.access_mask,
    )
    session.add(link)
    await session.flush()
    return {"id": link.id}


@router.put("/{link_id}")
async def update_agent_document_policy(
    agent_id: str,
    link_id: str,
    body: UpdatePolicyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update loading policy or access mask for an agent-document binding."""
    values: dict[str, Any] = {}
    if body.policy_load is not None:
        values["policy_load"] = body.policy_load
    if body.access_mask is not None:
        values["access_mask"] = body.access_mask
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(AgentDocument)
        .where(and_(AgentDocument.id == link_id, AgentDocument.agent_id == agent_id, AgentDocument.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/{link_id}")
async def unlink_agent_document(
    agent_id: str,
    link_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete (unlink) a document from an agent."""
    await session.execute(
        update(AgentDocument)
        .where(and_(AgentDocument.id == link_id, AgentDocument.agent_id == agent_id, AgentDocument.user_id == user_id))
        .values(deleted_at=_now())
    )
    return {"ok": True}


@router.get("/{link_id}/content")
async def get_agent_document_content(
    agent_id: str,
    link_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get the full content of an agent's document."""
    stmt = (
        select(Document)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(AgentDocument.id == link_id, AgentDocument.agent_id == agent_id, AgentDocument.user_id == user_id))
    )
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return {"id": doc.id, "title": doc.title, "content": doc.content}
