"""GTD (Getting Things Done) server runtime tool — plan CRUD via documents.

Ports TS ``serverRuntimes/gtd.ts``:
- createPlan: Create a plan document linked to a topic
- findPlanById: Retrieve a plan by document ID
- findPlanByTopic: Retrieve a plan by topic ID
- updatePlan: Update plan goal/description/content
- updatePlanMetadata: Update plan metadata
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

GTD_IDENTIFIER = "lobehub_gtd"
PLAN_FILE_TYPE = "agent/plan"


# ---------------------------------------------------------------------------
# Context-aware implementation
# ---------------------------------------------------------------------------

async def gtd_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    **kwargs: Any,
) -> str:
    """GTD tool — manage plans as documents."""
    from sqlalchemy import select, update as sa_update
    from app.models.file import Document
    from app.models.topic_ext import TopicDocument

    if api_name == "createPlan":
        topic_id = arguments.get("topicId")
        goal = arguments.get("goal", "")
        description = arguments.get("description", "")
        content = arguments.get("content", "")

        if not topic_id:
            return json.dumps({"error": "topicId is required"})

        doc = Document(
            user_id=user_id,
            title=goal,
            description=description,
            content=content,
            file_type=PLAN_FILE_TYPE,
            source=f"gtd:{topic_id}",
            source_type="api",
            total_char_count=len(content),
            total_line_count=content.count("\n") + 1,
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        # Associate with topic
        topic_doc = TopicDocument(
            topic_id=topic_id,
            document_id=doc.id,
            user_id=user_id,
        )
        session.add(topic_doc)
        await session.flush()

        return json.dumps({
            "id": doc.id,
            "title": doc.title,
            "description": doc.description,
            "content": doc.content,
            "createdAt": doc.created_at.isoformat() if doc.created_at else None,
        })

    elif api_name == "findPlanById":
        plan_id = arguments.get("id")
        if not plan_id:
            return json.dumps({"error": "id is required"})

        stmt = select(Document).where(
            Document.id == plan_id,
            Document.user_id == user_id,
            Document.file_type == PLAN_FILE_TYPE,
        )
        doc = (await session.execute(stmt)).scalar_one_or_none()
        if not doc:
            return json.dumps({"error": f"Plan not found: {plan_id}", "result": None})

        return json.dumps({
            "id": doc.id,
            "title": doc.title,
            "description": doc.description,
            "content": doc.content,
            "metadata": doc.metadata_,
            "createdAt": doc.created_at.isoformat() if doc.created_at else None,
            "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
        })

    elif api_name == "findPlanByTopic":
        topic_id = arguments.get("topicId")
        if not topic_id:
            return json.dumps({"error": "topicId is required"})

        stmt = (
            select(Document)
            .join(TopicDocument, TopicDocument.document_id == Document.id)
            .where(
                TopicDocument.topic_id == topic_id,
                Document.user_id == user_id,
                Document.file_type == PLAN_FILE_TYPE,
            )
            .limit(1)
        )
        doc = (await session.execute(stmt)).scalar_one_or_none()
        if not doc:
            return json.dumps({"result": None})

        return json.dumps({
            "id": doc.id,
            "title": doc.title,
            "description": doc.description,
            "content": doc.content,
            "metadata": doc.metadata_,
            "createdAt": doc.created_at.isoformat() if doc.created_at else None,
            "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
        })

    elif api_name == "updatePlan":
        plan_id = arguments.get("id")
        if not plan_id:
            return json.dumps({"error": "id is required"})

        update_data: dict[str, Any] = {}
        if "goal" in arguments:
            update_data["title"] = arguments["goal"]
        if "description" in arguments:
            update_data["description"] = arguments["description"]
        if "content" in arguments:
            c = arguments["content"]
            update_data["content"] = c
            update_data["total_char_count"] = len(c)
            update_data["total_line_count"] = c.count("\n") + 1

        if update_data:
            await session.execute(
                sa_update(Document)
                .where(Document.id == plan_id, Document.user_id == user_id)
                .values(**update_data)
            )
            await session.flush()

        # Re-fetch
        doc = (await session.execute(
            select(Document).where(Document.id == plan_id)
        )).scalar_one_or_none()

        if not doc:
            return json.dumps({"error": f"Plan not found after update: {plan_id}"})

        return json.dumps({
            "id": doc.id,
            "title": doc.title,
            "description": doc.description,
            "content": doc.content,
            "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
        })

    elif api_name == "updatePlanMetadata":
        plan_id = arguments.get("id")
        metadata = arguments.get("metadata", {})
        if not plan_id:
            return json.dumps({"error": "id is required"})

        await session.execute(
            sa_update(Document)
            .where(Document.id == plan_id, Document.user_id == user_id)
            .values(metadata_=metadata)
        )
        await session.flush()
        return json.dumps({"success": True})

    return json.dumps({"error": f"Unknown GTD API: {api_name}"})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@register(
    GTD_IDENTIFIER,
    description="GTD (Getting Things Done) — manage plans linked to topics. "
                "APIs: createPlan, findPlanById, findPlanByTopic, updatePlan, updatePlanMetadata.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "enum": ["createPlan", "findPlanById", "findPlanByTopic", "updatePlan", "updatePlanMetadata"],
            },
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def gtd_tool_stub(args: dict[str, Any]) -> str:
    return json.dumps({"error": "GTD tool requires server context (session + user_id)."})


register_context_handler(GTD_IDENTIFIER, gtd_with_context)
