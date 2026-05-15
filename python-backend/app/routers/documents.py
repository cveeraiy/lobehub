"""Document router — CRUD for documents within knowledge bases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.file import Document
from app.models.rag import Chunk, DocumentChunk, Embedding

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Schemas ──────────────────────────────────────────────────────────

class UpdateDocumentBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_documents(
    knowledge_base_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List documents, optionally filtered by knowledge base."""
    stmt = select(Document).where(Document.user_id == user_id)
    if knowledge_base_id:
        stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
    stmt = stmt.order_by(desc(Document.created_at))
    rows = (await session.execute(stmt)).scalars().all()
    return [_doc_dict(d) for d in rows]


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    doc = await _find_doc(session, user_id, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return _doc_dict(doc)


@router.put("/{document_id}")
async def update_document(
    document_id: str,
    body: UpdateDocumentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    values = body.model_dump(exclude_none=True)
    if not values:
        return {"ok": True}
    values["updated_at"] = _now()
    stmt = (
        update(Document)
        .where(and_(Document.id == document_id, Document.user_id == user_id))
        .values(**values)
    )
    await session.execute(stmt)
    return {"ok": True}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete document and its associated chunks/embeddings."""
    # Find chunk IDs linked to this document
    chunk_ids_stmt = select(DocumentChunk.chunk_id).where(DocumentChunk.document_id == document_id)
    chunk_ids = (await session.execute(chunk_ids_stmt)).scalars().all()

    if chunk_ids:
        # Delete embeddings for those chunks
        await session.execute(delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids)))
        # Delete chunks
        await session.execute(delete(Chunk).where(Chunk.id.in_(chunk_ids)))

    # Delete junction rows
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    # Delete the document
    await session.execute(
        delete(Document).where(and_(Document.id == document_id, Document.user_id == user_id))
    )
    return {"ok": True}


@router.get("/{document_id}/chunks")
async def list_document_chunks(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List all chunks belonging to a document."""
    stmt = (
        select(Chunk)
        .join(DocumentChunk, DocumentChunk.chunk_id == Chunk.id)
        .where(DocumentChunk.document_id == document_id)
        .order_by(Chunk.index)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": c.id,
            "text": c.text,
            "abstract": c.abstract,
            "index": c.index,
            "type": c.type,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]


@router.get("/{document_id}/stats")
async def document_stats(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Return chunk count and total chars for a document."""
    chunk_count = (
        await session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
    ).scalar_one()
    doc = await _find_doc(session, user_id, document_id)
    return {
        "chunk_count": chunk_count,
        "total_char_count": doc.total_char_count if doc else 0,
        "total_line_count": doc.total_line_count if doc else 0,
    }


# ── Helpers ──────────────────────────────────────────────────────────

async def _find_doc(db: AsyncSession, user_id: str, doc_id: str) -> Document | None:
    stmt = select(Document).where(and_(Document.id == doc_id, Document.user_id == user_id))
    return (await db.execute(stmt)).scalar_one_or_none()


def _doc_dict(d: Document) -> dict[str, Any]:
    return {
        "id": d.id,
        "title": d.title,
        "description": d.description,
        "filename": d.filename,
        "file_type": d.file_type,
        "source_type": d.source_type,
        "source": d.source,
        "knowledge_base_id": d.knowledge_base_id,
        "total_char_count": d.total_char_count,
        "total_line_count": d.total_line_count,
        "slug": d.slug,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }
