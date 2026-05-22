"""Hono /webapi compatibility routes for AI provider runtime calls."""

from __future__ import annotations

import ipaddress
import json
import logging
import random
import socket
from html import escape
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user_id
from app.services import ai_infra_service as ai_svc
from app.services import llm_service, provider_runtime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webapi", tags=["WebAPI"])

COMFYUI_DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, normal quality, low quality, low res, blurry, distortion, "
    "text, watermark, logo, bad anatomy, bad proportions, deformed"
)

COMFYUI_MODEL_ID_CANDIDATES: dict[str, list[str]] = {
    "flux-dev": ["flux1-dev.safetensors"],
    "flux-krea-dev": ["flux1-krea-dev.safetensors"],
    "flux-kontext-dev": ["flux1-kontext-dev.safetensors"],
    "flux-schnell": ["flux1-schnell.safetensors"],
    "stable-diffusion-15": [
        "v1-5-pruned-emaonly.safetensors",
        "v1-5-pruned.safetensors",
        "v1-5-pruned-emaonly.ckpt",
    ],
    "stable-diffusion-35": [
        "sd3.5_large.safetensors",
        "sd3.5_large_fp8_scaled.safetensors",
        "sd3.5_medium.safetensors",
    ],
    "stable-diffusion-35-inclclip": ["sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors"],
    "stable-diffusion-custom": ["custom_sd_lobe.safetensors"],
    "stable-diffusion-custom-refiner": ["custom_sd_lobe.safetensors"],
    "stable-diffusion-refiner": ["sd_xl_refiner_1.0.safetensors"],
    "stable-diffusion-xl": ["sd_xl_base_1.0.safetensors"],
}


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return str(value)


def _sse(data: Any) -> str:
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(_jsonable(data), separators=(',', ':'))}\n\n"


