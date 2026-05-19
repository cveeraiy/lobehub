from types import SimpleNamespace

import pytest

from app.routers.webapi import _stream_openai_chunks


pytestmark = pytest.mark.asyncio


async def _chunks():
    yield SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content="hello"),
                finish_reason=None,
            )
        ],
        id="chunk-1",
        usage=None,
    )
    yield {
        "choices": [
            {
                "delta": {},
                "finish_reason": "stop",
            }
        ],
        "id": "chunk-2",
        "usage": {"completion_tokens": 1, "prompt_tokens": 2, "total_tokens": 3},
    }


async def test_webapi_stream_converts_chunks_to_frontend_events():
    body = "".join([part async for part in _stream_openai_chunks("bedrock", _chunks())])

    assert 'event: text\ndata: "hello"' in body
    assert 'event: stop\ndata: "stop"' in body
    assert 'event: usage\ndata: {"input_tokens":2,"output_tokens":1,"total_tokens":3}' in body
    assert "[DONE]" not in body
