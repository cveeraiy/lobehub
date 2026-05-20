"""Document router — CRUD for documents within knowledge bases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent_ops import AgentDocument
from app.models.document_ext import DocumentHistory
from app.models.file import Document
from app.models.rag import Chunk, DocumentChunk, Embedding
from app.models.topic_ext import TopicDocument
from app.services.rag_parsing import parse_document_to_chunks, parse_file_to_chunks

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────

class CreateDocumentBody(BaseModel):
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    editor_data: Optional[str] = None  # JSON string
    source_type: Optional[str] = None
    source: Optional[str] = None
    file_type: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    parent_id: Optional[str] = None
    slug: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class UpdateDocumentBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    editor_data: Optional[str] = None  # JSON string
    slug: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class BatchDeleteDocumentsBody(BaseModel):
    ids: list[str]


class BatchCreateDocumentsBody(BaseModel):
    documents: list[CreateDocumentBody]


class SaveDocumentHistoryBody(BaseModel):
    document_id: str
    editor_data: str  # JSON string
    save_source: str = "manual"


class ParseBody(BaseModel):
    skip_exist: Optional[bool] = None
    skipExist: Optional[bool] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def create_documents_batch(
    body: BatchCreateDocumentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Batch create documents."""
    created_ids = []
    for doc_input in body.documents:
        editor_data = None
        if doc_input.editor_data:
            import json
            editor_data = json.loads(doc_input.editor_data)

        # Resolve parentId if it's a slug
        parent_id = doc_input.parent_id
        if parent_id:
            parent_doc = (await session.execute(
                select(Document).where(
                    and_(Document.slug == parent_id, Document.user_id == user_id)
                )
            )).scalar_one_or_none()
            if parent_doc:
                parent_id = parent_doc.id

        doc = Document(
            user_id=user_id,
            title=doc_input.title,
            description=doc_input.description,
            content=doc_input.content,
            editor_data=editor_data,
            file_type=doc_input.file_type or "document",
            source_type=doc_input.source_type or "api",
            source=doc_input.source or "api",
            knowledge_base_id=doc_input.knowledge_base_id,
            parent_id=parent_id,
            slug=doc_input.slug,
            metadata_=doc_input.metadata,
            total_char_count=len(doc_input.content or ""),
            total_line_count=(doc_input.content or "").count("\n") + 1,
        )
        session.add(doc)
        await session.flush()
        created_ids.append(doc.id)
    return {"ids": created_ids}


