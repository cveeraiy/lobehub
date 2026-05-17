"""Agent Documents router — agent-scoped document CRUD (SOUL.md, plan, skills).

Uses the agent_documents junction table to bind documents to agents with
access control and loading policy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent_ops import AgentDocument
from app.models.file import Document
from app.models.topic import Topic
from app.models.topic_ext import TopicDocument

router = APIRouter(prefix="/api/agents/{agent_id}/documents", tags=["Agent Documents"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LinkDocumentBody(BaseModel):
    document_id: str
    policy_load: str = "lazy"  # 'eager' | 'lazy' | 'disabled'


class CreateAgentDocBody(BaseModel):
    title: str
    content: str
    file_type: str = "markdown"
    policy_load: str = "eager"


class UpdatePolicyBody(BaseModel):
    policy_load: Optional[str] = None
    access_self: Optional[int] = None


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
            "access_self": ad.access_self,
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
        access_self=getattr(body, 'access_self', 31),
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
    if body.access_self is not None:
        values["access_self"] = body.access_self
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


# ── VFS-like endpoints ───────────────────────────────────────────────

class VfsListBody(BaseModel):
    path: str = "/"
    recursive: bool = False


class VfsStatBody(BaseModel):
    path: str


class VfsReadBody(BaseModel):
    path: str


class VfsWriteBody(BaseModel):
    path: str
    content: str
    create_if_missing: bool = True


class VfsMkdirBody(BaseModel):
    path: str


class VfsRenameBody(BaseModel):
    from_path: str
    to_path: str


class VfsCopyBody(BaseModel):
    from_path: str
    to_path: str


class VfsDeleteBody(BaseModel):
    paths: list[str]
    permanent: bool = False


class VfsTrashListBody(BaseModel):
    limit: int = 50


class VfsRestoreBody(BaseModel):
    link_ids: list[str]


class VfsEmptyTrashBody(BaseModel):
    pass


class SkillByPathBody(BaseModel):
    path: str
    title: Optional[str] = None
    content: Optional[str] = None


class DocByIdBody(BaseModel):
    document_id: str


class DocCreateBody(BaseModel):
    title: str
    content: str
    file_type: str = "markdown"
    path: Optional[str] = None


class DocModifyBody(BaseModel):
    document_id: str
    content: Optional[str] = None
    title: Optional[str] = None


@router.post("/vfs/list")
async def vfs_list(
    agent_id: str,
    body: VfsListBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List documents under a virtual path for this agent."""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
        ))
        .order_by(Document.title)
    )
    rows = (await session.execute(stmt)).all()
    items = []
    for ad, doc in rows:
        slug = doc.slug or doc.id
        doc_path = f"/{slug}"
        if body.path != "/" and not doc_path.startswith(body.path):
            continue
        items.append({
            "path": doc_path,
            "name": doc.title or doc.filename or slug,
            "type": "file",
            "size": doc.total_char_count,
            "file_type": doc.file_type,
            "link_id": ad.id,
            "document_id": doc.id,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        })
    return items