def _get_field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _event_sse(event: str, data: Any, event_id: str | None = None) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(_jsonable(data), separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def _usage_payload(usage: Any) -> dict[str, Any]:
    if isinstance(usage, dict):
        return {
            "input_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
            "output_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
    return {
        "input_tokens": getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _chunk_events(chunk: Any) -> list[str]:
    """Convert LiteLLM/OpenAI stream chunks into Lobe frontend SSE events."""
    event_id = _get_field(chunk, "id")
    events: list[str] = []

    choices = _get_field(chunk, "choices") or []
    for choice in choices:
        delta = _get_field(choice, "delta") or {}
        content = _get_field(delta, "content")
        if content:
            events.append(_event_sse("text", content, event_id))

        reasoning = _get_field(delta, "reasoning_content")
        if reasoning:
            events.append(_event_sse("reasoning", reasoning, event_id))

        tool_calls = _get_field(delta, "tool_calls")
        if tool_calls:
            events.append(_event_sse("tool_calls", _jsonable(tool_calls), event_id))

        finish_reason = _get_field(choice, "finish_reason")
        if finish_reason:
            events.append(_event_sse("stop", finish_reason, event_id))

    usage = _get_field(chunk, "usage")
    if usage:
        events.append(_event_sse("usage", _usage_payload(usage), event_id))

    if not events and isinstance(chunk, str):
        events.append(_event_sse("text", chunk, event_id))

    return events


def _error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            data = exc.response.json()
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict) and error.get("message"):
                    return str(error["message"])
                if data.get("message"):
                    return str(data["message"])
                if data.get("detail"):
                    return str(data["detail"])
        except Exception:
            pass
        if exc.response.text:
            return exc.response.text

    message = getattr(exc, "message", None) or str(exc)
    return str(message) if message else exc.__class__.__name__


def _int_body(body: dict[str, Any], *keys: str, default: int) -> int:
    for key in keys:
        value = body.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            break
    return default


def _float_body(body: dict[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        value = body.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            break
    return default


def _clean_comfyui_model_id(model: str | None) -> str:
    if not model:
        return "stable-diffusion-xl"
    return model.removeprefix("comfyui/").strip()


async def _available_comfyui_checkpoints(runtime: provider_runtime.ProviderRuntimeConfig) -> list[str]:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"{runtime.api_base.rstrip('/')}/object_info/CheckpointLoaderSimple",
            headers=runtime.extra_kwargs.get("auth_headers") or {},
        )
    res.raise_for_status()
    data = res.json()
    names = (
        data.get("CheckpointLoaderSimple", {})
        .get("input", {})
        .get("required", {})
        .get("ckpt_name", [[]])[0]
    )
    return [str(name) for name in names] if isinstance(names, list) else []


async def _resolve_comfyui_checkpoint(
    runtime: provider_runtime.ProviderRuntimeConfig,
    model: str | None,
) -> str:
    clean_model = _clean_comfyui_model_id(model)
    if clean_model.endswith((".safetensors", ".ckpt", ".pt", ".pth", ".bin")):
        return clean_model

    candidates = COMFYUI_MODEL_ID_CANDIDATES.get(clean_model, [clean_model])
    try:
        available = await _available_comfyui_checkpoints(runtime)
    except Exception:
        available = []
    if not available:
        return candidates[0]
    for candidate in candidates:
        if candidate in available:
            return candidate
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        {
            "error": "ComfyUI model not available",
            "model": clean_model,
            "expected": candidates,
            "available": available[:50],
        },
    )


def _build_comfyui_checkpoint_workflow(body: dict[str, Any], checkpoint_name: str) -> dict[str, Any]:
    prompt = str(body.get("prompt") or body.get("positive") or "")
    if not prompt:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "prompt is required")

    image_urls = body.get("imageUrls") or body.get("image_urls") or []
    if not isinstance(image_urls, list):
        image_urls = []
    image_url = body.get("imageUrl") or body.get("image_url") or (image_urls[0] if image_urls else None)
    is_i2i = bool(image_url)

    width = _int_body(body, "width", default=1024)
    height = _int_body(body, "height", default=1024)
    steps = _int_body(body, "steps", default=20)
    cfg = _float_body(body, "cfg", "guidance", "guidanceScale", "guidance_scale", default=7.0)
    seed = _int_body(body, "seed", default=random.randint(0, 2**31 - 1))
    sampler_name = str(body.get("samplerName") or body.get("sampler_name") or "euler")
    scheduler = str(body.get("scheduler") or "normal")
    denoise = _float_body(body, "strength", "denoise", default=0.75 if is_i2i else 1.0)
    negative_prompt = str(body.get("negativePrompt") or body.get("negative_prompt") or COMFYUI_DEFAULT_NEGATIVE_PROMPT)

    workflow: dict[str, Any] = {
        "1": {
            "_meta": {"title": "Load Checkpoint"},
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        "2": {
            "_meta": {"title": "Positive Prompt"},
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": prompt},
        },
        "3": {
            "_meta": {"title": "Negative Prompt"},
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 1], "text": negative_prompt},
        },
        "5": {
            "_meta": {"title": "KSampler"},
            "class_type": "KSampler",
            "inputs": {
                "cfg": cfg,
                "denoise": denoise,
                "latent_image": ["9", 0] if is_i2i else ["4", 0],
                "model": ["1", 0],
                "negative": ["3", 0],
                "positive": ["2", 0],
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "seed": seed,
                "steps": steps,
            },
        },
        "6": {
            "_meta": {"title": "VAE Decode"},
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "_meta": {"title": "Save Image"},
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "Ethos/Python_ComfyUI", "images": ["6", 0]},
        },
    }
    if is_i2i:
        workflow["8"] = {
            "_meta": {"title": "Load Input Image"},
            "class_type": "LoadImage",
            "inputs": {"image": str(image_url)},
        }
        workflow["9"] = {
            "_meta": {"title": "VAE Encode Input"},
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["8", 0], "vae": ["1", 2]},
        }
    else:
        workflow["4"] = {
            "_meta": {"title": "Empty Latent"},
            "class_type": "EmptyLatentImage",
            "inputs": {"batch_size": 1, "height": height, "width": width},
        }
    return workflow


async def _resolve_comfyui_workflow(
    body: dict[str, Any],
    runtime: provider_runtime.ProviderRuntimeConfig,
) -> dict[str, Any]:
    workflow = body.get("workflow")
    if workflow is None and isinstance(body.get("prompt"), dict):
        workflow = body["prompt"]
    if workflow is not None:
        if isinstance(workflow, str):
            try:
                workflow = json.loads(workflow)
            except json.JSONDecodeError as exc:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "workflow must be valid JSON") from exc
        if not isinstance(workflow, dict):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "workflow must be a ComfyUI prompt object")
        return workflow

    checkpoint_name = await _resolve_comfyui_checkpoint(runtime, body.get("model"))
    return _build_comfyui_checkpoint_workflow(body, checkpoint_name)


def _classify_provider_error(provider: str, exc: Exception) -> tuple[str, int]:
    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    message = _error_message(exc).lower()
    provider_id = provider.lower()

    if provider_id == "bedrock" and any(
        text in message
        for text in (
            "access key",
            "secret access key",
            "secret key",
            "credentials",
            "authentication",
            "invalid api key format",
            "security token",
        )
    ):
        return "InvalidBedrockCredentials", status.HTTP_401_UNAUTHORIZED

    if status_code in {401, 403} or any(
        text in message
        for text in (
            "api key",
            "apikey",
            "authentication",
            "authorization",
            "unauthorized",
            "forbidden",
            "credentials",
            "access key",
            "secret key",
            "invalid key",
        )
    ):
        return "InvalidProviderAPIKey", status.HTTP_401_UNAUTHORIZED

    if status_code == 404 or ("model" in message and "not found" in message):
        return "ModelNotFound", status.HTTP_404_NOT_FOUND

    if provider_id in {"ollama", "lmstudio"} and any(
        text in message
        for text in (
            "all connection attempts failed",
            "connection refused",
            "connect error",
            "connecterror",
            "service unavailable",
        )
    ):
        return "OllamaServiceUnavailable", 472

    return "ProviderBizError", 471


