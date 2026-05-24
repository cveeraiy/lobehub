"""Model runtime bridge for TypeScript backend removal."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user_id
from app.services import llm_service
from app.services import provider_runtime
from app.services.ai_infra_service import service as ai_svc

router = APIRouter(prefix="/api/model-runtime", tags=["model-runtime"])


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return _jsonable(value.dict())
    return str(value)


def _first_image_url(data: Any) -> str | None:
    if isinstance(data, dict):
        items = data.get("data")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first.get("url") or first.get("b64_json")
        return data.get("url") or data.get("image_url") or data.get("imageUrl")
    return None


def _image_size(data: Any) -> tuple[int | None, int | None]:
    if isinstance(data, dict):
        if isinstance(data.get("width"), int) or isinstance(data.get("height"), int):
            return data.get("width"), data.get("height")
        items = data.get("data")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return items[0].get("width"), items[0].get("height")
    return None, None


def _schema_tool(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": schema.get("name") or "structured_output",
            "description": schema.get("description")
            or "Generate structured output according to the provided schema",
            "parameters": schema.get("schema") or {"type": "object", "properties": {}},
        },
    }


def _decode_tool_arguments(arguments: Any) -> Any:
    if isinstance(arguments, str):
        return json.loads(arguments)
    return arguments


def _extract_tool_result(data: dict[str, Any], *, schema_tool_name: str | None = None) -> Any:
    message = ((data.get("choices") or [{}])[0].get("message") or {})
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None

    results: list[dict[str, Any]] = []
    for call in tool_calls:
        fn = call.get("function") or {}
        name = fn.get("name")
        arguments = _decode_tool_arguments(fn.get("arguments") or "{}")
        if schema_tool_name and name == schema_tool_name:
            return arguments
        results.append({"arguments": arguments, "name": name})

    return results


def _extract_json_content(data: dict[str, Any]) -> Any:
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}")
    if not isinstance(content, str):
        return content

    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)


async def _resolve(session: AsyncSession, user_id: str, provider: str):
    return await provider_runtime.resolve_provider_config(session, user_id, provider)


@router.post("/chat")
async def chat(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = body.get("provider") or "openai"
    payload = body.get("payload") or {}
    runtime = await _resolve(session, user_id, provider)
    model = payload.get("model") or body.get("model") or "gpt-4o-mini"

    response = await llm_service.chat(
        payload.get("messages") or [],
        model=provider_runtime.model_for_litellm(runtime, model),
        stream=False,
        temperature=payload.get("temperature"),
        max_tokens=payload.get("max_tokens"),
        api_key=runtime.api_key,
        api_base=runtime.api_base,
        extra_kwargs=provider_runtime.chat_extra_kwargs(runtime, payload),
    )
    return _jsonable(response)


@router.post("/embeddings")
async def embeddings(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = body.get("provider") or "openai"
    payload = body.get("payload") or {}
    runtime = await _resolve(session, user_id, provider)
    model = payload.get("model") or body.get("model") or "text-embedding-3-small"
    input_value = payload.get("input") or []
    texts = input_value if isinstance(input_value, list) else [input_value]

    return await llm_service.embed(
        texts,
        model=provider_runtime.model_for_litellm(runtime, model),
        api_key=runtime.api_key,
        api_base=runtime.api_base,
        dimensions=payload.get("dimensions"),
    )


@router.post("/generate-object")
async def generate_object(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = body.get("provider") or "openai"
    payload = body.get("payload") or {}
    runtime = await _resolve(session, user_id, provider)
    model = payload.get("model") or body.get("model") or "gpt-4o-mini"
    schema = payload.get("schema")
    tools = payload.get("tools")

    extra_kwargs = provider_runtime.chat_extra_kwargs(runtime, payload)
    schema_tool_name: str | None = None
    if tools:
        extra_kwargs["tools"] = tools
        extra_kwargs["tool_choice"] = "auto"
    elif isinstance(schema, dict):
        tool = _schema_tool(schema)
        schema_tool_name = tool["function"]["name"]
        extra_kwargs["tools"] = [tool]
        extra_kwargs["tool_choice"] = {
            "type": "function",
            "function": {"name": schema_tool_name},
        }
    else:
        extra_kwargs["response_format"] = {"type": "json_object"}

    response = await llm_service.chat(
        payload.get("messages") or [],
        model=provider_runtime.model_for_litellm(runtime, model),
        stream=False,
        temperature=payload.get("temperature"),
        api_key=runtime.api_key,
        api_base=runtime.api_base,
        extra_kwargs=extra_kwargs,
    )
    data = _jsonable(response)
    if isinstance(data, dict):
        try:
            tool_result = _extract_tool_result(data, schema_tool_name=schema_tool_name)
            if tool_result is not None:
                return tool_result
            parsed = _extract_json_content(data)
            return parsed if isinstance(parsed, (dict, list)) else {"content": parsed}
        except (TypeError, json.JSONDecodeError):
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
            return {"content": content}
    return data


@router.get("/models/{provider}")
async def models(
    provider: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    runtime = await _resolve(session, user_id, provider)
    remote_models = await provider_runtime.list_remote_models(runtime)
    if remote_models is not None:
        return remote_models
    models = await ai_svc.get_provider_model_list(session, user_id, provider)
    return [
        {
            "abilities": item.get("abilities") or {},
            "displayName": item.get("display_name") or item.get("id"),
            "enabled": item.get("enabled", True),
            "id": item.get("id"),
            "type": item.get("type", "chat"),
        }
        for item in models
    ]


@router.post("/image")
async def image(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = body.get("provider") or "openai"
    payload = body.get("payload") or {}
    params = payload.get("params") or {}
    runtime = await _resolve(session, user_id, provider)
    model = payload.get("model") or body.get("model")
    prompt = params.get("prompt") or payload.get("prompt")
    if not model or not prompt:
        return {"error": "model and prompt are required", "success": False}

    response = await litellm.aimage_generation(
        model=provider_runtime.model_for_litellm(runtime, model),
        prompt=prompt,
        api_key=runtime.api_key,
        api_base=runtime.api_base,
        n=params.get("n") or params.get("imageNum") or 1,
        size=params.get("size"),
    )
    data = _jsonable(response)
    image_url = _first_image_url(data)
    width, height = _image_size(data)

    return {
        "height": height or params.get("height"),
        "imageUrl": image_url,
        "modelUsage": data.get("usage") if isinstance(data, dict) else None,
        "raw": data,
        "width": width or params.get("width"),
    }


@router.post("/video")
async def video(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = body.get("provider") or "openai"
    payload = body.get("payload") or {}
    params = payload.get("params") or {}
    runtime = await _resolve(session, user_id, provider)
    model = payload.get("model") or body.get("model")
    prompt = params.get("prompt") or payload.get("prompt")
    if not model or not prompt:
        return {"error": "model and prompt are required", "success": False}

    response = await litellm.avideo_generation(
        prompt=prompt,
        model=provider_runtime.model_for_litellm(runtime, model),
        api_key=runtime.api_key,
        api_base=runtime.api_base,
        seconds=str(params.get("duration")) if params.get("duration") else None,
        size=params.get("resolution") or params.get("size"),
    )
    data = _jsonable(response)
    inference_id = data.get("id") or data.get("video_id") or data.get("videoId") if isinstance(data, dict) else None

    return {
        "inferenceId": inference_id,
        "raw": data,
        "useWebhook": False,
    }


@router.post("/video/status")
async def video_status(
    body: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    provider = body.get("provider") or "openai"
    runtime = await _resolve(session, user_id, provider)
    inference_id = body.get("inferenceId") or body.get("inference_id")
    if not inference_id:
        return {"error": "inferenceId is required", "status": "failed"}

    response = await litellm.avideo_status(
        video_id=inference_id,
        api_key=runtime.api_key,
        api_base=runtime.api_base,
    )
    data = _jsonable(response)
    status_value = data.get("status") if isinstance(data, dict) else None
    video_url = data.get("url") or data.get("video_url") or data.get("videoUrl") if isinstance(data, dict) else None

    if status_value in {"completed", "succeeded", "success"}:
        return {"headers": {}, "raw": data, "status": "success", "videoUrl": video_url}
    if status_value in {"failed", "cancelled", "canceled", "error"}:
        return {"error": data.get("error") if isinstance(data, dict) else None, "raw": data, "status": "failed"}

    return {"raw": data, "status": "processing"}