@router.post("/vfs/stat")
async def vfs_stat(
    agent_id: str,
    body: VfsStatBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get file stat for a virtual path."""
    slug = body.path.strip("/")
    doc = (await session.execute(
        select(Document, AgentDocument)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
            Document.slug == slug,
        ))
    )).one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    d, ad = doc
    return {
        "path": body.path,
        "name": d.title or d.filename or slug,
        "type": "file",
        "size": d.total_char_count,
        "file_type": d.file_type,
        "link_id": ad.id,
        "document_id": d.id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


@router.post("/vfs/read")
async def vfs_read(
    agent_id: str,
    body: VfsReadBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Read file content by virtual path."""
    slug = body.path.strip("/")
    doc = (await session.execute(
        select(Document)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
            Document.slug == slug,
        ))
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return {"path": body.path, "content": doc.content, "title": doc.title}


@router.post("/vfs/write")
async def vfs_write(
    agent_id: str,
    body: VfsWriteBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Write content to a virtual path (create or update)."""
    slug = body.path.strip("/")
    doc = (await session.execute(
        select(Document)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
            Document.slug == slug,
        ))
    )).scalar_one_or_none()

    if doc:
        await session.execute(
            update(Document)
            .where(Document.id == doc.id)
            .values(
                content=body.content,
                total_char_count=len(body.content),
                total_line_count=body.content.count("\n") + 1,
                updated_at=_now(),
            )
        )
        return {"document_id": doc.id, "created": False}
    elif body.create_if_missing:
        new_doc = Document(
            user_id=user_id,
            title=slug,
            content=body.content,
            file_type="markdown",
            source="agent",
            source_type="api",
            slug=slug,
            total_char_count=len(body.content),
            total_line_count=body.content.count("\n") + 1,
        )
        session.add(new_doc)
        await session.flush()
        link = AgentDocument(
            agent_id=agent_id,
            document_id=new_doc.id,
            user_id=user_id,
            policy_load="eager",
        )
        session.add(link)
        await session.flush()
        return {"document_id": new_doc.id, "created": True}
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


@router.post("/vfs/mkdir")
async def vfs_mkdir(
    agent_id: str,
    body: VfsMkdirBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a virtual directory (a document with type 'folder')."""
    slug = body.path.strip("/")
    doc = Document(
        user_id=user_id,
        title=slug.split("/")[-1],
        file_type="folder",
        source="agent",
        source_type="api",
        slug=slug,
        total_char_count=0,
        total_line_count=0,
    )
    session.add(doc)
    await session.flush()
    link = AgentDocument(
        agent_id=agent_id,
        document_id=doc.id,
        user_id=user_id,
        policy_load="disabled",
    )
    session.add(link)
    await session.flush()
    return {"document_id": doc.id, "path": body.path}


@router.post("/vfs/rename")
async def vfs_rename(
    agent_id: str,
    body: VfsRenameBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Rename a virtual path (update slug)."""
    old_slug = body.from_path.strip("/")
    new_slug = body.to_path.strip("/")
    doc = (await session.execute(
        select(Document)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            Document.slug == old_slug,
        ))
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await session.execute(
        update(Document).where(Document.id == doc.id).values(
            slug=new_slug,
            title=new_slug.split("/")[-1],
            updated_at=_now(),
        )
    )
    return {"ok": True}


@router.post("/vfs/copy")
async def vfs_copy(
    agent_id: str,
    body: VfsCopyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Copy a virtual file to a new path."""
    src_slug = body.from_path.strip("/")
    dst_slug = body.to_path.strip("/")
    src_doc = (await session.execute(
        select(Document)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            Document.slug == src_slug,
        ))
    )).scalar_one_or_none()
    if not src_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")

    new_doc = Document(
        user_id=user_id,
        title=dst_slug.split("/")[-1],
        content=src_doc.content,
        file_type=src_doc.file_type,
        source="agent",
        source_type="api",
        slug=dst_slug,
        total_char_count=src_doc.total_char_count,
        total_line_count=src_doc.total_line_count,
    )
    session.add(new_doc)
    await session.flush()
    link = AgentDocument(
        agent_id=agent_id,
        document_id=new_doc.id,
        user_id=user_id,
        policy_load="eager",
    )
    session.add(link)
    await session.flush()
    return {"document_id": new_doc.id}


@router.post("/vfs/delete")
async def vfs_delete(
    agent_id: str,
    body: VfsDeleteBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete (soft or hard) virtual files by path."""
    for path in body.paths:
        slug = path.strip("/")
        stmt = (
            select(AgentDocument)
            .join(Document, Document.id == AgentDocument.document_id)
            .where(and_(
                AgentDocument.agent_id == agent_id,
                AgentDocument.user_id == user_id,
                Document.slug == slug,
            ))
        )
        ad = (await session.execute(stmt)).scalar_one_or_none()
        if ad:
            if body.permanent:
                await session.execute(
                    delete(AgentDocument).where(AgentDocument.id == ad.id)
                )
            else:
                await session.execute(
                    update(AgentDocument).where(AgentDocument.id == ad.id).values(deleted_at=_now())
                )
    return {"ok": True}


@router.post("/vfs/trash")
async def vfs_list_trash(
    agent_id: str,
    body: VfsTrashListBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List soft-deleted documents (trash)."""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.isnot(None),
        ))
        .order_by(desc(AgentDocument.deleted_at))
        .limit(body.limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "link_id": ad.id,
            "document_id": doc.id,
            "path": f"/{doc.slug or doc.id}",
            "name": doc.title or doc.filename,
            "deleted_at": ad.deleted_at.isoformat() if ad.deleted_at else None,
        }
        for ad, doc in rows
    ]


