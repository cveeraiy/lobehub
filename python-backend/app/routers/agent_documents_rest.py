"""Agent Documents REST adapter — flat /api/agent-documents paths for frontend.

Maps the frontend REST client paths (agentDocument.rest.ts) to the underlying
agent_documents router logic. The existing router uses /api/agents/{agent_id}/documents
but the frontend expects /api/agent-documents with agent_id as a query/body param.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from pydantic import Field as PField
from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models.agent_ops import AgentDocument
from app.models.file import Document
from app.models.topic import Topic
from app.models.topic_ext import TopicDocument

router = APIRouter(prefix="/api/agent-documents", tags=["Agent Documents REST"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────


class CreateDocBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    title: str
    content: str


class CreateForTopicBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    title: str
    content: str
    topic_id: str = PField(alias="topicId")


class AssociateBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    document_id: str = PField(alias="documentId")


class InitTemplateBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    template_set: str = PField(default="default", alias="templateSet")


class ReplaceContentBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    content: str


class ModifyNodesBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    operations: list[dict[str, Any]]


class CopyDocBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    new_title: Optional[str] = PField(default=None, alias="newTitle")


class RenameDocBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    new_title: str = PField(alias="newTitle")


class UpdateLoadRuleBody(BaseModel):
    model_config = {"populate_by_name": True}
    agent_id: str = PField(alias="agentId")
    rule: dict[str, Any]


# ── Helpers ──────────────────────────────────────────────────────────


def _serialize_doc(ad: AgentDocument, doc: Document) -> dict[str, Any]:
    return {
        "id": ad.id,
        "documentId": doc.id,
        "agentId": ad.agent_id,
        "filename": doc.slug or doc.title,
        "title": doc.title,
        "content": doc.content or "",
        "description": getattr(doc, "description", None),
        "fileType": doc.file_type,
        "totalCharCount": doc.total_char_count,
        "policyLoad": ad.policy_load,
        "policyLoadPosition": ad.policy_load_position,
        "policyLoadFormat": ad.policy_load_format,
        "templateId": ad.template_id,
        "policy": ad.policy,
        "loadRules": ad.policy_load_rule,
        "createdAt": ad.created_at.isoformat() if ad.created_at else None,
        "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# ── Templates ────────────────────────────────────────────────────────


TEMPLATES = {
    "default": {
        "name": "Default",
        "description": "Basic SOUL.md + plan template",
        "templates": [
            {"filename": "SOUL.md", "content": "# SOUL\n\nDescribe who you are."},
            {"filename": "plan.md", "content": "# Plan\n\nOutline your current plan."},
        ],
    },
    "coding": {
        "name": "Coding Assistant",
        "description": "Templates for coding agents",
        "templates": [
            {"filename": "SOUL.md", "content": "# SOUL\n\nYou are a coding assistant."},
            {"filename": "plan.md", "content": "# Plan\n\nOutline tasks."},
            {"filename": "guidelines.md", "content": "# Guidelines\n\nCode style rules."},
        ],
    },
}


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/templates")
async def get_templates(
    user_id: str = Depends(get_current_user_id),
):
    """GET /api/agent-documents/templates"""
    return [
        {
            "id": tid,
            "name": t["name"],
            "description": t["description"],
            "filenames": [f["filename"] for f in t["templates"]],
        }
        for tid, t in TEMPLATES.items()
    ]


@router.get("/list")
async def list_documents(
    agent_id: str = Query(alias="agentId", default=None),
    target: str = Query(default="agent"),
    topic_id: Optional[str] = Query(alias="topicId", default=None),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/agent-documents/list?agentId=...&target=...&topicId=..."""
    if not agent_id:
        raise HTTPException(400, "agentId is required")

    if target == "currentTopic":
        if not topic_id:
            raise HTTPException(400, "topicId is required for currentTopic target")
        stmt = (
            select(Document)
            .join(TopicDocument, TopicDocument.document_id == Document.id)
            .join(AgentDocument, AgentDocument.document_id == Document.id)
            .where(and_(
                TopicDocument.topic_id == topic_id,
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


@router.get("")
async def get_documents(
    agent_id: str = Query(alias="agent_id", default=None),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/agent-documents?agent_id=..."""
    if not agent_id:
        raise HTTPException(400, "agent_id is required")

    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
            AgentDocument.deleted_at.is_(None),
        ))
        .order_by(desc(AgentDocument.created_at))
    )
    rows = (await session.execute(stmt)).all()
    return [_serialize_doc(ad, doc) for ad, doc in rows]


@router.post("/initialize-template")
async def initialize_from_template(
    body: InitTemplateBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/agent-documents/initialize-template"""
    ts = TEMPLATES.get(body.template_set, TEMPLATES["default"])
    created = 0
    for tmpl in ts["templates"]:
        doc = Document(
            user_id=user_id,
            title=tmpl["filename"],
            content=tmpl["content"],
            file_type="markdown",
            source="agent",
            source_type="api",
            total_char_count=len(tmpl["content"]),
            total_line_count=tmpl["content"].count("\n") + 1,
        )
        session.add(doc)
        await session.flush()
        link = AgentDocument(
            agent_id=body.agent_id,
            document_id=doc.id,
            user_id=user_id,
            policy_load="always",
            template_id=body.template_set,
        )
        session.add(link)
        created += 1
    await session.flush()
    return {"created": created, "templateSet": body.template_set}


@router.post("/associate")
async def associate_document(
    body: AssociateBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/agent-documents/associate"""
    link = AgentDocument(
        agent_id=body.agent_id,
        document_id=body.document_id,
        user_id=user_id,
        policy_load="lazy",
    )
    session.add(link)
    await session.flush()
    return {"id": link.id, "documentId": body.document_id}


@router.post("")
async def create_document(
    body: CreateDocBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/agent-documents"""
    doc = Document(
        user_id=user_id,
        title=body.title,
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
        agent_id=body.agent_id,
        document_id=doc.id,
        user_id=user_id,
        policy_load="always",
    )
    session.add(link)
    await session.flush()
    return {"id": link.id, "documentId": doc.id}


@router.post("/for-topic")
async def create_for_topic(
    body: CreateForTopicBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/agent-documents/for-topic"""
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
        agent_id=body.agent_id,
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

    return {"id": link.id, "documentId": doc.id}


@router.get("/{doc_id}/read")
async def read_document(
    doc_id: str,
    agent_id: str = Query(alias="agent_id"),
    format: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/agent-documents/{id}/read?agent_id=...&format=..."""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.document_id == doc_id,
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
        ))
    )
    row = (await session.execute(stmt)).one_or_none()
    if not row:
        raise HTTPException(404, "Document not found")
    ad, doc = row
    result = _serialize_doc(ad, doc)
    if format:
        result["editorData"] = doc.editor_data
    return result


@router.put("/{doc_id}/content")
async def replace_content(
    doc_id: str,
    body: ReplaceContentBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """PUT /api/agent-documents/{id}/content"""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.document_id == doc_id,
            AgentDocument.agent_id == body.agent_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(404, "Document not linked to agent")

    await session.execute(
        update(Document).where(Document.id == doc_id).values(
            content=body.content,
            total_char_count=len(body.content),
            total_line_count=body.content.count("\n") + 1,
            updated_at=_now(),
        )
    )
    return {"ok": True, "documentId": doc_id}


@router.post("/{doc_id}/modify-nodes")
async def modify_nodes(
    doc_id: str,
    body: ModifyNodesBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/agent-documents/{id}/modify-nodes"""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.document_id == doc_id,
            AgentDocument.agent_id == body.agent_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(404, "Document not linked to agent")

    doc = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    editor_data = doc.editor_data or {}
    editor_data["_last_operations"] = body.operations
    await session.execute(
        update(Document).where(Document.id == doc_id).values(
            editor_data=editor_data,
            updated_at=_now(),
        )
    )
    return {"ok": True, "documentId": doc_id}


@router.delete("/{doc_id}")
async def remove_document(
    doc_id: str,
    agent_id: str = Query(alias="agent_id"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """DELETE /api/agent-documents/{id}?agent_id=..."""
    result = await session.execute(
        delete(AgentDocument).where(and_(
            AgentDocument.document_id == doc_id,
            AgentDocument.agent_id == agent_id,
            AgentDocument.user_id == user_id,
        ))
    )
    deleted = result.rowcount > 0
    return {"deleted": deleted, "id": doc_id}


@router.post("/{doc_id}/copy")
async def copy_document(
    doc_id: str,
    body: CopyDocBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/agent-documents/{id}/copy"""
    stmt = (
        select(AgentDocument, Document)
        .join(Document, Document.id == AgentDocument.document_id)
        .where(and_(
            AgentDocument.document_id == doc_id,
            AgentDocument.agent_id == body.agent_id,
            AgentDocument.user_id == user_id,
        ))
    )
    row = (await session.execute(stmt)).one_or_none()
    if not row:
        raise HTTPException(404, "Document not found")
    ad, src_doc = row

    new_doc = Document(
        user_id=user_id,
        title=body.new_title or f"{src_doc.title} (copy)",
        content=src_doc.content,
        file_type=src_doc.file_type,
        source="agent",
        source_type="api",
        total_char_count=src_doc.total_char_count,
        total_line_count=src_doc.total_line_count,
    )
    session.add(new_doc)
    await session.flush()

    new_link = AgentDocument(
        agent_id=body.agent_id,
        document_id=new_doc.id,
        user_id=user_id,
        policy_load=ad.policy_load,
    )
    session.add(new_link)
    await session.flush()
    return {"id": new_link.id, "documentId": new_doc.id}


@router.put("/{doc_id}/rename")
async def rename_document(
    doc_id: str,
    body: RenameDocBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """PUT /api/agent-documents/{id}/rename"""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.document_id == doc_id,
            AgentDocument.agent_id == body.agent_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(404, "Document not linked to agent")

    await session.execute(
        update(Document).where(Document.id == doc_id).values(
            title=body.new_title,
            updated_at=_now(),
        )
    )
    return {"ok": True, "documentId": doc_id}


@router.put("/{doc_id}/load-rule")
async def update_load_rule(
    doc_id: str,
    body: UpdateLoadRuleBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """PUT /api/agent-documents/{id}/load-rule"""
    ad = (await session.execute(
        select(AgentDocument).where(and_(
            AgentDocument.document_id == doc_id,
            AgentDocument.agent_id == body.agent_id,
            AgentDocument.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(404, "Document not linked to agent")

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
