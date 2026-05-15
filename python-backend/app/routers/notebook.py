"""Notebook router — create/update/delete documents linked to topics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.file import Document
from app.models.topic_ext import TopicDocument

router = APIRouter(prefix="/api/notebook", tags=["Notebook"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CreateDocumentBody(BaseModel):
    title: str
    content: str
    topic_id: str
    description: Optional[str] = None
    type: str = "markdown"  # 'article' | 'markdown' | 'note' | 'report'
    source: str = "notebook"
    metadata: Optional[dict[str, Any]] = None


class UpdateDocumentBody(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None


@router.get("/documents")
async def list_notebook_documents(
    topic_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List notebook documents, optionally by topic."""
    if topic_id:
        stmt = (
            select(Document)
            .join(TopicDocument, TopicDocument.document_id == Document.id)
            .where(and_(TopicDocument.topic_id == topic_id, Document.user_id == user_id))
            .order_by(desc(Document.updated_at))
        )
    else:
        stmt = (
            select(Document)
            .where(and_(Document.user_id == user_id, Document.source_type == "api"))
            .order_by(desc(Document.updated_at))
        )
    rows = (await session.execute(stmt)).scalars().all()
    return [_doc_dict(d) for d in rows]


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def create_notebook_document(
    body: CreateDocumentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a document and associate it with a topic."""
    doc = Document(
        user_id=user_id,
        title=body.title,
        content=body.content,
        description=body.description,
        file_type=body.type,
        source="notebook" if body.source == "notebook" else body.source,
        source_type="api",
        total_char_count=len(body.content),
        total_line_count=body.content.count("\n") + 1,
        metadata_=body.metadata,
    )
    session.add(doc)
    await session.flush()

    # Associate with topic
    assoc = TopicDocument(
        topic_id=body.topic_id,
        document_id=doc.id,
        user_id=user_id,
    )
    session.add(assoc)
    await session.flush()

    return {"id": doc.id}


@router.get("/documents/{document_id}")
async def get_notebook_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(and_(Document.id == document_id, Document.user_id == user_id))
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return _doc_dict(doc, include_content=True)


@router.put("/documents/{document_id}")
async def update_notebook_document(
    document_id: str,
    body: UpdateDocumentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values: dict[str, Any] = {}
    if body.title is not None:
        values["title"] = body.title
    if body.content is not None:
        values["content"] = body.content
        values["total_char_count"] = len(body.content)
        values["total_line_count"] = body.content.count("\n") + 1
    if body.description is not None:
        values["description"] = body.description
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    await session.execute(
        update(Document)
        .where(and_(Document.id == document_id, Document.user_id == user_id))
        .values(**values)
    )
    return {"ok": True}


@router.delete("/documents/{document_id}")
async def delete_notebook_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Remove topic associations
    await session.execute(
        delete(TopicDocument).where(TopicDocument.document_id == document_id)
    )
    # Delete document
    await session.execute(
        delete(Document).where(and_(Document.id == document_id, Document.user_id == user_id))
    )
    return {"ok": True}


def _doc_dict(d: Document, include_content: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": d.id,
        "title": d.title,
        "description": d.description,
        "file_type": d.file_type,
        "total_char_count": d.total_char_count,
        "total_line_count": d.total_line_count,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }
    if include_content:
        result["content"] = d.content
    return result