@router.post("/vfs/restore")
async def vfs_restore(
    agent_id: str,
    body: VfsRestoreBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Restore soft-deleted documents from trash."""
    for link_id in body.link_ids:
        await session.execute(
            update(AgentDocument)
            .where(and_(
                AgentDocument.id == link_id,
                AgentDocument.agent_id == agent_id,
                AgentDocument.user_id == user_id,
            ))
            .values(deleted_at=None)
        )
    return {"ok": True}


@router.post("/vfs/empty-trash")
async def vfs_empty_trash(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Permanently delete all items in trash."""
    await session.execute(
        delete(AgentDocument).where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.isnot(None),
        ))
    )
    return {"ok": True}


# ── Skill-by-path endpoints ─────────────────────────────────────────

@router.post("/skill-by-path")
async def create_or_update_skill_by_path(
    agent_id: str,
    body: SkillByPathBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create/update a document used as a skill, referenced by path."""
    slug = body.path.strip("/")
    doc = (await session.execute(
        select(Document)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
            Document.slug == slug,
        ))
    )).scalar_one_or_none()

    if doc:
        values: dict[str, Any] = {"updated_at": _now()}
        if body.content is not None:
            values["content"] = body.content
            values["total_char_count"] = len(body.content)
        if body.title is not None:
            values["title"] = body.title
        await session.execute(update(Document).where(Document.id == doc.id).values(**values))
        return {"document_id": doc.id, "created": False}
    else:
        new_doc = Document(
            user_id=user_id,
            title=body.title or slug,
            content=body.content or "",
            file_type="markdown",
            source="agent",
            source_type="api",
            slug=slug,
            total_char_count=len(body.content or ""),
            total_line_count=(body.content or "").count("\n") + 1,
        )
        session.add(new_doc)
        await session.flush()
        link = AgentDocument(
            agent_id=agent_id,
            document_id=new_doc.id,
            user_id=user_id,
            policy_load="eager",
        )
        session.add(link)
        await session.flush()
        return {"document_id": new_doc.id, "created": True}


@router.delete("/skill-by-path")
async def delete_skill_by_path(
    agent_id: str,
    path: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete a skill document by virtual path."""
    slug = path.strip("/")
    ad = (await session.execute(
        select(AgentDocument)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            Document.slug == slug,
        ))
    )).scalar_one_or_none()
    if ad:
        await session.execute(delete(AgentDocument).where(AgentDocument.id == ad.id))
    return {"ok": True}


# ── Document by ID endpoints ────────────────────────────────────────