@router.get("/query")
async def query_documents(
    current: int = 1,
    page_size: int = 20,
    file_types: Optional[str] = None,
    source_types: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Query documents with pagination and filters."""
    stmt = select(Document).where(Document.user_id == user_id)
    if file_types:
        ft_list = file_types.split(",")
        stmt = stmt.where(Document.file_type.in_(ft_list))
    if source_types:
        st_list = source_types.split(",")
        stmt = stmt.where(Document.source_type.in_(st_list))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(desc(Document.updated_at)).offset((current - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_doc_dict(d) for d in rows], "total": total}


@router.get("/by-slug/{slug}")
async def get_document_by_slug(
    slug: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    doc = (await session.execute(
        select(Document).where(and_(Document.slug == slug, Document.user_id == user_id))
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return _doc_dict(doc)


@router.get("/breadcrumb/{slug}")
async def get_breadcrumb_alias(
    slug: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /breadcrumb/{slug} — frontend path."""
    return await get_folder_breadcrumb(slug, user_id=user_id, session=session)


@router.get("/folder-breadcrumb/{slug}")
async def get_folder_breadcrumb(
    slug: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Build breadcrumb chain from slug to root."""
    chain: list[dict[str, Any]] = []
    current = (await session.execute(
        select(Document).where(and_(Document.slug == slug, Document.user_id == user_id))
    )).scalar_one_or_none()
    while current:
        chain.insert(0, {
            "id": current.id,
            "name": current.title or current.filename or "Untitled",
            "slug": current.slug or current.id,
        })
        if current.parent_id:
            current = (await session.execute(
                select(Document).where(
                    and_(Document.id == current.parent_id, Document.user_id == user_id)
                )
            )).scalar_one_or_none()
        else:
            break
    return chain


@router.get("/history/compare")
async def compare_history_alias(
    leftId: Optional[str] = None,
    rightId: Optional[str] = None,
    left_id: Optional[str] = None,
    right_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /history/compare — frontend path (query params)."""
    return await compare_document_history_items(
        left_id=leftId or left_id,
        right_id=rightId or right_id,
        user_id=user_id,
        session=session,
    )


@router.get("/history/item")
async def get_history_item_alias(
    historyId: Optional[str] = None,
    history_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /history/item — frontend path (query param)."""
    hid = historyId or history_id
    if not hid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "historyId is required")
    return await get_document_history_item(hid, user_id=user_id, session=session)


@router.get("/history")
async def list_history_alias(
    documentId: Optional[str] = None,
    document_id: Optional[str] = None,
    beforeSavedAt: Optional[str] = None,
    before_saved_at: Optional[str] = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Alias: GET /history — frontend path (query params)."""
    did = documentId or document_id
    if not did:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "documentId is required")
    return await list_document_history(
        did,
        before_saved_at=beforeSavedAt or before_saved_at,
        limit=limit,
        user_id=user_id,
        session=session,
    )


@router.get("/history/{document_id}")
async def list_document_history(
    document_id: str,
    before_saved_at: Optional[str] = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List document history items."""
    stmt = select(DocumentHistory).where(
        and_(DocumentHistory.document_id == document_id, DocumentHistory.user_id == user_id)
    )
    if before_saved_at:
        stmt = stmt.where(DocumentHistory.saved_at < before_saved_at)
    stmt = stmt.order_by(desc(DocumentHistory.saved_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": h.id,
            "document_id": h.document_id,
            "save_source": h.save_source,
            "saved_at": h.saved_at.isoformat() if h.saved_at else None,
        }
        for h in rows
    ]


@router.get("/history-item/{history_id}")
async def get_document_history_item(
    history_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific document history entry with editor data."""
    h = (await session.execute(
        select(DocumentHistory).where(
            and_(DocumentHistory.id == history_id, DocumentHistory.user_id == user_id)
        )
    )).scalar_one_or_none()
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "History item not found")
    return {
        "id": h.id,
        "document_id": h.document_id,
        "editor_data": h.editor_data,
        "save_source": h.save_source,
        "saved_at": h.saved_at.isoformat() if h.saved_at else None,
    }


@router.get("/history-compare")
async def compare_document_history_items(
    left_id: str = None,
    right_id: str = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Compare two document history items."""
    left = right = None
    if left_id:
        left = (await session.execute(
            select(DocumentHistory).where(
                and_(DocumentHistory.id == left_id, DocumentHistory.user_id == user_id)
            )
        )).scalar_one_or_none()
    if right_id:
        right = (await session.execute(
            select(DocumentHistory).where(
                and_(DocumentHistory.id == right_id, DocumentHistory.user_id == user_id)
            )
        )).scalar_one_or_none()
    return {
        "left": {
            "id": left.id,
            "editor_data": left.editor_data,
            "saved_at": left.saved_at.isoformat() if left.saved_at else None,
        } if left else None,
        "right": {
            "id": right.id,
            "editor_data": right.editor_data,
            "saved_at": right.saved_at.isoformat() if right.saved_at else None,
        } if right else None,
    }


@router.post("/history", status_code=status.HTTP_201_CREATED)
async def save_document_history(
    body: SaveDocumentHistoryBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Save a document history snapshot."""
    import json
    editor_data = json.loads(body.editor_data)
    history = DocumentHistory(
        document_id=body.document_id,
        user_id=user_id,
        editor_data=editor_data,
        save_source=body.save_source,
        saved_at=_now(),
    )
    session.add(history)
    await session.flush()
    return {"id": history.id}


@router.post("/{document_id}/parse")
async def parse_document(
    document_id: str,
    body: Optional[ParseBody] = Body(default=None),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Parse a document into chunks."""
    doc = await _find_doc(session, user_id, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    skip = bool(body and (body.skip_exist or body.skipExist))
    return await parse_document_to_chunks(session, user_id, doc, skip_exist=skip)


@router.post("/parse-file/{file_id}")
async def parse_file_content(
    file_id: str,
    skip_exist: bool = False,
    body: Optional[ParseBody] = Body(default=None),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Parse file content into a document and chunks."""
    skip = skip_exist or bool(body and (body.skip_exist or body.skipExist))
    result = await parse_file_to_chunks(session, user_id, file_id, skip_exist=skip)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    body: CreateDocumentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    editor_data = None
    if body.editor_data:
        import json
        editor_data = json.loads(body.editor_data)

    parent_id = body.parent_id
    if parent_id:
        parent_doc = (await session.execute(
            select(Document).where(
                and_(Document.slug == parent_id, Document.user_id == user_id)
            )
        )).scalar_one_or_none()
        if parent_doc:
            parent_id = parent_doc.id

    doc = Document(
        user_id=user_id,
        title=body.title,
        description=body.description,
        content=body.content,
        editor_data=editor_data,
        file_type=body.file_type or "document",
        source_type=body.source_type or "api",
        source=body.source or "api",
        knowledge_base_id=body.knowledge_base_id,
        parent_id=parent_id,
        slug=body.slug,
        metadata_=body.metadata,
        total_char_count=len(body.content or ""),
        total_line_count=(body.content or "").count("\n") + 1,
    )
    session.add(doc)
    await session.flush()
    return {"id": doc.id}


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
    values: dict[str, Any] = {}
    if body.title is not None:
        values["title"] = body.title
    if body.description is not None:
        values["description"] = body.description
    if body.content is not None:
        values["content"] = body.content
        values["total_char_count"] = len(body.content)
        values["total_line_count"] = body.content.count("\n") + 1
    if body.editor_data is not None:
        import json
        values["editor_data"] = json.loads(body.editor_data)
    if body.slug is not None:
        values["slug"] = body.slug
    if body.metadata is not None:
        values["metadata_"] = body.metadata
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

    # Delete junction rows
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    if chunk_ids:
        await session.execute(delete(Chunk).where(Chunk.id.in_(chunk_ids)))
    # Delete history entries
    await session.execute(delete(DocumentHistory).where(DocumentHistory.document_id == document_id))
    # Delete agent_documents references
    await session.execute(delete(AgentDocument).where(AgentDocument.document_id == document_id))
    # Delete topic_documents references
    await session.execute(delete(TopicDocument).where(TopicDocument.document_id == document_id))
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


@router.post("/remove-all")
async def remove_all_documents(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Get all document IDs for user
    doc_ids = (await session.execute(
        select(Document.id).where(Document.user_id == user_id)
    )).scalars().all()
    if doc_ids:
        chunk_ids = (await session.execute(
            select(DocumentChunk.chunk_id).where(DocumentChunk.document_id.in_(doc_ids))
        )).scalars().all()
        if chunk_ids:
            await session.execute(delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids)))
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids)))
        if chunk_ids:
            await session.execute(delete(Chunk).where(Chunk.id.in_(chunk_ids)))
        await session.execute(delete(DocumentHistory).where(DocumentHistory.document_id.in_(doc_ids)))
        await session.execute(delete(Document).where(Document.user_id == user_id))
    return {"ok": True}


@router.post("/batch-delete")
async def batch_delete_documents(
    body: BatchDeleteDocumentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not body.ids:
        return {"ok": True}
    chunk_ids = (await session.execute(
        select(DocumentChunk.chunk_id).where(DocumentChunk.document_id.in_(body.ids))
    )).scalars().all()
    if chunk_ids:
        await session.execute(delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids)))
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(body.ids)))
    if chunk_ids:
        await session.execute(delete(Chunk).where(Chunk.id.in_(chunk_ids)))
    await session.execute(delete(DocumentHistory).where(DocumentHistory.document_id.in_(body.ids)))
    await session.execute(
        delete(Document).where(and_(Document.id.in_(body.ids), Document.user_id == user_id))
    )
    return {"ok": True}


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
