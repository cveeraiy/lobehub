from __future__ import annotations

from typing import Any

import pytest

from app.routers import klavis


@pytest.mark.asyncio
async def test_call_klavis_tool_returns_mcp_result_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_klavis_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"method": method, "path": path, **kwargs})
        return {
            "result": {
                "content": [{"text": "done", "type": "text"}],
                "isError": False,
            },
            "success": True,
        }

    monkeypatch.setattr(klavis, "_klavis_request", fake_klavis_request)

    result = await klavis.call_tool(
        klavis.CallToolBody(
            server_url="https://klavis.example.test/mcp",
            tool_args={"query": "status"},
            tool_name="search",
        ),
        user_id="user-1",
    )

    assert calls == [
        {
            "json": {
                "serverUrl": "https://klavis.example.test/mcp",
                "toolArgs": {"query": "status"},
                "toolName": "search",
            },
            "method": "POST",
            "path": "/mcp/call-tool",
        }
    ]
    assert result == {
        "content": [{"text": "done", "type": "text"}],
        "state": {"content": [{"text": "done", "type": "text"}], "isError": False},
        "success": True,
    }


@pytest.mark.asyncio
async def test_call_klavis_tool_maps_remote_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_klavis_request(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"error": "not connected", "success": False}

    monkeypatch.setattr(klavis, "_klavis_request", fake_klavis_request)

    result = await klavis.call_tool(
        klavis.CallToolBody(server_url="https://klavis.example.test/mcp", tool_name="search"),
        user_id="user-1",
    )

    assert result == {
        "content": "not connected",
        "state": {"content": [{"text": "not connected", "type": "text"}], "isError": True},
        "success": False,
    }


@pytest.mark.asyncio
async def test_get_and_list_klavis_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_klavis_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"method": method, "path": path, **kwargs})
        return {"tools": [{"inputSchema": {"type": "object"}, "name": "search"}]}

    monkeypatch.setattr(klavis, "_klavis_request", fake_klavis_request)

    by_name = await klavis.get_tools(server_name="Google Calendar")
    by_url = await klavis.list_tools(server_url="https://klavis.example.test/mcp", user_id="user-1")

    assert by_name == {"tools": [{"inputSchema": {"type": "object"}, "name": "search"}]}
    assert by_url == {"tools": [{"inputSchema": {"type": "object"}, "name": "search"}]}
    assert calls == [
        {"method": "GET", "path": "/mcp/tools?serverName=Google Calendar"},
        {
            "json": {"serverUrl": "https://klavis.example.test/mcp"},
            "method": "POST",
            "path": "/mcp/list-tools",
        },
    ]
