"""Message conversion helpers between OpenAI format and LangChain."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


def dicts_to_lc_messages(messages: list[dict[str, Any]]) -> list[BaseMessage]:
    """Convert OpenAI-format message dicts to LangChain BaseMessage objects."""
    result: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            kwargs: dict[str, Any] = {"content": content or ""}
            if msg.get("tool_calls"):
                kwargs["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "args": json.loads(tc["function"]["arguments"])
                        if isinstance(tc.get("function", {}).get("arguments"), str)
                        else tc.get("function", {}).get("arguments", {}),
                    }
                    for tc in msg["tool_calls"]
                ]
            result.append(AIMessage(**kwargs))
        elif role == "tool":
            result.append(ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
            ))
        else:
            result.append(HumanMessage(content=content))
    return result


def lc_message_to_dict(msg: BaseMessage) -> dict[str, Any]:
    """Convert a LangChain BaseMessage back to OpenAI-format dict."""
    if isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    elif isinstance(msg, AIMessage):
        d: dict[str, Any] = {"role": "assistant", "content": msg.content or None}
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.get("id", tc.get("name", "")),
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("args", {})),
                    },
                }
                for tc in msg.tool_calls
            ]
        return d
    elif isinstance(msg, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": msg.tool_call_id,
            "content": msg.content,
        }
    elif isinstance(msg, HumanMessage):
        return {"role": "user", "content": msg.content}
    return {"role": "user", "content": str(msg.content)}
