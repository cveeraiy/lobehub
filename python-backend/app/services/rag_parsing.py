"""Lightweight RAG parsing and search helpers for REST parity.

This module intentionally handles the local, deterministic path: chunk
document text, create file-backed documents from stored metadata, and provide a
lexical fallback when vector embeddings are unavailable.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import Document, File
from app.models.knowledge import KnowledgeBaseFile
from app.models.rag import Chunk, DocumentChunk, Embedding
from app.services import knowledge_service
from app.services.file_service import S3Client

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 1200
_DEFAULT_CHUNK_OVERLAP = 120


def split_text(text: str, *, chunk_size: int = _DEFAULT_CHUNK_SIZE, overlap: int = _DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split text into stable chunks with a small overlap."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs or [cleaned]:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + chunk_size].strip())
                start += max(chunk_size - overlap, 1)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = paragraph

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk]


async def clear_document_chunks(session: AsyncSession, document_id: str) -> None:
    chunk_ids = (
        await session.execute(select(DocumentChunk.chunk_id).where(DocumentChunk.document_id == document_id))
    ).scalars().all()
    if not chunk_ids:
        return

    await session.execute(delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids)))
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    await session.execute(delete(Chunk).where(Chunk.id.in_(chunk_ids)))


async def parse_document_to_chunks(
    session: AsyncSession,
    user_id: str,
    document: Document,
    *,
    skip_exist: bool = False,
) -> dict[str, Any]:
    existing_count = (
        await session.execute(select(DocumentChunk.chunk_id).where(DocumentChunk.document_id == document.id))
    ).scalars().all()
    if existing_count and skip_exist:
        return {
            "id": document.id,
            "content": document.content or "",
            "metadata": document.metadata_,
            "chunkCount": len(existing_count),
            "chunksCreated": 0,
        }

    await clear_document_chunks(session, document.id)

    content = document.content or ""
    chunks = await knowledge_service.create_chunks(
        session,
        user_id,
        split_text(content),
        document_id=document.id,
        metadata={
            "documentId": document.id,
            "fileId": document.file_id,
            "fileName": document.title or document.filename,
            "knowledgeBaseId": document.knowledge_base_id,
        },
    )
    await session.execute(
        update(Document)
        .where(and_(Document.id == document.id, Document.user_id == user_id))
        .values(
            total_char_count=len(content),
            total_line_count=content.count("\n") + 1 if content else 0,
        )
    )

    return {
        "id": document.id,
        "content": content,
        "metadata": document.metadata_,
        "chunkCount": len(chunks),
        "chunksCreated": len(chunks),
    }


def _content_from_file_metadata(file: File) -> str:
    metadata = file.metadata_ or {}
    for key in ("content", "text", "preview", "description"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def _extract_text_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return ""


async def _content_from_file_storage(file: File) -> str:
    if not file.url or file.url.startswith(("http://", "https://")):
        return ""

    try:
        data = await S3Client.from_settings().get_bytes(file.url)
    except Exception:
        logger.exception("Failed to read file bytes for parsing: %s", file.id)
        return ""

    file_type = (file.file_type or "").lower()
    filename = (file.name or "").lower()
    try:
        if file_type == "application/pdf" or filename.endswith(".pdf"):
            return _extract_pdf_text(data)
        if file_type.startswith("text/") or filename.endswith((".md", ".markdown", ".txt", ".csv", ".json")):
            return _extract_text_bytes(data)
    except Exception:
        logger.exception("Failed to extract text for file: %s", file.id)

    return ""


async def _content_from_file(file: File) -> str:
    return _content_from_file_metadata(file) or await _content_from_file_storage(file)


async def ensure_document_for_file(session: AsyncSession, user_id: str, file: File) -> Document:
    existing = (
        await session.execute(select(Document).where(and_(Document.file_id == file.id, Document.user_id == user_id)))
    ).scalar_one_or_none()
    if existing:
        if not (existing.content or "").strip():
            content = await _content_from_file(file)
            if content:
                existing.content = content
                existing.total_char_count = len(content)
                existing.total_line_count = content.count("\n") + 1
                await session.flush()
        return existing

    content = await _content_from_file(file)
    document = Document(
        user_id=user_id,
        title=file.name,
        content=content,
        file_type=file.file_type,
        filename=file.name,
        total_char_count=len(content),
        total_line_count=content.count("\n") + 1 if content else 0,
        metadata_=file.metadata_,
        source_type="file",
        source=file.url,
        file_id=file.id,
    )
    session.add(document)
    await session.flush()
    return document


async def parse_file_to_chunks(
    session: AsyncSession,
    user_id: str,
    file_id: str,
    *,
    skip_exist: bool = False,
) -> dict[str, Any] | None:
    file = (
        await session.execute(select(File).where(and_(File.id == file_id, File.user_id == user_id)))
    ).scalar_one_or_none()
    if not file:
        return None

    document = await ensure_document_for_file(session, user_id, file)
    result = await parse_document_to_chunks(session, user_id, document, skip_exist=skip_exist)
    result["fileId"] = file.id
    result["filename"] = file.name
    return result


def _score_text(query_terms: list[str], text: str) -> float:
    lower = text.lower()
    if not query_terms:
        return 0.0
    hits = sum(lower.count(term) for term in query_terms)
    coverage = sum(1 for term in query_terms if term in lower) / len(query_terms)
    return coverage + min(hits / 20, 0.5)


async def lexical_search_chunks(
    session: AsyncSession,
    user_id: str,
    query: str,
    *,
    limit: int = 10,
    file_ids: list[str] | None = None,
    kb_ids: list[str] | None = None,
    document_id: str | None = None,
) -> list[dict[str, Any]]:
    terms = [term.lower() for term in re.findall(r"\w+", query or "") if len(term) > 1]

    stmt = (
        select(Chunk, Document, File)
        .join(DocumentChunk, DocumentChunk.chunk_id == Chunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .outerjoin(File, File.id == Document.file_id)
        .where(Chunk.user_id == user_id)
    )
    if document_id:
        stmt = stmt.where(Document.id == document_id)
    if file_ids:
        stmt = stmt.where(or_(Document.file_id.in_(file_ids), Document.id.in_(file_ids)))
    if kb_ids:
        kb_file_ids = select(KnowledgeBaseFile.file_id).where(
            and_(KnowledgeBaseFile.knowledge_base_id.in_(kb_ids), KnowledgeBaseFile.user_id == user_id)
        )
        stmt = stmt.where(or_(Document.knowledge_base_id.in_(kb_ids), Document.file_id.in_(kb_file_ids)))

    rows = (await session.execute(stmt)).all()
    ranked: list[dict[str, Any]] = []
    for chunk, document, file in rows:
        text = chunk.text or ""
        score = _score_text(terms, text)
        if terms and score <= 0:
            continue
        file_id = file.id if file else document.file_id or document.id
        file_name = file.name if file else document.title or document.filename or "Untitled"
        ranked.append(
            {
                "id": chunk.id,
                "text": text,
                "metadata": chunk.metadata_,
                "index": chunk.index,
                "similarity": score,
                "fileId": file_id,
                "fileName": file_name,
                "documentId": document.id,
            }
        )

    ranked.sort(key=lambda item: (item.get("similarity") or 0, -(item.get("index") or 0)), reverse=True)
    return ranked[:limit]


def group_and_rank_files(chunks: list[dict[str, Any]], *, top_k: int = 3) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        file_id = chunk.get("fileId") or chunk.get("documentId")
        if not file_id:
            continue
        entry = grouped.setdefault(
            file_id,
            {
                "fileId": file_id,
                "fileName": chunk.get("fileName") or "Untitled",
                "relevanceScore": 0.0,
                "topChunks": [],
            },
        )
        entry["relevanceScore"] = max(float(entry["relevanceScore"]), float(chunk.get("similarity") or 0))
        if len(entry["topChunks"]) < top_k:
            entry["topChunks"].append(chunk)

    return sorted(grouped.values(), key=lambda item: item["relevanceScore"], reverse=True)
