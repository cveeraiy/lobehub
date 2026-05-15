"""Task server runtime tool — CRUD for tasks from within agent execution.

Ports TS ``serverRuntimes/task.ts``:
- createTask, editTask, deleteTask
- listTasks, viewTask
- updateTaskStatus
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

TASK_IDENTIFIER = "lobehub_task"

_PRIORITY_LABELS = {0: "none", 1: "low", 2: "medium", 3: "high", 4: "urgent"}


def _priority_label(p: int | None) -> str:
    return _PRIORITY_LABELS.get(p or 0, "none")


# ---------------------------------------------------------------------------
# Context-aware implementation
# ---------------------------------------------------------------------------

async def task_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    **kwargs: Any,
) -> str:
    """Task tool — CRUD tasks from within agent execution."""
    from sqlalchemy import select, update as sa_update, delete as sa_del
    from app.models.task import Task

    agent_id = kwargs.get("agent_id")
    task_id = kwargs.get("task_id")  # current task context

    if api_name == "createTask":
        name = arguments.get("name", "Untitled task")
        instruction = arguments.get("instruction", "")
        priority = arguments.get("priority", 0)
        assignee_agent_id = arguments.get("assigneeAgentId", agent_id)
        parent_identifier = arguments.get("parentIdentifier")

        parent_task_id = None
        if parent_identifier:
            stmt = select(Task).where(
                (Task.id == parent_identifier) | (Task.identifier == parent_identifier),
                Task.created_by_user_id == user_id,
            )
            parent = (await session.execute(stmt)).scalar_one_or_none()
            if not parent:
                return json.dumps({"success": False, "content": f"Parent task not found: {parent_identifier}"})
            parent_task_id = parent.id

        # Generate unique identifier
        from app.models._helpers import create_nanoid
        identifier = f"TASK-{create_nanoid(6).upper()}"

        task = Task(
            identifier=identifier,
            seq=0,
            created_by_user_id=user_id,
            created_by_agent_id=agent_id,
            assignee_agent_id=assignee_agent_id,
            parent_task_id=parent_task_id,
            name=name,
            instruction=instruction,
            priority=priority,
            sort_order=arguments.get("sortOrder", 0),
        )
        session.add(task)
        await session.flush()
        await session.refresh(task)

        return json.dumps({
            "success": True,
            "content": (
                f"Task created: [{task.identifier}] {task.name}\n"
                f"Status: {task.status} | Priority: {_priority_label(task.priority)}"
            ),
        })

    elif api_name == "editTask":
        identifier = arguments.get("identifier")
        if not identifier:
            return json.dumps({"success": False, "content": "identifier is required"})

        stmt = select(Task).where(
            (Task.id == identifier) | (Task.identifier == identifier),
            Task.created_by_user_id == user_id,
        )
        task = (await session.execute(stmt)).scalar_one_or_none()
        if not task:
            return json.dumps({"success": False, "content": f"Task not found: {identifier}"})

        update_data: dict[str, Any] = {}
        changes: list[str] = []

        for field, col in [("name", "name"), ("instruction", "instruction"), ("description", "description")]:
            if field in arguments and arguments[field] is not None:
                update_data[col] = arguments[field]
                changes.append(f"{field} updated")

        if "priority" in arguments and arguments["priority"] is not None:
            update_data["priority"] = arguments["priority"]
            changes.append(f"priority → {_priority_label(arguments['priority'])}")

        if "assigneeAgentId" in arguments:
            update_data["assignee_agent_id"] = arguments["assigneeAgentId"]
            changes.append(f"assignee → {arguments['assigneeAgentId'] or 'unassigned'}")

        if update_data:
            await session.execute(
                sa_update(Task).where(Task.id == task.id).values(**update_data)
            )
            await session.flush()

        return json.dumps({
            "success": True,
            "content": f"Task [{task.identifier}] edited: {', '.join(changes) or 'no changes'}",
        })

    elif api_name == "deleteTask":
        identifier = arguments.get("identifier")
        if not identifier:
            return json.dumps({"success": False, "content": "identifier is required"})

        stmt = select(Task).where(
            (Task.id == identifier) | (Task.identifier == identifier),
            Task.created_by_user_id == user_id,
        )
        task = (await session.execute(stmt)).scalar_one_or_none()
        if not task:
            return json.dumps({"success": False, "content": f"Task not found: {identifier}"})

        await session.execute(sa_del(Task).where(Task.id == task.id))
        await session.flush()

        return json.dumps({
            "success": True,
            "content": f"Task [{task.identifier}] {task.name} deleted.",
        })

    elif api_name == "listTasks":
        stmt = select(Task).where(Task.created_by_user_id == user_id)

        statuses = arguments.get("statuses")
        if statuses:
            stmt = stmt.where(Task.status.in_(statuses))

        assignee = arguments.get("assigneeAgentId")
        if assignee:
            stmt = stmt.where(Task.assignee_agent_id == assignee)
        elif agent_id:
            stmt = stmt.where(Task.assignee_agent_id == agent_id)

        limit = min(arguments.get("limit", 20), 100)
        offset = arguments.get("offset", 0)

        stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        tasks = (await session.execute(stmt)).scalars().all()

        lines = [f"Found {len(tasks)} task(s):"]
        for t in tasks:
            lines.append(
                f"  [{t.identifier}] {t.name or '(unnamed)'} "
                f"| {t.status} | {_priority_label(t.priority)}"
            )

        return json.dumps({"success": True, "content": "\n".join(lines)})

    elif api_name == "viewTask":
        identifier = arguments.get("identifier") or task_id
        if not identifier:
            return json.dumps({"success": False, "content": "No task identifier provided and no current task context."})

        stmt = select(Task).where(
            (Task.id == identifier) | (Task.identifier == identifier),
            Task.created_by_user_id == user_id,
        )
        task = (await session.execute(stmt)).scalar_one_or_none()
        if not task:
            return json.dumps({"success": False, "content": f"Task not found: {identifier}"})

        return json.dumps({
            "success": True,
            "content": (
                f"Task: [{task.identifier}] {task.name}\n"
                f"Status: {task.status} | Priority: {_priority_label(task.priority)}\n"
                f"Instruction: {task.instruction[:500]}\n"
                f"Description: {task.description or '(none)'}\n"
                f"Created: {task.created_at.isoformat() if task.created_at else '?'}"
            ),
        })

    elif api_name == "updateTaskStatus":
        identifier = arguments.get("identifier") or task_id
        status = arguments.get("status")
        error = arguments.get("error")

        if not identifier:
            return json.dumps({"success": False, "content": "No task identifier provided."})
        if not status:
            return json.dumps({"success": False, "content": "status is required"})

        stmt = select(Task).where(
            (Task.id == identifier) | (Task.identifier == identifier),
            Task.created_by_user_id == user_id,
        )
        task = (await session.execute(stmt)).scalar_one_or_none()
        if not task:
            return json.dumps({"success": False, "content": f"Task not found: {identifier}"})

        update_vals: dict[str, Any] = {"status": status}
        if error:
            update_vals["error"] = error
        if status == "completed":
            from datetime import datetime, timezone
            update_vals["completed_at"] = datetime.now(timezone.utc)

        await session.execute(
            sa_update(Task).where(Task.id == task.id).values(**update_vals)
        )
        await session.flush()

        msg = f"Task {task.identifier} status updated to {status}."
        if status == "failed" and error:
            msg += f" Error: {error}"
        return json.dumps({"success": True, "content": msg})

    return json.dumps({"error": f"Unknown task API: {api_name}"})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@register(
    TASK_IDENTIFIER,
    description="Task management — create, edit, delete, list, view, and update status of tasks. "
                "APIs: createTask, editTask, deleteTask, listTasks, viewTask, updateTaskStatus.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "enum": ["createTask", "editTask", "deleteTask", "listTasks", "viewTask", "updateTaskStatus"],
            },
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def task_tool_stub(args: dict[str, Any]) -> str:
    return json.dumps({"error": "Task tool requires server context (session + user_id)."})


register_context_handler(TASK_IDENTIFIER, task_with_context)