def _provider_error_payload(provider: str, exc: Exception) -> tuple[dict[str, Any], int]:
    error_type, status_code = _classify_provider_error(provider, exc)
    message = _error_message(exc)
    body = {
        "error": {
            "message": message,
            "name": exc.__class__.__name__,
        },
        "message": message,
        "provider": provider,
    }
    return {
        "body": body,
        "errorType": error_type,
        "message": message,
        "provider": provider,
        "type": error_type,
    }, status_code


async def _stream_openai_chunks(provider: str, chunks: AsyncIterator[Any]) -> AsyncIterator[str]:
    try:
        async for chunk in chunks:
            for event in _chunk_events(chunk):
                yield event
    except Exception as exc:
        payload, _ = _provider_error_payload(provider, exc)
        logger.warning(
            "Route: [%s] %s: %s",
            provider,
            payload["type"],
            exc,
            exc_info=exc.__traceback__ is not None,
        )
        yield "event: error\n"
        yield _sse(
            {
                "body": payload["body"],
                "message": payload["message"],
                "type": payload["type"],
            },
        )


def _provider_error(provider: str, exc: Exception) -> JSONResponse:
    payload, status_code = _provider_error_payload(provider, exc)
    log = logger.warning if payload["type"] != "ProviderBizError" else logger.error
    log(
        "Route: [%s] %s: %s",
        provider,
        payload["type"],
        exc,
        exc_info=exc.__traceback__ is not None,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload,
    )


