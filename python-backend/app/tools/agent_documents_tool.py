"""Agent Documents runtime tool.

Ports the server-side behavior of ``lobe-agent-documents``. The tool id passed
to the model is the ``agent_documents.id`` association row; ``documentId`` in
state points to the backing ``documents.id`` row used by the editor/portal.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, desc, select, update

from app.tools.registry import register, register_context_handler

AGENT_DOCUMENTS_IDENTIFIER = "lobe-agent-documents"
LEGACY_AGENT_DOCUMENTS_IDENTIFIER = "lobehub_agent_documents"
AGENT_DOCUMENTS_APIS = [
    "copyDocument",
    "createDocument",
    "listDocuments",
    "modifyNodes",
    "readDocument",
    "removeDocument",
    "renameDocument",
    "replaceDocumentContent",
    "updateLoadRule",
]


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _success(content: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"content": content, "success": True}
    if state is not None:
        result["state"] = state
    return result


def _failure(content: str, error_type: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"content": content, "success": False}
    if error_type:
        result["error"] = {"message": content, "type": error_type}
    return result


def _slugify_filename(title: str) -> str:
    value = title.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return f"{value or 'untitled'}.md"


def _extract_markdown_h1(title: str, content: str) -> tuple[str, str]:
    lines = content.splitlines()
    if lines and lines[0].startswith("# "):
        extracted = lines[0][2:].strip()
        stripped = "\n".join(lines[1:]).lstrip("\n")
        return extracted or title, stripped
    return title, content


def _record(agent_doc: Any, doc: Any) -> dict[str, Any]:
    filename = doc.filename or doc.slug or doc.title or ""
    return {
        "content": doc.content or "",
        "documentId": doc.id,
        "filename": filename,
        "id": agent_doc.id,
        "litexml": doc.content or "",
        "title": doc.title,
    }


def _list_item(agent_doc: Any, doc: Any) -> dict[str, Any]:
    item = _record(agent_doc, doc)
    return {
        "documentId": item["documentId"],
        "filename": item["filename"] or item["title"] or "",
        "id": item["id"],
        "title": item["title"],
    }


def _format_document_read_content(doc: dict[str, Any], format_: str = "xml") -> str:
    markdown = doc.get("content") or ""
    xml = doc.get("litexml") or ""
    if format_ == "markdown":
        return markdown
    if format_ == "both":
        return _json({"markdown": markdown, "xml": xml})
    return xml or markdown


def _is_current_page_document(doc: dict[str, Any] | None, arguments: dict[str, Any]) -> bool:
    if arguments.get("scope") != "page":
        return False
    current_document_id = arguments.get("currentDocumentId") or arguments.get("current_document_id")
    return bool(current_document_id and doc and doc.get("documentId") == current_document_id)


def _current_page_write_blocked(api_name: str) -> dict[str, Any]:
    message = (
        f"Cannot use lobe-agent-documents.{api_name} on the current page document "
        "while page scope is active. Use lobe-page-agent so the open editor shows a diff node "
        "for review instead of writing directly to the database."
    )
    return {
        "content": message,
        "error": {
            "code": "CURRENT_PAGE_DOCUMENT_WRITE_FORBIDDEN",
            "kind": "replan",
            "message": message,
            "type": "CurrentPageDocumentWriteForbidden",
        },
        "success": False,
    }


async def _find_agent_document(
    session: Any,
    user_id: str,
    agent_id: str,
    agent_document_id: str,
) -> tuple[Any, Any] | None:
    from app.models.agent_ops import AgentDocument
    from app.models.file import Document

    row = (
        await session.execute(
            select(AgentDocument, Document)
            .join(Document, Document.id == AgentDocument.document_id)
            .where(
                and_(
                    AgentDocument.id == agent_document_id,
                    AgentDocument.agent_id == agent_id,
                    AgentDocument.user_id == user_id,
                    AgentDocument.deleted_at.is_(None),
                )
            )
        )
    ).one_or_none()
    if not row:
        return None
    return row


async def _create_document(
    session: Any,
    user_id: str,
    agent_id: str,
    title: str,
    content: str,
    *,
    topic_id: str | None = None,
    source_suffix: str | None = None,
    source_agent_doc: Any | None = None,
) -> tuple[Any, Any]:
    from app.models.agent_ops import AgentDocument
    from app.models.file import Document
    from app.models.topic_ext import TopicDocument

    final_title, final_content = _extract_markdown_h1(title, content)
    filename = _slugify_filename(final_title)
    doc = Document(
        user_id=user_id,
        title=final_title,
        filename=filename,
        content=final_content,
        file_type="agent/document",
        source=f"agent-document://{agent_id}/{filename}{source_suffix or ''}",
        source_type="api",
        total_char_count=len(final_content),
        total_line_count=len(final_content.split("\n")),
        metadata_=getattr(source_agent_doc, "metadata_", None),
        editor_data=getattr(source_agent_doc, "editor_data", None),
    )
    session.add(doc)
    await session.flush()
    await session.refresh(doc)

    agent_doc = AgentDocument(
        agent_id=agent_id,
        document_id=doc.id,
        user_id=user_id,
        policy=getattr(source_agent_doc, "policy", None),
        policy_load=getattr(source_agent_doc, "policy_load", "always"),
        policy_load_format=getattr(source_agent_doc, "policy_load_format", "raw"),
        policy_load_position=getattr(source_agent_doc, "policy_load_position", "before-first-user"),
        policy_load_rule=getattr(source_agent_doc, "policy_load_rule", "always"),
        template_id=getattr(source_agent_doc, "template_id", None),
    )
    session.add(agent_doc)

    if topic_id:
        session.add(TopicDocument(topic_id=topic_id, document_id=doc.id, user_id=user_id))

    await session.flush()
    await session.refresh(agent_doc)
    return agent_doc, doc


async def _pin_task_document(session: Any, user_id: str, task_id: str | None, document_id: str) -> None:
    if not task_id:
        return

    from app.models.task import TaskDocument

    existing = (
        await session.execute(
            select(TaskDocument).where(
                and_(
                    TaskDocument.task_id == task_id,
                    TaskDocument.document_id == document_id,
                    TaskDocument.user_id == user_id,
                )
            )
        )
    ).scalar_one_or_none()
    if existing:
        return
    session.add(TaskDocument(task_id=task_id, document_id=document_id, user_id=user_id, pinned_by="agent"))


async def run_agent_documents_api(
    api_name: str,
    arguments: dict[str, Any],
    *,
    session: Any,
    user_id: str,
) -> dict[str, Any]:
    from app.models.agent_ops import AgentDocument
    from app.models.file import Document
    from app.models.topic_ext import TopicDocument

    agent_id = arguments.get("agentId") or arguments.get("agent_id")
    if not agent_id:
        labels = {
            "copyDocument": "copy agent document",
            "createDocument": "create agent document",
            "listDocuments": "list agent documents",
            "modifyNodes": "modify agent document nodes",
            "readDocument": "read agent document",
            "removeDocument": "remove agent document",
            "renameDocument": "rename agent document",
            "replaceDocumentContent": "replace agent document content",
            "updateLoadRule": "update load rule",
        }
        return _failure(f"Cannot {labels.get(api_name, 'use agent documents')} without agentId context.")

    if api_name == "listDocuments":
        target = arguments.get("target") or "agent"
        topic_id = arguments.get("topicId") or arguments.get("topic_id")
        if target == "currentTopic" and not topic_id:
            return _failure("Cannot list current topic documents without topicId context.")

        stmt = (
            select(AgentDocument, Document)
            .join(Document, Document.id == AgentDocument.document_id)
            .where(
                and_(
                    AgentDocument.agent_id == agent_id,
                    AgentDocument.user_id == user_id,
                    AgentDocument.deleted_at.is_(None),
                )
            )
            .order_by(desc(AgentDocument.created_at))
        )
        if target == "currentTopic":
            stmt = stmt.join(TopicDocument, TopicDocument.document_id == Document.id).where(
                TopicDocument.topic_id == topic_id
            )
        rows = (await session.execute(stmt)).all()
        items = [_list_item(agent_doc, doc) for agent_doc, doc in rows]
        return _success(_json(items), {"documents": items})

    if api_name == "createDocument":
        title = arguments.get("title") or "Untitled"
        content = arguments.get("content") or ""
        target = arguments.get("target") or "agent"
        topic_id = arguments.get("topicId") or arguments.get("topic_id")
        if target == "currentTopic" and not topic_id:
            return _failure("Cannot create current topic document without topicId context.")

        agent_doc, doc = await _create_document(
            session,
            user_id,
            agent_id,
            title,
            content,
            topic_id=topic_id if target == "currentTopic" else None,
        )
        await _pin_task_document(session, user_id, arguments.get("taskId") or arguments.get("task_id"), doc.id)
        record = _record(agent_doc, doc)
        return _success(
            f'Created document "{record.get("title") or title}" ({agent_doc.id}).',
            {"documentId": doc.id},
        )

    doc_id = arguments.get("id")
    if not doc_id:
        return _failure("Document id is required.", "MissingDocumentIdError")

    found = await _find_agent_document(session, user_id, agent_id, doc_id)
    if not found:
        return _failure(f"Document not found: {doc_id}")
    agent_doc, doc = found
    record = _record(agent_doc, doc)

    if api_name == "readDocument":
        format_ = arguments.get("format") or "xml"
        return _success(
            _format_document_read_content(record, format_),
            {
                "content": record["content"],
                "id": agent_doc.id,
                "title": record["title"],
                "xml": record["litexml"],
            },
        )

    if api_name == "replaceDocumentContent":
        if _is_current_page_document(record, arguments):
            return _current_page_write_blocked(api_name)
        content = arguments.get("content") or ""
        await session.execute(
            update(Document)
            .where(and_(Document.id == doc.id, Document.user_id == user_id))
            .values(
                content=content,
                editor_data=None,
                total_char_count=len(content),
                total_line_count=len(content.split("\n")),
                updated_at=_now(),
            )
        )
        await session.flush()
        return _success(f"Updated document {doc_id}.", {"id": doc_id, "updated": True})

    if api_name == "modifyNodes":
        if _is_current_page_document(record, arguments):
            return _current_page_write_blocked(api_name)
        operations = arguments.get("operations") if isinstance(arguments.get("operations"), list) else []
        if not operations:
            return _failure("No operations provided.")

        editor_data = doc.editor_data or {}
        editor_data["_last_operations"] = operations
        await session.execute(
            update(Document)
            .where(and_(Document.id == doc.id, Document.user_id == user_id))
            .values(editor_data=editor_data, updated_at=_now())
        )
        await session.flush()
        results = [{"action": operation.get("action"), "success": True} for operation in operations]
        return _success(
            f"Modified document {doc_id}. Applied {len(results)} operation(s).",
            {
                "id": doc_id,
                "results": results,
                "successCount": len(results),
                "totalCount": len(results),
            },
        )

    if api_name == "removeDocument":
        await session.execute(
            update(AgentDocument)
            .where(and_(AgentDocument.id == agent_doc.id, AgentDocument.user_id == user_id))
            .values(
                delete_reason="tool",
                deleted_at=_now(),
                deleted_by_user_id=user_id,
                policy_load="disabled",
                updated_at=_now(),
            )
        )
        await session.flush()
        return _success(f"Removed document {doc_id}.", {"deleted": True, "id": doc_id})

    if api_name == "renameDocument":
        if _is_current_page_document(record, arguments):
            return _current_page_write_blocked(api_name)
        new_title = (arguments.get("newTitle") or "").strip()
        if not new_title:
            return _failure("id and newTitle are required")
        filename = _slugify_filename(new_title)
        await session.execute(
            update(Document)
            .where(and_(Document.id == doc.id, Document.user_id == user_id))
            .values(
                filename=filename,
                source=f"agent-document://{agent_id}/{filename}",
                title=new_title,
                updated_at=_now(),
            )
        )
        await session.flush()
        return _success(
            f'Renamed document {doc_id} to "{new_title}".',
            {"id": doc_id, "newTitle": new_title, "renamed": True},
        )

    if api_name == "copyDocument":
        new_title = arguments.get("newTitle") or f"{record.get('title') or 'Untitled'} (copy)"
        copied_agent_doc, copied_doc = await _create_document(
            session,
            user_id,
            agent_id,
            new_title,
            record["content"],
            source_suffix=f"?copy={uuid4()}",
            source_agent_doc=agent_doc,
        )
        await _pin_task_document(
            session,
            user_id,
            arguments.get("taskId") or arguments.get("task_id"),
            copied_doc.id,
        )
        return _success(
            f"Copied document {doc_id} to {copied_agent_doc.id}.",
            {"copiedFromId": doc_id, "newDocumentId": copied_agent_doc.id},
        )

    if api_name == "updateLoadRule":
        rule = arguments.get("rule") or {}
        policy = dict(rule)
        values: dict[str, Any] = {
            "policy": policy,
            "updated_at": _now(),
        }
        if "policyLoadFormat" in rule:
            values["policy_load_format"] = rule["policyLoadFormat"]
        if "rule" in rule:
            values["policy_load_rule"] = rule["rule"]
            values["policy_load"] = "always" if rule["rule"] == "always" else "progressive"
        await session.execute(
            update(AgentDocument)
            .where(and_(AgentDocument.id == agent_doc.id, AgentDocument.user_id == user_id))
            .values(**values)
        )
        await session.flush()
        return _success(f"Updated load rule for document {doc_id}.", {"applied": True, "rule": rule})

    return _failure(f"Unknown agentDocuments API: {api_name}", "UnknownApiError")


async def _agent_documents_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    return _json(await run_agent_documents_api(api_name, arguments, session=session, user_id=user_id))


@register(
    AGENT_DOCUMENTS_IDENTIFIER,
    description="Agent Documents — manage agent-scoped documents.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {"type": "string", "enum": AGENT_DOCUMENTS_APIS},
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def agent_documents_tool_context_required(args: dict[str, Any]) -> str:
    return _json({"error": "Agent Documents tool requires server context (session + user_id)."})


@register(
    LEGACY_AGENT_DOCUMENTS_IDENTIFIER,
    description="Legacy Agent Documents identifier; use lobe-agent-documents.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {"type": "string", "enum": AGENT_DOCUMENTS_APIS},
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def legacy_agent_documents_tool_context_required(args: dict[str, Any]) -> str:
    return _json({"error": "Agent Documents tool requires server context (session + user_id)."})


for _api in AGENT_DOCUMENTS_APIS:
    register_context_handler(f"{AGENT_DOCUMENTS_IDENTIFIER}__{_api}", _agent_documents_context_dispatch)
    register_context_handler(f"{LEGACY_AGENT_DOCUMENTS_IDENTIFIER}__{_api}", _agent_documents_context_dispatch)
