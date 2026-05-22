"""Agent Documents server runtime tool — CRUD for agent-scoped documents.

Ports TS ``serverRuntimes/agentDocuments.ts``:
- createDocument, readDocument, removeDocument, renameDocument
- replaceDocumentContent, listDocuments
- createTopicDocument, listTopicDocuments
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

AGENT_DOCUMENTS_IDENTIFIER = "lobehub_agent_documents"


async def agent_documents_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    **kwargs: Any,
) -> str:
    """Agent documents tool — manage agent-scoped documents."""
    from sqlalchemy import delete as sa_del
    from sqlalchemy import select
    from sqlalchemy import update as sa_update

    from app.models.agent_ops import AgentDocument
    from app.models.file import Document
    from app.models.topic_ext import TopicDocument

    agent_id = arguments.get("agentId") or kwargs.get("agent_id")

    if api_name == "createDocument":
        title = arguments.get("title", "Untitled")
        content = arguments.get("content", "")

        if not agent_id:
            return json.dumps({"success": False, "content": "agentId is required"})

        doc = Document(
            user_id=user_id,
            title=title,
            content=content,
            file_type="agent/document",
            source=f"agent:{agent_id}",
            source_type="api",
            total_char_count=len(content),
            total_line_count=content.count("\n") + 1,
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        # Link to agent
        agent_doc = AgentDocument(
            agent_id=agent_id,
            document_id=doc.id,
            user_id=user_id,
        )
        session.add(agent_doc)
        await session.flush()

        return json.dumps({
            "success": True,
            "documentId": doc.id,
            "content": f"Document created: {title} [{doc.id}]",
        })

    elif api_name == "readDocument":
        doc_id = arguments.get("id")
        if not doc_id:
            return json.dumps({"success": False, "content": "id is required"})

        stmt = select(Document).where(Document.id == doc_id, Document.user_id == user_id)
        doc = (await session.execute(stmt)).scalar_one_or_none()
        if not doc:
            return json.dumps({"success": False, "content": f"Document not found: {doc_id}"})

        return json.dumps({
            "success": True,
            "documentId": doc.id,
            "title": doc.title,
            "content": doc.content,
        })

    elif api_name == "removeDocument":
        doc_id = arguments.get("id")
        if not doc_id:
            return json.dumps({"success": False, "content": "id is required"})

        # Remove agent-document link and document
        await session.execute(
            sa_del(AgentDocument).where(
                AgentDocument.document_id == doc_id,
                AgentDocument.user_id == user_id,
            )
        )
        await session.execute(
            sa_del(Document).where(Document.id == doc_id, Document.user_id == user_id)
        )
        await session.flush()

        return json.dumps({"success": True, "content": f"Document {doc_id} removed."})

    elif api_name == "renameDocument":
        doc_id = arguments.get("id")
        new_title = arguments.get("newTitle")
        if not doc_id or not new_title:
            return json.dumps({"success": False, "content": "id and newTitle are required"})

        await session.execute(
            sa_update(Document)
            .where(Document.id == doc_id, Document.user_id == user_id)
            .values(title=new_title)
        )
        await session.flush()
        return json.dumps({"success": True, "content": f"Document {doc_id} renamed to '{new_title}'."})

    elif api_name == "replaceDocumentContent":
        doc_id = arguments.get("id")
        content = arguments.get("content", "")
        if not doc_id:
            return json.dumps({"success": False, "content": "id is required"})

        await session.execute(
            sa_update(Document)
            .where(Document.id == doc_id, Document.user_id == user_id)
            .values(
                content=content,
                total_char_count=len(content),
                total_line_count=content.count("\n") + 1,
            )
        )
        await session.flush()
        return json.dumps({"success": True, "content": f"Document {doc_id} content replaced."})

    elif api_name == "listDocuments":
        if not agent_id:
            return json.dumps({"success": False, "content": "agentId is required"})

        stmt = (
            select(Document)
            .join(AgentDocument, AgentDocument.document_id == Document.id)
            .where(AgentDocument.agent_id == agent_id, AgentDocument.user_id == user_id)
            .order_by(Document.created_at.desc())
        )
        docs = (await session.execute(stmt)).scalars().all()

        items = [{"id": d.id, "title": d.title} for d in docs]
        return json.dumps({"success": True, "documents": items, "content": f"Found {len(items)} document(s)."})

    elif api_name == "createTopicDocument":
        title = arguments.get("title", "Untitled")
        content = arguments.get("content", "")
        topic_id = arguments.get("topicId")

        if not agent_id or not topic_id:
            return json.dumps({"success": False, "content": "agentId and topicId are required"})

        doc = Document(
            user_id=user_id,
            title=title,
            content=content,
            file_type="agent/document",
            source=f"agent:{agent_id}:topic:{topic_id}",
            source_type="api",
            total_char_count=len(content),
            total_line_count=content.count("\n") + 1,
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        # Link to agent and topic
        session.add(AgentDocument(agent_id=agent_id, document_id=doc.id, user_id=user_id))
        session.add(TopicDocument(topic_id=topic_id, document_id=doc.id, user_id=user_id))
        await session.flush()

        return json.dumps({
            "success": True,
            "documentId": doc.id,
            "content": f"Topic document created: {title} [{doc.id}]",
        })

    elif api_name == "listTopicDocuments":
        topic_id = arguments.get("topicId")
        if not agent_id or not topic_id:
            return json.dumps({"success": False, "content": "agentId and topicId are required"})

        stmt = (
            select(Document)
            .join(TopicDocument, TopicDocument.document_id == Document.id)
            .join(AgentDocument, AgentDocument.document_id == Document.id)
            .where(
                TopicDocument.topic_id == topic_id,
                AgentDocument.agent_id == agent_id,
                AgentDocument.user_id == user_id,
            )
            .order_by(Document.created_at.desc())
        )
        docs = (await session.execute(stmt)).scalars().all()

        items = [{"id": d.id, "title": d.title} for d in docs]
        return json.dumps({"success": True, "documents": items, "content": f"Found {len(items)} topic document(s)."})

    return json.dumps({"error": f"Unknown agentDocuments API: {api_name}"})


@register(
    AGENT_DOCUMENTS_IDENTIFIER,
    description="Agent Documents — manage agent-scoped documents. "
                "APIs: createDocument, readDocument, removeDocument, renameDocument, "
                "replaceDocumentContent, listDocuments, createTopicDocument, listTopicDocuments.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "enum": [
                    "createDocument", "readDocument", "removeDocument", "renameDocument",
                    "replaceDocumentContent", "listDocuments", "createTopicDocument", "listTopicDocuments",
                ],
            },
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def agent_documents_tool_context_required(args: dict[str, Any]) -> str:
    return json.dumps({"error": "Agent Documents tool requires server context (session + user_id)."})


register_context_handler(AGENT_DOCUMENTS_IDENTIFIER, agent_documents_with_context)