@router.post("/by-id/associate")
async def associate_document_by_id(
    agent_id: str,
    body: DocByIdBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Associate an existing document to the agent by document ID."""
    link = AgentDocument(
        agent_id=agent_id,
        document_id=body.document_id,
        user_id=user_id,
        policy_load="lazy",
    )
    session.add(link)
    await session.flush()
    return {"link_id": link.id}


@router.post("/by-id/create")
async def create_document_for_agent(
    agent_id: str,
    body: DocCreateBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create a new document and associate it with the agent."""
    doc = Document(
        user_id=user_id,
        title=body.title,
        content=body.content,
        file_type=body.file_type,
        source="agent",
        source_type="api",
        slug=body.path.strip("/") if body.path else None,
        total_char_count=len(body.content),
        total_line_count=body.content.count("\n") + 1,
    )
    session.add(doc)
    await session.flush()
    link = AgentDocument(
        agent_id=agent_id,
        document_id=doc.id,
        user_id=user_id,
        policy_load="eager",
    )
    session.add(link)
    await session.flush()
    return {"document_id": doc.id, "link_id": link.id}


@router.put("/by-id/{document_id}")
async def modify_agent_document_by_id(
    agent_id: str,
    document_id: str,
    body: DocModifyBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Modify a document by its ID (if linked to this agent)."""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.document_id == document_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not linked to agent")
    values: dict[str, Any] = {"updated_at": _now()}
    if body.content is not None:
        values["content"] = body.content
        values["total_char_count"] = len(body.content)
        values["total_line_count"] = body.content.count("\n") + 1
    if body.title is not None:
        values["title"] = body.title
    await session.execute(update(Document).where(Document.id == document_id).values(**values))
    return {"ok": True}


@router.delete("/by-id/{document_id}")
async def remove_agent_document_by_id(
    agent_id: str,
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Remove a document from agent by document ID."""
    await session.execute(
        delete(AgentDocument).where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.document_id == document_id,
            AgentDocument.user_id == user_id,
        ))
    )
    return {"ok": True}


# ── Missing TS parity endpoints ────────────────────────────────────


class UpsertDocumentBody(BaseModel):
    filename: str
    content: str
    metadata: Optional[dict[str, Any]] = None


class CloneDocumentsBody(BaseModel):
    source_agent_id: str
    target_agent_id: str


class CreateForTopicBody(BaseModel):
    title: str
    content: str
    topic_id: str


class ModifyNodesBody(BaseModel):
    operations: list[dict[str, Any]]


class ReplaceContentBody(BaseModel):
    content: str


class UpdateLoadRuleBody(BaseModel):
    rule: dict[str, Any]


class ListDocumentsParams(BaseModel):
    target: str = "agent"  # 'agent' | 'currentTopic'
    topic_id: Optional[str] = None


@router.get("/templates")
async def get_templates(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get available document templates (static list)."""
    return [
        {
            "id": "default",
            "name": "Default",
            "description": "Basic SOUL.md + plan template",
            "filenames": ["SOUL.md", "plan.md"],
        },
        {
            "id": "coding",
            "name": "Coding Assistant",
            "description": "Templates for coding agents",
            "filenames": ["SOUL.md", "plan.md", "guidelines.md"],
        },
    ]


@router.put("/upsert")
async def upsert_document(
    agent_id: str,
    body: UpsertDocumentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create or update a document by filename (slug)."""
    doc = (await session.execute(
        select(Document)
        .join(AgentDocument, AgentDocument.document_id == Document.id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
            Document.slug == body.filename,
        ))
    )).scalar_one_or_none()

    if doc:
        values: dict[str, Any] = {
            "content": body.content,
            "total_char_count": len(body.content),
            "total_line_count": body.content.count("\n") + 1,
            "updated_at": _now(),
        }
        if body.metadata is not None:
            values["metadata_"] = body.metadata
        await session.execute(update(Document).where(Document.id == doc.id).values(**values))
        return {"id": doc.id, "created": False}
    else:
        new_doc = Document(
            user_id=user_id,
            title=body.filename,
            content=body.content,
            file_type="markdown",
            source="agent",
            source_type="api",
            slug=body.filename,
            total_char_count=len(body.content),
            total_line_count=body.content.count("\n") + 1,
        )
        if body.metadata:
            new_doc.metadata_ = body.metadata
        session.add(new_doc)
        await session.flush()
        link = AgentDocument(
            agent_id=agent_id,
            document_id=new_doc.id,
            user_id=user_id,
            policy_load="always",
        )
        session.add(link)
        await session.flush()
        return {"id": new_doc.id, "created": True}


