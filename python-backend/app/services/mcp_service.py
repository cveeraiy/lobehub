"""MCP (Model Context Protocol) client service.

Full MCP client implementation supporting:
- **Streamable HTTP** — JSON-RPC over HTTP (replaces SSE)
- **stdio** — spawn a subprocess and communicate over stdin/stdout

Provides:
- Connection pool with keyed client caching
- `initialize` handshake with capability negotiation
- `list_tools`, `list_resources`, `list_prompts`
- `call_tool` with content-block processing (images/audio → S3)
- Manifest generation for both HTTP and stdio servers
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Optional

import httpx

logger = logging.getLogger(__name__)

# Type alias for content processing callback
ProcessContentBlocksFn = Callable[
    [list[dict[str, Any]]], Coroutine[Any, Any, list[dict[str, Any]]]
]


# ── Types ────────────────────────────────────────────────────────────

class MCPToolCallRawResult:
    """Raw result from an MCP tool call."""
    __slots__ = ("content", "is_error")

    def __init__(self, content: list[dict[str, Any]], is_error: bool = False):
        self.content = content
        self.is_error = is_error


class MCPToolCallProcessedResult:
    """Processed result from an MCP tool call."""
    __slots__ = ("content", "state", "success", "error")

    def __init__(
        self,
        content: str,
        state: dict[str, Any],
        success: bool,
        error: Optional[Exception] = None,
    ):
        self.content = content
        self.state = state
        self.success = success
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "state": self.state,
            "success": self.success,
            "error": str(self.error) if self.error else None,
        }


# ── HTTP Transport ───────────────────────────────────────────────────

class MCPHTTPClient:
    """MCP client over Streamable HTTP (JSON-RPC)."""

    def __init__(
        self,
        url: str,
        *,
        name: str = "",
        auth: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
    ) -> None:
        self.url = url.rstrip("/")
        self.name = name
        self.timeout = timeout
        self._id_counter = 0
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if headers:
            self._headers.update(headers)
        # Bearer token auth
        if auth:
            token = auth.get("accessToken") or auth.get("token")
            if token and auth.get("type") in ("bearer", "oauth2"):
                self._headers["Authorization"] = f"Bearer {token}"
        self._session_id: Optional[str] = None
        self._initialized = False
        # Persistent HTTP client — reuses TCP connections across RPC calls
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def initialize(self) -> dict[str, Any]:
        """Perform MCP initialize handshake."""
        result = await self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "lobehub-python", "version": "0.1.0"},
        })
        self._initialized = True
        # Send initialized notification
        await self._notify("notifications/initialized", {})
        return result

    async def _send(self, method: str, params: dict[str, Any]) -> Any:
        self._id_counter += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._id_counter,
            "method": method,
            "params": params,
        }
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        resp = await self._client.post(self.url, json=payload, headers=headers)
        resp.raise_for_status()
        # Capture session ID from response headers
        if "mcp-session-id" in resp.headers:
            self._session_id = resp.headers["mcp-session-id"]
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        return data.get("result", {})

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        try:
            await self._client.post(self.url, json=payload, headers=headers)
        except Exception:
            pass  # Notifications are best-effort

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._send("tools/list", {})
        return result.get("tools", [])

    async def list_resources(self) -> list[dict[str, Any]]:
        result = await self._send("resources/list", {})
        return result.get("resources", [])

    async def list_prompts(self) -> list[dict[str, Any]]:
        result = await self._send("prompts/list", {})
        return result.get("prompts", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._send("tools/call", {"name": name, "arguments": arguments})


# ── Stdio Transport ──────────────────────────────────────────────────

class MCPStdioClient:
    """MCP client over subprocess stdio (JSON-RPC over stdin/stdout)."""

    def __init__(
        self,
        command: str,
        *,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        name: str = "",
        timeout: int = 60,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env
        self.name = name
        self.timeout = timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._id_counter = 0
        self._initialized = False

    async def start(self) -> None:
        import os
        merged_env = dict(os.environ)
        if self.env:
            merged_env.update(self.env)
        self._process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

    async def stop(self) -> None:
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None

    async def initialize(self) -> dict[str, Any]:
        """Perform MCP initialize handshake."""
        if not self._process:
            await self.start()
        result = await self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "lobehub-python", "version": "0.1.0"},
        })
        self._initialized = True
        await self._notify("notifications/initialized", {})
        return result

    async def _send(self, method: str, params: dict[str, Any]) -> Any:
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("MCPStdioClient not started")

        self._id_counter += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._id_counter,
            "method": method,
            "params": params,
        }
        line = json.dumps(request) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

        raw = await asyncio.wait_for(
            self._process.stdout.readline(), timeout=self.timeout
        )
        data = json.loads(raw.decode())
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        return data.get("result", {})

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        line = json.dumps(payload) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._send("tools/list", {})
        return result.get("tools", [])

    async def list_resources(self) -> list[dict[str, Any]]:
        result = await self._send("resources/list", {})
        return result.get("resources", [])

    async def list_prompts(self) -> list[dict[str, Any]]:
        result = await self._send("prompts/list", {})
        return result.get("prompts", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._send("tools/call", {"name": name, "arguments": arguments})


# ── MCPClientParams ──────────────────────────────────────────────────

MCPClient = MCPHTTPClient | MCPStdioClient


class MCPClientParams:
    """Union type for MCP client connection parameters."""

    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.type: str = data.get("type", "http")
        self.name: str = data.get("name", "")

    def to_key(self) -> str:
        """Serialize params to a cache key."""
        sorted_keys = sorted(self.data.keys())
        return json.dumps({k: self.data[k] for k in sorted_keys if k != "env"})


# ── MCPService (singleton) ───────────────────────────────────────────

# Max cached MCP clients and idle TTL (seconds)
_MCP_CACHE_MAX = 64
_MCP_IDLE_TTL = 1800  # 30 min


class _CachedClient:
    __slots__ = ("client", "last_used")

    def __init__(self, client: MCPClient) -> None:
        self.client = client
        self.last_used = time.monotonic()


class MCPService:
    """Central MCP service with connection pooling, LRU eviction, and retry."""

    def __init__(self) -> None:
        self._clients: dict[str, _CachedClient] = {}

    async def get_client(
        self, params: dict[str, Any], *, skip_cache: bool = False,
    ) -> MCPClient:
        """Get or create an initialized MCP client."""
        cp = MCPClientParams(params)
        key = cp.to_key()

        if not skip_cache and key in self._clients:
            entry = self._clients[key]
            entry.last_used = time.monotonic()
            return entry.client

        client: MCPClient
        if cp.type == "stdio":
            client = MCPStdioClient(
                command=params["command"],
                args=params.get("args", []),
                env=params.get("env"),
                name=cp.name,
            )
        else:
            client = MCPHTTPClient(
                url=params["url"],
                name=cp.name,
                auth=params.get("auth"),
                headers=params.get("headers"),
            )

        try:
            await client.initialize()
        except Exception as exc:
            logger.error("Failed to initialize MCP client %s: %s", cp.name, exc)
            raise RuntimeError(f"Failed to initialize MCP client: {exc}") from exc

        # Evict stale / over-limit entries before caching
        await self._evict()
        self._clients[key] = _CachedClient(client)
        return client

    async def _evict(self) -> None:
        """Close idle clients and enforce cache size limit."""
        now = time.monotonic()
        stale = [k for k, v in self._clients.items() if (now - v.last_used) > _MCP_IDLE_TTL]
        for k in stale:
            await self._close_entry(k)

        # If still over limit, evict LRU
        while len(self._clients) >= _MCP_CACHE_MAX:
            lru_key = min(self._clients, key=lambda k: self._clients[k].last_used)
            await self._close_entry(lru_key)

    async def _close_entry(self, key: str) -> None:
        entry = self._clients.pop(key, None)
        if entry is None:
            return
        client = entry.client
        try:
            if isinstance(client, MCPHTTPClient):
                await client.close()
            elif isinstance(client, MCPStdioClient):
                await client.stop()
        except Exception:
            logger.debug("Error closing MCP client %s", key, exc_info=True)

    # ── List operations ───────────────────────────────────────────

    async def list_tools(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """List tools as LobeChat-compatible API schemas."""
        max_retries = 3
        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                client = await self.get_client(params, skip_cache=attempt > 0)
                raw_tools = await client.list_tools()
                return [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "parameters": t.get("inputSchema", {}),
                    }
                    for t in raw_tools
                ]
            except Exception as exc:
                last_error = exc
                logger.warning("list_tools attempt %d failed: %s", attempt + 1, exc)
        raise RuntimeError(f"list_tools failed after {max_retries} retries: {last_error}")

    async def list_raw_tools(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """List raw MCP tool objects."""
        client = await self.get_client(params)
        return await client.list_tools()

    async def list_resources(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """List MCP resources."""
        client = await self.get_client(params)
        return await client.list_resources()

    async def list_prompts(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """List MCP prompts."""
        client = await self.get_client(params)
        return await client.list_prompts()

    # ── Tool calling ──────────────────────────────────────────────

    async def call_tool(
        self,
        *,
        client_params: dict[str, Any],
        tool_name: str,
        args: Any,
        process_content_blocks: Optional[ProcessContentBlocksFn] = None,
    ) -> MCPToolCallProcessedResult:
        """Call a tool on an MCP server and return processed result."""
        client = await self.get_client(client_params)

        # Parse args if string
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        try:
            result = await client.call_tool(tool_name, args or {})
            raw = MCPToolCallRawResult(
                content=result.get("content", []),
                is_error=result.get("isError", False),
            )
            return await self.process_tool_call_result(raw, process_content_blocks)
        except Exception as exc:
            logger.error("MCP tool %s failed: %s", tool_name, exc)
            return MCPToolCallProcessedResult(
                content=str(exc),
                state={"content": [{"type": "text", "text": str(exc)}], "isError": True},
                success=False,
                error=exc,
            )

    @staticmethod
    async def process_tool_call_result(
        raw: MCPToolCallRawResult,
        process_fn: Optional[ProcessContentBlocksFn] = None,
    ) -> MCPToolCallProcessedResult:
        """Process MCP tool result: upload images/audio, convert to string."""
        from app.services.mcp_content_processor import content_blocks_to_string

        new_content = raw.content
        if not raw.is_error and process_fn:
            new_content = await process_fn(raw.content)

        content_str = content_blocks_to_string(new_content)
        state = {"content": new_content, "isError": raw.is_error}

        return MCPToolCallProcessedResult(
            content=content_str, state=state, success=True,
        )

    # ── Manifest generation ───────────────────────────────────────

    async def get_streamable_manifest(
        self,
        identifier: str,
        url: str,
        metadata: Optional[dict[str, Any]] = None,
        auth: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Build a ToolManifest for a streamable HTTP MCP server."""
        params: dict[str, Any] = {"name": identifier, "type": "http", "url": url}
        if auth:
            params["auth"] = auth
        if headers:
            params["headers"] = headers

        tools = await self.list_tools(params)

        desc = (
            metadata.get("description")
            if metadata and metadata.get("description")
            else f"{identifier} MCP server has {len(tools)} tools"
            + (f', like "{tools[0]["name"]}"' if tools else "")
        )

        return {
            "identifier": identifier,
            "type": "mcp",
            "api": tools,
            "mcpParams": params,
            "meta": {
                "avatar": (metadata or {}).get("avatar", "MCP_AVATAR"),
                "description": desc,
                "title": (metadata or {}).get("name", identifier),
            },
        }

    async def get_stdio_manifest(
        self,
        params: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Build a ToolManifest for a stdio MCP server."""
        mcp_params = {
            "type": "stdio",
            "name": params.get("name", ""),
            "command": params["command"],
            "args": params.get("args", []),
            "env": params.get("env"),
        }

        client = await self.get_client(mcp_params)

        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        identifier = params.get("name", "")
        parts = []
        if tools:
            parts.append(f"{len(tools)} tools")
        if resources:
            parts.append(f"{len(resources)} resources")
        if prompts:
            parts.append(f"{len(prompts)} prompts")

        desc = (
            metadata.get("description")
            if metadata and metadata.get("description")
            else f"{identifier} MCP server has {', '.join(parts)}"
        )

        api = [
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "parameters": t.get("inputSchema", {}),
            }
            for t in tools
        ]

        return {
            "identifier": identifier,
            "type": "mcp",
            "api": api,
            "tools": tools,
            "resources": resources,
            "prompts": prompts,
            "mcpParams": mcp_params,
            "meta": {
                "avatar": (metadata or {}).get("avatar", "MCP_AVATAR"),
                "description": desc,
                "title": (metadata or {}).get("name", identifier),
            },
        }


# Singleton instance
mcp_service = MCPService()


# ── Backward-compatible convenience function ─────────────────────────

async def call_tool(
    client: MCPHTTPClient | MCPStdioClient,
    name: str,
    arguments: dict[str, Any],
) -> str:
    """Call an MCP tool and return the result as a JSON string."""
    result = await client.call_tool(name, arguments)
    # MCP tools may return content array or direct result
    if isinstance(result, dict) and "content" in result:
        content_items = result["content"]
        texts = [
            item.get("text", json.dumps(item))
            for item in (content_items if isinstance(content_items, list) else [content_items])
        ]
        return "\n".join(texts)
    return json.dumps(result)