@router.post("/chat/{provider}")
async def chat_completion(
    provider: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    body = await request.json()
    model = body.get("model")
    messages = body.get("messages")
    if not model or not messages:
        raise HTTPException(status_code=400, detail="model and messages are required")

    try:
        runtime = await provider_runtime.resolve_provider_config(session, user_id, provider)
        response = await llm_service.chat(
            messages,
            model=provider_runtime.model_for_litellm(runtime, model),
            stream=body.get("stream", True),
            temperature=body.get("temperature"),
            max_tokens=body.get("max_tokens"),
            api_key=runtime.api_key,
            api_base=runtime.api_base,
            extra_kwargs=provider_runtime.chat_extra_kwargs(runtime, body),
        )
        if body.get("stream", True):
            return StreamingResponse(
                _stream_openai_chunks(provider, response),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        return JSONResponse(_jsonable(response))
    except Exception as exc:
        return _provider_error(provider, exc)


@router.get("/models/{provider}")
async def list_provider_models(
    provider: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    try:
        runtime = await provider_runtime.resolve_provider_config(session, user_id, provider)
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
    except Exception as exc:
        return _provider_error(provider, exc)


@router.post("/models/{provider}/pull")
async def pull_provider_model(
    provider: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    body = await request.json()
    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="model is required")

    runtime = await provider_runtime.resolve_provider_config(session, user_id, provider)
    if runtime.runtime_provider != "ollama":
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content={"error": "Model pull is only implemented for Ollama providers."},
        )

    async def stream() -> AsyncIterator[bytes]:
        async for chunk in provider_runtime.stream_ollama_pull(
            runtime,
            model,
            bool(body.get("insecure")),
        ):
            yield chunk

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.post("/tts/openai")
async def openai_tts(request: Request):
    payload = await request.json()
    options = payload.get("options") or {}
    api_key = (
        payload.get("apiKey")
        or options.get("apiKey")
        or request.headers.get("x-openai-api-key")
        or settings.openai_api_key
    )
    if not api_key:
        raise HTTPException(status_code=401, detail="OpenAI API key is required")

    body = {
        "input": payload.get("input") or payload.get("text") or payload.get("content"),
        "model": payload.get("model") or options.get("model") or payload.get("ttsModel") or "tts-1",
        "voice": payload.get("voice") or options.get("voice") or "alloy",
    }
    if payload.get("response_format"):
        body["response_format"] = payload["response_format"]

    base_url = (
        payload.get("baseURL")
        or options.get("baseURL")
        or request.headers.get("x-openai-end-point")
        or settings.openai_proxy_url
        or "https://api.openai.com/v1"
    ).rstrip("/")
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(
            f"{base_url}/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        )
    return Response(
        content=res.content,
        media_type=res.headers.get("content-type", "audio/mpeg"),
        status_code=res.status_code,
    )


@router.post("/tts/edge")
async def edge_tts(request: Request):
    try:
        import edge_tts
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="edge-tts dependency is not installed. Run uv sync in python-backend.",
        ) from exc

    payload = await request.json()
    options = payload.get("options") or {}
    text = payload.get("input") or payload.get("text") or payload.get("content")
    if not text:
        raise HTTPException(status_code=400, detail="input text is required")
    voice = payload.get("voice") or options.get("voice") or "en-US-AriaNeural"
    communicate = edge_tts.Communicate(str(text), voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return Response(content=b"".join(chunks), media_type="audio/mpeg")


@router.post("/tts/microsoft")
async def microsoft_tts(request: Request):
    payload = await request.json()
    options = payload.get("options") or {}
    text = payload.get("input") or payload.get("text") or payload.get("content")
    if not text:
        raise HTTPException(status_code=400, detail="input text is required")

    api_key = (
        payload.get("apiKey")
        or options.get("apiKey")
        or request.headers.get("x-microsoft-speech-key")
        or request.headers.get("ocp-apim-subscription-key")
    )
    region = payload.get("region") or options.get("region") or request.headers.get("x-microsoft-speech-region")
    if not api_key or not region:
        raise HTTPException(status_code=401, detail="Microsoft speech key and region are required")

    voice = payload.get("voice") or options.get("voice") or "en-US-JennyNeural"
    output_format = options.get("outputFormat") or "audio-24khz-48kbitrate-mono-mp3"
    ssml = (
        "<speak version='1.0' xml:lang='en-US'>"
        f"<voice xml:lang='en-US' name='{escape(str(voice), quote=True)}'>"
        f"{escape(str(text))}</voice>"
        "</speak>"
    )
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            content=ssml.encode("utf-8"),
            headers={
                "Content-Type": "application/ssml+xml",
                "Ocp-Apim-Subscription-Key": api_key,
                "User-Agent": "lobehub-python-backend",
                "X-Microsoft-OutputFormat": output_format,
            },
        )
    return Response(
        content=res.content,
        media_type=res.headers.get("content-type", "audio/mpeg"),
        status_code=res.status_code,
    )


@router.post("/stt/openai")
async def openai_stt(
    request: Request,
    speech: UploadFile = File(...),
    options: str = Form(...),
):
    parsed_options = json.loads(options)
    api_key = (
        parsed_options.get("apiKey")
        or request.headers.get("x-openai-api-key")
        or settings.openai_api_key
    )
    if not api_key:
        raise HTTPException(status_code=401, detail="OpenAI API key is required")

    audio = await speech.read()
    model = parsed_options.get("model") or "whisper-1"
    data = {"model": model}
    if parsed_options.get("language") and parsed_options["language"] != "auto":
        data["language"] = parsed_options["language"]

    base_url = (
        parsed_options.get("baseURL")
        or request.headers.get("x-openai-end-point")
        or settings.openai_proxy_url
        or "https://api.openai.com/v1"
    ).rstrip("/")
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(
            f"{base_url}/audio/transcriptions",
            data=data,
            files={
                "file": (
                    speech.filename or "speech.webm",
                    audio,
                    speech.content_type or "audio/webm",
                ),
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
    return Response(
        content=res.content,
        media_type=res.headers.get("content-type", "application/json"),
        status_code=res.status_code,
    )


def _is_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return False
    return True


@router.post("/proxy")
async def proxy(request: Request):
    url = (await request.body()).decode("utf-8").strip()
    if not _is_public_url(url):
        return JSONResponse(status_code=400, content={"error": "Not support internal host proxy"})
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        res = await client.get(url)
    headers = {
        key: value
        for key, value in res.headers.items()
        if key.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
    }
    return Response(content=res.content, status_code=res.status_code, headers=headers)


@router.post("/trace", status_code=status.HTTP_201_CREATED)
async def trace_event():
    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/create-image/comfyui")
async def create_image_comfyui(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    body = await request.json()
    runtime = await provider_runtime.resolve_provider_config(session, user_id, "comfyui")
    workflow = await _resolve_comfyui_workflow(body, runtime)
    client_id = body.get("clientId") or body.get("client_id") or f"python-{user_id}"
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(
            f"{runtime.api_base.rstrip('/')}/prompt",
            json={"client_id": client_id, "prompt": workflow},
            headers=runtime.extra_kwargs.get("auth_headers") or {},
        )
    if not res.is_success:
        return Response(
            content=res.content,
            media_type=res.headers.get("content-type", "application/json"),
            status_code=res.status_code,
        )
    return res.json()