@router.delete("/all")
async def delete_all_documents(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Delete all documents for an agent (soft-delete links)."""
    await session.execute(
        update(AgentDocument)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
        ))
        .values(deleted_at=_now())
    )
    return {"ok": True}


@router.post("/clone")
async def clone_documents(
    agent_id: str,
    body: CloneDocumentsBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Clone all documents from source agent to target agent."""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.agent_id == body.source_agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
        ))
    )
    rows = (await session.execute(stmt)).all()
    created = 0
    for ad, doc in rows:
        new_doc = Document(
            user_id=user_id,
            title=doc.title,
            content=doc.content,
            file_type=doc.file_type,
            source="agent",
            source_type="api",
            slug=doc.slug,
            total_char_count=doc.total_char_count,
            total_line_count=doc.total_line_count,
            editor_data=doc.editor_data,
        )
        session.add(new_doc)
        await session.flush()
        link = AgentDocument(
            agent_id=body.target_agent_id,
            document_id=new_doc.id,
            user_id=user_id,
            policy_load=ad.policy_load,
            policy=ad.policy,
            policy_load_position=ad.policy_load_position,
            policy_load_format=ad.policy_load_format,
            policy_load_rule=ad.policy_load_rule,
            template_id=ad.template_id,
        )
        session.add(link)
        created += 1
    await session.flush()
    return {"cloned": created}


@router.get("/has-documents")
async def has_documents(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Check if agent has any documents."""
    count = (await session.execute(
        select(func.count()).select_from(AgentDocument).where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
        ))
    )).scalar_one()
    return count > 0


@router.get("/context")
async def get_context(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get agent document context for LLM injection (documents with policy_load='always')."""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
            AgentDocument.policy_load == "always",
        ))
        .order_by(AgentDocument.created_at)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": doc.id,
            "filename": doc.slug or doc.title,
            "content": doc.content or "",
            "metadata": doc.metadata_,
            "policy_load_position": ad.policy_load_position,
            "policy_load_format": ad.policy_load_format,
        }
        for ad, doc in rows
    ]


