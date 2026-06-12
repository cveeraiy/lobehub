"""Notebook server runtime tool — document CRUD scoped to user.

Ports the legacy TypeScript ``lobe-notebook`` server runtime:
- createDocument, updateDocument, getDocument, deleteDocument

The older ``lobehub_notebook`` note APIs remain registered for compatibility.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

NOTEBOOK_IDENTIFIER = "lobe-notebook"
LEGACY_NOTEBOOK_IDENTIFIER = "lobehub_notebook"
NOTE_FILE_TYPE = "notebook/note"
NOTEBOOK_APIS = ["createDocument", "updateDocument", "getDocument", "deleteDocument"]
LEGACY_NOTE_APIS = ["createNote", "readNote", "updateNote", "deleteNote", "listNotes"]


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _count_words(content: str) -> int:
    return len([part for part in content.strip().split() if part])


def _count_lines(content: str) -> int:
    return len(content.split("\n"))


def _to_notebook_document(doc: Any) -> dict[str, Any]:
    source_type = "ai" if doc.source_type == "api" else doc.source_type
    return {
        "content": doc.content or "",
        "createdAt": doc.created_at.isoformat() if doc.created_at else None,
        "description": doc.description or "",
        "id": doc.id,
        "sourceType": source_type,
        "title": doc.title or "Untitled",
        "type": doc.file_type or "markdown",
        "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
        "wordCount": doc.total_char_count,
    }


def _success(content: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"content": content, "success": True}
    if state is not None:
        result["state"] = state
    return result


def _failure(content: str, message: str, error_type: str) -> dict[str, Any]:
    return {
        "content": content,
        "error": {"message": message, "type": error_type},
        "success": False,
    }


async def _get_document(session: Any, user_id: str, document_id: str) -> Any | None:
    from sqlalchemy import and_, select

    from app.models.file import Document

    stmt = select(Document).where(and_(Document.id == document_id, Document.user_id == user_id))
    return (await session.execute(stmt)).scalar_one_or_none()


async def _delete_document(session: Any, user_id: str, document_id: str) -> bool:
    from sqlalchemy import and_, delete

    from app.models.file import Document
    from app.models.task import TaskDocument
    from app.models.topic_ext import TopicDocument

    doc = await _get_document(session, user_id, document_id)
    if not doc:
        return False

    await session.execute(delete(TaskDocument).where(TaskDocument.document_id == document_id))
    await session.execute(delete(TopicDocument).where(TopicDocument.document_id == document_id))
    await session.execute(delete(Document).where(and_(Document.id == document_id, Document.user_id == user_id)))
    await session.flush()
    return True


async def _pin_task_document(session: Any, user_id: str, task_id: str, document_id: str) -> None:
    from sqlalchemy import and_, select

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


async def run_notebook_api(
    api_name: str,
    arguments: dict[str, Any],
    *,
    session: Any,
    user_id: str,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    from sqlalchemy import and_, select

    from app.models.file import Document
    from app.models.topic_ext import TopicDocument

    if api_name == "createDocument":
        title = arguments.get("title") or "Untitled"
        content = arguments.get("content") or ""
        document_type = arguments.get("type") or "markdown"
        topic_id = arguments.get("topicId") or arguments.get("topic_id")
        task_id = arguments.get("taskId") or arguments.get("task_id")

        if not content:
            return _failure(
                "Error: Missing content. The document content is required.",
                "The document content is required.",
                "MissingContentError",
            )

        if not topic_id:
            return _failure(
                "Error: No topic context. Documents must be created within a topic.",
                "Documents must be created within a topic.",
                "MissingTopicContextError",
            )

        doc = Document(
            user_id=user_id,
            title=title,
            content=content,
            file_type=document_type,
            source=f"notebook:{topic_id}",
            source_type="api",
            total_char_count=_count_words(content),
            total_line_count=_count_lines(content),
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        topic_doc = (
            await session.execute(
                select(TopicDocument).where(
                    and_(
                        TopicDocument.topic_id == topic_id,
                        TopicDocument.document_id == doc.id,
                        TopicDocument.user_id == user_id,
                    )
                )
            )
        ).scalar_one_or_none()
        if not topic_doc:
            session.add(TopicDocument(topic_id=topic_id, document_id=doc.id, user_id=user_id))

        if task_id:
            await _pin_task_document(session, user_id, task_id, doc.id)

        await session.flush()
        await session.refresh(doc)
        notebook_doc = _to_notebook_document(doc)
        return _success(
            f'📄 Created document: "{title}"\n\nYou can view and edit this document in the Portal sidebar.',
            {"document": notebook_doc},
        )

    if api_name == "updateDocument":
        document_id = arguments.get("id")
        if not document_id:
            return _failure("Error: Missing document id.", "Document id is required.", "MissingDocumentIdError")

        doc = await _get_document(session, user_id, document_id)
        if not doc:
            return _failure(
                f"Error: Document not found: {document_id}",
                f"Document not found: {document_id}",
                "DocumentNotFoundError",
            )

        if "title" in arguments:
            doc.title = arguments.get("title")

        if "content" in arguments:
            content = arguments.get("content") or ""
            if arguments.get("append") and doc.content:
                content = f"{doc.content}\n\n{content}"
            doc.content = content
            # Match the TS runtime service update path, which counts characters
            # after updates even though create stores word count.
            doc.total_char_count = len(content)
            doc.total_line_count = _count_lines(content)

        doc.updated_at = datetime.now(UTC).replace(tzinfo=None)
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        notebook_doc = _to_notebook_document(doc)
        action_desc = "Appended to" if arguments.get("append") else "Updated"
        return _success(f'📝 {action_desc} document: "{notebook_doc["title"]}"', {"document": notebook_doc})

    if api_name == "getDocument":
        document_id = arguments.get("id")
        if not document_id:
            return _failure("Error: Missing document id.", "Document id is required.", "MissingDocumentIdError")

        doc = await _get_document(session, user_id, document_id)
        if not doc:
            return _failure(
                f"Error: Document not found: {document_id}",
                f"Document not found: {document_id}",
                "DocumentNotFoundError",
            )

        notebook_doc = _to_notebook_document(doc)
        return _success(
            f'📄 Document: "{notebook_doc["title"]}"\n\n{notebook_doc["content"]}',
            {"document": notebook_doc},
        )

    if api_name == "deleteDocument":
        document_id = arguments.get("id")
        if not document_id:
            return _failure("Error: Missing document id.", "Document id is required.", "MissingDocumentIdError")

        doc = await _get_document(session, user_id, document_id)
        if not doc:
            return _failure(
                f"Error: Document not found: {document_id}",
                f"Document not found: {document_id}",
                "DocumentNotFoundError",
            )

        title = doc.title
        await _delete_document(session, user_id, document_id)
        return _success(f'🗑️ Deleted document: "{title}"', {"deletedId": document_id})

    return _failure(
        f"Error: Unknown notebook API: {api_name}",
        f"Unknown notebook API: {api_name}",
        "UnknownApiError",
    )


async def _notebook_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    return _json(await run_notebook_api(api_name, arguments, session=session, user_id=user_id))


async def notebook_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    **kwargs: Any,
) -> str:
    """Notebook tool — CRUD for notes stored as documents."""
    from sqlalchemy import delete as sa_del
    from sqlalchemy import select
    from sqlalchemy import update as sa_update

    from app.models.file import Document

    if api_name == "createNote":
        title = arguments.get("title", "Untitled Note")
        content = arguments.get("content", "")

        doc = Document(
            user_id=user_id,
            title=title,
            content=content,
            file_type=NOTE_FILE_TYPE,
            source="notebook",
            source_type="api",
            total_char_count=len(content),
            total_line_count=content.count("\n") + 1,
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        return json.dumps({
            "success": True,
            "noteId": doc.id,
            "content": f"Note created: {title} [{doc.id}]",
        })

    elif api_name == "readNote":
        note_id = arguments.get("id")
        if not note_id:
            return json.dumps({"success": False, "content": "id is required"})

        stmt = select(Document).where(
            Document.id == note_id,
            Document.user_id == user_id,
            Document.file_type == NOTE_FILE_TYPE,
        )
        doc = (await session.execute(stmt)).scalar_one_or_none()
        if not doc:
            return json.dumps({"success": False, "content": f"Note not found: {note_id}"})

        return json.dumps({
            "success": True,
            "noteId": doc.id,
            "title": doc.title,
            "content": doc.content,
            "createdAt": doc.created_at.isoformat() if doc.created_at else None,
            "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
        })

    elif api_name == "updateNote":
        note_id = arguments.get("id")
        if not note_id:
            return json.dumps({"success": False, "content": "id is required"})

        update_data: dict[str, Any] = {}
        if "title" in arguments:
            update_data["title"] = arguments["title"]
        if "content" in arguments:
            c = arguments["content"]
            update_data["content"] = c
            update_data["total_char_count"] = len(c)
            update_data["total_line_count"] = c.count("\n") + 1

        if update_data:
            result = await session.execute(
                sa_update(Document)
                .where(
                    Document.id == note_id,
                    Document.user_id == user_id,
                    Document.file_type == NOTE_FILE_TYPE,
                )
                .values(**update_data)
            )
            if result.rowcount == 0:  # type: ignore[union-attr]
                return json.dumps({"success": False, "content": f"Note not found: {note_id}"})
            await session.flush()

        return json.dumps({"success": True, "content": f"Note {note_id} updated."})

    elif api_name == "deleteNote":
        note_id = arguments.get("id")
        if not note_id:
            return json.dumps({"success": False, "content": "id is required"})

        result = await session.execute(
            sa_del(Document).where(
                Document.id == note_id,
                Document.user_id == user_id,
                Document.file_type == NOTE_FILE_TYPE,
            )
        )
        if result.rowcount == 0:  # type: ignore[union-attr]
            return json.dumps({"success": False, "content": f"Note not found: {note_id}"})
        await session.flush()
        return json.dumps({"success": True, "content": f"Note {note_id} deleted."})

    elif api_name == "listNotes":
        limit = min(arguments.get("limit", 50), 200)
        offset = arguments.get("offset", 0)

        stmt = (
            select(Document)
            .where(Document.user_id == user_id, Document.file_type == NOTE_FILE_TYPE)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        docs = (await session.execute(stmt)).scalars().all()

        items = [
            {"id": d.id, "title": d.title, "createdAt": d.created_at.isoformat() if d.created_at else None}
            for d in docs
        ]
        return json.dumps({
            "success": True,
            "notes": items,
            "content": f"Found {len(items)} note(s).",
        })

    return json.dumps({"error": f"Unknown notebook API: {api_name}"})


@register(
    NOTEBOOK_IDENTIFIER,
    description="Notebook — create, update, read, and delete topic-scoped documents. "
                "APIs: createDocument, updateDocument, getDocument, deleteDocument.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "enum": NOTEBOOK_APIS,
            },
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def notebook_tool_context_required(args: dict[str, Any]) -> str:
    return json.dumps({"error": "Notebook tool requires server context (session + user_id)."})


@register(
    LEGACY_NOTEBOOK_IDENTIFIER,
    description="Legacy notebook note CRUD. APIs: createNote, readNote, updateNote, deleteNote, listNotes.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {"type": "string", "enum": LEGACY_NOTE_APIS},
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def legacy_notebook_tool_context_required(args: dict[str, Any]) -> str:
    return json.dumps({"error": "Legacy notebook tool requires server context (session + user_id)."})


async def _legacy_notebook_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    return await notebook_with_context(api_name, arguments, session, user_id, **kwargs)


for _api in NOTEBOOK_APIS:
    register_context_handler(f"{NOTEBOOK_IDENTIFIER}__{_api}", _notebook_context_dispatch)

for _api in LEGACY_NOTE_APIS:
    register_context_handler(f"{LEGACY_NOTEBOOK_IDENTIFIER}__{_api}", _legacy_notebook_context_dispatch)
