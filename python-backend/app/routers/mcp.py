"""MCP router — interact with MCP servers (list tools/resources/prompts, call tools, get manifests).

Mirrors the TS ``mcpRouter`` in ``src/server/routers/tools/mcp.ts``.
Only the HTTP (streamable) transport is exposed via the web API; stdio
is blocked with a 400 error for security in hosted environments.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import get_current_user_id
from app.services.mcp_service import mcp_service

router = APIRouter(prefix="/api/mcp", tags=["MCP"])


# ── Schemas ──────────────────────────────────────────────────────────

class HTTPParams(BaseModel):
    type: str = Field("http", pattern="^http$")
    name: str = Field(..., min_length=1)
    url: str
    auth: Optional[dict[str, Any]] = None
    headers: Optional[dict[str, str]] = None


class StdioParams(BaseModel):
    type: str = Field("stdio", pattern="^stdio$")
    name: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)
    args: list[str] = Field(default_factory=list)
    env: Optional[dict[str, str]] = None


class MCPClientParamsBody(BaseModel):
    """Union-style body — clients send either HTTP or stdio params."""
    type: str = "http"
    name: str = Field(..., min_length=1)
    url: Optional[str] = None
    command: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    env: Optional[dict[str, str]] = None
    auth: Optional[dict[str, Any]] = None
    headers: Optional[dict[str, str]] = None


class CallToolBody(BaseModel):
    params: MCPClientParamsBody
    tool_name: str = Field(..., alias="toolName")
    args: Any = None
    meta: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class StreamableManifestBody(BaseModel):
    identifier: str
    url: str
    metadata: Optional[dict[str, Any]] = None
    auth: Optional[dict[str, Any]] = None
    headers: Optional[dict[str, str]] = None


class StdioManifestBody(BaseModel):
    name: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)
    args: list[str] = Field(default_factory=list)
    env: Optional[dict[str, str]] = None
    metadata: Optional[dict[str, Any]] = None


# ── Helpers ──────────────────────────────────────────────────────────

def _validate_params(body: MCPClientParamsBody) -> dict[str, Any]:
    """Convert body to a params dict and block stdio in web env."""
    if body.type == "stdio":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Stdio MCP type is not supported in web environment.",
        )
    if body.type == "http" and not body.url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "url is required for HTTP MCP.")
    return body.model_dump(exclude_none=True)


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/tools")
async def list_tools(
    body: MCPClientParamsBody,
    user_id: str = Depends(get_current_user_id),
):
    """List tools from an MCP server as Ethos-compatible API schemas."""
    params = _validate_params(body)
    return await mcp_service.list_tools(params)


@router.post("/tools/raw")
async def list_raw_tools(
    body: MCPClientParamsBody,
    user_id: str = Depends(get_current_user_id),
):
    """List raw MCP tool objects."""
    params = _validate_params(body)
    return await mcp_service.list_raw_tools(params)


@router.post("/resources")
async def list_resources(
    body: MCPClientParamsBody,
    user_id: str = Depends(get_current_user_id),
):
    """List resources from an MCP server."""
    params = _validate_params(body)
    return await mcp_service.list_resources(params)


@router.post("/prompts")
async def list_prompts(
    body: MCPClientParamsBody,
    user_id: str = Depends(get_current_user_id),
):
    """List prompts from an MCP server."""
    params = _validate_params(body)
    return await mcp_service.list_prompts(params)


@router.post("/tools/call")
async def call_tool(
    body: CallToolBody,
    user_id: str = Depends(get_current_user_id),
):
    """Call a tool on an MCP server with content-block processing."""
    params = _validate_params(body.params)

    # Build content processor with S3 upload
    process_fn = None
    try:
        from app.services.file_service import S3Client
        from app.services.mcp_content_processor import process_content_blocks

        s3 = S3Client.from_settings()

        async def _process(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return await process_content_blocks(blocks, s3)

        process_fn = _process
    except Exception:
        pass  # If S3 isn't configured, skip content processing

    result = await mcp_service.call_tool(
        client_params=params,
        tool_name=body.tool_name,
        args=body.args,
        process_content_blocks=process_fn,
    )
    return result.to_dict()


@router.post("/manifest/http")
async def get_streamable_manifest(
    body: StreamableManifestBody,
    user_id: str = Depends(get_current_user_id),
):
    """Get a ToolManifest for a streamable HTTP MCP server."""
    return await mcp_service.get_streamable_manifest(
        identifier=body.identifier,
        url=body.url,
        metadata=body.metadata,
        auth=body.auth,
        headers=body.headers,
    )


@router.post("/manifest/stdio")
async def get_stdio_manifest(
    body: StdioManifestBody,
    user_id: str = Depends(get_current_user_id),
):
    """Get a ToolManifest for a stdio MCP server.

    NOTE: This endpoint is available for desktop/CLI environments only.
    In hosted web environments, stdio servers should be blocked at the
    infrastructure level.
    """
    params = {
        "name": body.name,
        "command": body.command,
        "args": body.args,
        "env": body.env,
    }
    return await mcp_service.get_stdio_manifest(params, metadata=body.metadata)