@router.get("/map")
async def get_documents_map(
    agent_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get a map of all documents keyed by filename/slug."""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
        ))
    )
    rows = (await session.execute(stmt)).all()
    result: dict[str, Any] = {}
    for ad, doc in rows:
        key = doc.slug or doc.title or doc.id
        result[key] = {
            "id": doc.id,
            "content": doc.content,
            "metadata": doc.metadata_,
            "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
        }
    return result


@router.post("/initialize-from-template")
async def initialize_from_template(
    agent_id: str,
    template_set: str = "default",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Initialize agent documents from a template set."""
    templates_map: dict[str, list[dict[str, str]]] = {
        "default": [
            {"filename": "SOUL.md", "content": "# SOUL\n\nDescribe who you are."},
            {"filename": "plan.md", "content": "# Plan\n\nOutline your current plan."},
        ],
        "coding": [
            {"filename": "SOUL.md", "content": "# SOUL\n\nYou are a coding assistant."},
            {"filename": "plan.md", "content": "# Plan\n\nOutline tasks."},
            {"filename": "guidelines.md", "content": "# Guidelines\n\nCode style rules."},
        ],
    }
    templates = templates_map.get(template_set, templates_map["default"])
    created = 0
    for tmpl in templates:
        doc = Document(
            user_id=user_id,
            title=tmpl["filename"],
            content=tmpl["content"],
            file_type="markdown",
            source="agent",
            source_type="api",
            slug=tmpl["filename"],
            total_char_count=len(tmpl["content"]),
            total_line_count=tmpl["content"].count("\n") + 1,
        )
        session.add(doc)
        await session.flush()
        link = AgentDocument(
            agent_id=agent_id,
            document_id=doc.id,
            user_id=user_id,
            policy_load="always",
            template_id=template_set,
        )
        session.add(link)
        created += 1
    await session.flush()
    return {"created": created, "template_set": template_set}


@router.post("/create-for-topic")
async def create_for_topic(
    agent_id: str,
    body: CreateForTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Create an agent document and associate it with a topic."""
    title = body.title.strip()
    if not title:
        topic = (await session.execute(
            select(Topic).where(and_(Topic.id == body.topic_id, Topic.user_id == user_id))
        )).scalar_one_or_none()
        title = topic.title if topic and topic.title else ""

    doc = Document(
        user_id=user_id,
        title=title,
        content=body.content,
        file_type="markdown",
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
        policy_load="always",
    )
    session.add(link)
    await session.flush()

    topic_doc = TopicDocument(
        topic_id=body.topic_id,
        document_id=doc.id,
        user_id=user_id,
    )
    session.add(topic_doc)
    await session.flush()

    return {"id": doc.id, "link_id": link.id}


@router.put("/by-id/{document_id}/nodes")
async def modify_nodes(
    agent_id: str,
    document_id: str,
    body: ModifyNodesBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Modify document editor nodes through LiteXML operations."""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.document_id == document_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not linked to agent")

    doc = (await session.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    editor_data = doc.editor_data or {}
    editor_data["_last_operations"] = body.operations
    await session.execute(
        update(Document).where(Document.id == document_id).values(
            editor_data=editor_data,
            updated_at=_now(),
        )
    )
    return {"ok": True, "operations_count": len(body.operations)}


@router.put("/by-id/{document_id}/replace-content")
async def replace_document_content(
    agent_id: str,
    document_id: str,
    body: ReplaceContentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Full content replacement for a document."""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.document_id == document_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not linked to agent")

    await session.execute(
        update(Document).where(Document.id == document_id).values(
            content=body.content,
            total_char_count=len(body.content),
            total_line_count=body.content.count("\n") + 1,
            updated_at=_now(),
        )
    )
    return {"ok": True}


@router.put("/by-id/{document_id}/load-rule")
async def update_load_rule(
    agent_id: str,
    document_id: str,
    body: UpdateLoadRuleBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Update document load rule for context injection."""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.document_id == document_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not linked to agent")

    values: dict[str, Any] = {"updated_at": _now()}
    rule = body.rule
    if "rule" in rule:
        values["policy_load_rule"] = rule["rule"]
    if "policyLoadFormat" in rule:
        values["policy_load_format"] = rule["policyLoadFormat"]
    if "priority" in rule:
        values["policy_load_position"] = str(rule["priority"])
    values["policy"] = rule

    await session.execute(
        update(AgentDocument).where(AgentDocument.id == ad.id).values(**values)
    )
    return {"ok": True}


@router.post("/list-filtered")
async def list_documents_filtered(
    agent_id: str,
    body: ListDocumentsParams,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List documents with optional topic filtering."""
    if body.target == "currentTopic":
        if not body.topic_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "topic_id is required for currentTopic target")
        stmt = (
            select(Document)
            .join(TopicDocument, TopicDocument.document_id == Document.id)
            .join(AgentDocument, AgentDocument.document_id == Document.id)
            .where(and_(
                TopicDocument.topic_id == body.topic_id,
                AgentDocument.agent_id == agent_id,
                AgentDocument.user_id == user_id,
                AgentDocument.deleted_at.is_(None),
            ))
        )
    else:
        stmt = (
            select(Document)
            .join(AgentDocument, AgentDocument.document_id == Document.id)
            .where(and_(
                AgentDocument.agent_id == agent_id,
                AgentDocument.user_id == user_id,
                AgentDocument.deleted_at.is_(None),
            ))
        )

    docs = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.slug or d.title,
            "content": d.content,
            "fileType": d.file_type,
            "totalCharCount": d.total_char_count,
            "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in docs
    ]
