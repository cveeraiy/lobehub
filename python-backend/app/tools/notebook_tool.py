"""Notebook server runtime tool — note CRUD scoped to user.

Ports TS ``serverRuntimes/notebook.ts``:
- createNote, readNote, updateNote, deleteNote, listNotes

Simplified version that stores notes as documents with file_type='notebook/note'.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

NOTEBOOK_IDENTIFIER = "lobehub_notebook"
NOTE_FILE_TYPE = "notebook/note"


async def notebook_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    **kwargs: Any,
) -> str:
    """Notebook tool — CRUD for notes stored as documents."""
    from sqlalchemy import select, update as sa_update, delete as sa_del
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
    description="Notebook — create, read, update, delete and list notes. "
                "APIs: createNote, readNote, updateNote, deleteNote, listNotes.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "enum": ["createNote", "readNote", "updateNote", "deleteNote", "listNotes"],
            },
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def notebook_tool_stub(args: dict[str, Any]) -> str:
    return json.dumps({"error": "Notebook tool requires server context (session + user_id)."})


register_context_handler(NOTEBOOK_IDENTIFIER, notebook_with_context)
