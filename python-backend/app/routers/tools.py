"""Manual tool execution router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services.tool_execution import execute_tool_call_with_context, list_builtin_tools

router = APIRouter(prefix="/api/tools", tags=["Tools"])


# ── Schemas ──────────────────────────────────────────────────────────

class RunToolBody(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_tools(
    user_id: str = Depends(get_current_user_id),
):
    """Return all registered builtin tool names."""
    return {"tools": list_builtin_tools()}


@router.post("/run")
async def run_tool(
    body: RunToolBody,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Manually invoke a tool by name."""
    result = await execute_tool_call_with_context(body.tool_name, body.arguments, session=session, user_id=user_id)
    return {"result": result}
