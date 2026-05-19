"""Provider-specific runtime helpers for /webapi compatibility."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import ai_infra_service
from app.services import llm_service
from app.services.key_vault import KeyVaultService


OPENAI_COMPAT_BASE_URLS: dict[str, str] = {
    "ai21": "https://api.ai21.com/studio/v1",
    "ai302": "https://api.302.ai/v1",
    "ai360": "https://api.360.cn/v1",
    "akashchat": "https://chatapi.akash.network/api/v1",
    "baichuan": "https://api.baichuan-ai.com/v1",
    "bailiancodingplan": "https://coding.dashscope.aliyuncs.com/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "cohere": "https://api.cohere.ai/compatibility/v1",
    "cometapi": "https://api.cometapi.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "fireworksai": "https://api.fireworks.ai/inference/v1",
    "giteeai": "https://ai.gitee.com/v1",
    "github": "https://models.github.ai/inference",
    "glmcodingplan": "https://open.bigmodel.cn/api/coding/paas/v4",
    "groq": "https://api.groq.com/openai/v1",
    "infiniai": "https://cloud.infini-ai.com/maas/v1",
    "internlm": "https://chat.intern-ai.org.cn/api/v1",
    "jina": "https://deepsearch.jina.ai/v1",
    "kimicodingplan": "https://kimi.moonshot.cn/api/coding/kimi-k2/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "longcat": "https://api.longcat.chat/openai/v1",
    "minimax": "https://api.minimaxi.com/v1",
    "minimaxcodingplan": "https://api.minimaxi.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "modelscope": "https://api-inference.modelscope.cn/v1",
    "nebius": "https://api.studio.nebius.com/v1",
    "novita": "https://api.novita.ai/v3/openai",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "ollamacloud": "https://ollama.com/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "perplexity": "https://api.perplexity.ai",
    "ppio": "https://api.ppinfra.com/v3/openai",
    "qiniu": "https://openai.qiniu.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "sambanova": "https://api.sambanova.ai/v1",
    "search1api": "https://api.search1api.com/v1",
    "sensenova": "https://api.sensenova.cn/compatible-mode/v2",
    "siliconcloud": "https://api.siliconflow.cn/v1",
    "stepfun": "https://api.stepfun.com/v1",
    "tencentcloud": "https://api.lkeap.cloud.tencent.com/v1",
    "togetherai": "https://api.together.xyz/v1",
    "upstage": "https://api.upstage.ai/v1/solar",
    "v0": "https://api.v0.dev/v1",
    "vercelaigateway": "https://ai-gateway.vercel.sh/v1",
    "vllm": "http://localhost:8000/v1",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
    "volcenginecodingplan": "https://ark.cn-beijing.volces.com/api/coding/v3",
    "xai": "https://api.x.ai/v1",
    "xiaomimimo": "https://api.xiaomimimo.com/v1",
    "xinference": "http://localhost:9997/v1",
    "zeroone": "https://api.lingyiwanwu.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}

LITELLM_PREFIXES: dict[str, str] = {
    "anthropic": "anthropic",
    "bedrock": "bedrock",
    "cohere": "cohere",
    "deepseek": "deepseek",
    "fireworksai": "fireworks_ai",
    "google": "gemini",
    "groq": "groq",
    "mistral": "mistral",
    "ollamacloud": "openai",
    "openai": "openai",
    "openrouter": "openrouter",
    "perplexity": "perplexity",
    "qwen": "hosted_vllm",
    "togetherai": "together_ai",
    "vertexai": "vertex_ai",
    "xai": "xai",
}

ENV_KEY_BY_PROVIDER: dict[str, str] = {
    "azure": "AZURE_API_KEY",
    "azureai": "AZUREAI_ENDPOINT_KEY",
    "bedrock": "AWS_SECRET_ACCESS_KEY",
    "cloudflare": "CLOUDFLARE_API_KEY",
    "giteeai": "GITEE_AI_API_KEY",
    "github": "GITHUB_TOKEN",
    "githubcopilot": "GITHUB_COPILOT_API_KEY",
    "ollamacloud": "OLLAMA_CLOUD_API_KEY",
    "openai": "OPENAI_API_KEY",
    "tencentcloud": "TENCENT_CLOUD_API_KEY",
    "vertexai": "VERTEXAI_CREDENTIALS",
}

BEDROCK_FALLBACK_MODELS: list[dict[str, Any]] = [
    {
        "abilities": {
            "functionCall": True,
            "reasoning": True,
            "structuredOutput": True,
            "vision": True,
        },
        "contextWindowTokens": 1_000_000,
        "displayName": "Claude Opus 4.7",
        "enabled": True,
        "id": "global.anthropic.claude-opus-4-7",
        "releasedAt": "2026-04-16",
        "type": "chat",
    },
    {
        "abilities": {
            "functionCall": True,
            "reasoning": True,
            "structuredOutput": True,
            "vision": True,
        },
        "contextWindowTokens": 1_000_000,
        "displayName": "Claude Sonnet 4.6",
        "enabled": True,
        "id": "global.anthropic.claude-sonnet-4-6",
        "releasedAt": "2026-02-17",
        "type": "chat",
    },
    {
        "abilities": {
            "functionCall": True,
            "reasoning": True,
            "structuredOutput": True,
            "vision": True,
        },
        "contextWindowTokens": 1_000_000,
        "displayName": "Claude Sonnet 4.5",
        "enabled": True,
        "id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "releasedAt": "2025-09-29",
        "type": "chat",
    },
    {
        "abilities": {
            "functionCall": True,
            "reasoning": True,
            "structuredOutput": True,
            "vision": True,
        },
        "contextWindowTokens": 200_000,
        "displayName": "Claude Sonnet 4",
        "enabled": False,
        "id": "global.anthropic.claude-sonnet-4-20250514-v1:0",
        "releasedAt": "2025-05-14",
        "type": "chat",
    },
    {
        "abilities": {
            "functionCall": True,
            "reasoning": True,
            "structuredOutput": True,
            "vision": True,
        },
        "contextWindowTokens": 200_000,
        "displayName": "Claude 3.7 Sonnet",
        "enabled": True,
        "id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "releasedAt": "2025-02-19",
        "type": "chat",
    },
    {
        "abilities": {"functionCall": True, "vision": True},
        "contextWindowTokens": 200_000,
        "displayName": "Claude 3.5 Sonnet",
        "id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "releasedAt": "2024-10-22",
        "type": "chat",
    },
    {
        "abilities": {"functionCall": True, "vision": True},
        "contextWindowTokens": 200_000,
        "displayName": "Claude 3 Haiku",
        "id": "anthropic.claude-3-haiku-20240307-v1:0",
        "releasedAt": "2024-03-07",
        "type": "chat",
    },
    {
        "abilities": {"functionCall": True},
        "contextWindowTokens": 128_000,
        "displayName": "Llama 3.3 70B Instruct",
        "id": "us.meta.llama3-3-70b-instruct-v1:0",
        "type": "chat",
    },
    {
        "abilities": {"functionCall": True},
        "contextWindowTokens": 8000,
        "displayName": "Llama 3 70B Instruct",
        "id": "meta.llama3-70b-instruct-v1:0",
        "type": "chat",
    },
]


@dataclass
class ProviderRuntimeConfig:
    provider: str
    runtime_provider: str
    key_vaults: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    extra_kwargs: dict[str, Any] = field(default_factory=dict)


def get_vault() -> KeyVaultService | None:
    try:
        return KeyVaultService.from_env()
    except RuntimeError:
        return None


def resolve_runtime_provider(provider: str, settings: dict[str, Any] | None = None) -> str:
    return (settings or {}).get("sdkType") or provider


async def resolve_provider_config(
    session: AsyncSession,
    user_id: str,
    provider: str,
) -> ProviderRuntimeConfig:
    detail = await ai_infra_service.get_provider_detail(session, user_id, provider, get_vault())
    key_vaults = (detail or {}).get("key_vaults") or {}
    settings = (detail or {}).get("settings") or {}
    config = (detail or {}).get("config") or {}
    runtime_provider = resolve_runtime_provider(provider, settings)
    runtime_state = await ai_infra_service.get_runtime_state(session, user_id, get_vault())
    creds = await llm_service.resolve_provider_credentials(
        runtime_state.get("runtimeConfig", {}),
        provider,
    )
    creds.update(_provider_specific_credentials(runtime_provider, key_vaults, config))
    if runtime_provider == "bedrock":
        # The TS runtime derives a synthetic apiKey for Bedrock from AWS keys.
        # LiteLLM expects explicit AWS credential fields instead.
        creds.pop("api_key", None)
        creds.pop("api_base", None)

    return ProviderRuntimeConfig(
        provider=provider,
        runtime_provider=runtime_provider,
        key_vaults=key_vaults,
        settings=settings,
        config=config,
        api_key=creds.get("api_key") or _env_api_key(runtime_provider),
        api_base=creds.get("api_base") or _env_base_url(runtime_provider) or _default_base_url(runtime_provider),
        extra_kwargs={k: v for k, v in creds.items() if k not in {"api_key", "api_base"} and v},
    )


def _env_api_key(provider: str) -> Optional[str]:
    env_key = ENV_KEY_BY_PROVIDER.get(provider) or f"{provider.upper()}_API_KEY"
    return os.getenv(env_key)


def _env_base_url(provider: str) -> Optional[str]:
    candidates = [
        f"{provider.upper()}_PROXY_URL",
        f"{provider.upper()}_BASE_URL",
        f"{provider.upper()}_ENDPOINT",
    ]
    if provider == "azure":
        candidates.append("AZURE_ENDPOINT")
    if provider == "azureai":
        candidates.append("AZUREAI_ENDPOINT")
    if provider == "comfyui":
        candidates.extend(["COMFYUI_BASE_URL", "COMFYUI_DEFAULT_URL"])
    if provider == "ollama":
        candidates.append("OLLAMA_PROXY_URL")
    return next((os.getenv(key) for key in candidates if os.getenv(key)), None)


def _default_base_url(provider: str) -> Optional[str]:
    if provider == "comfyui":
        return "http://localhost:8188"
    if provider == "ollama":
        return os.getenv("OLLAMA_PROXY_URL")
    if provider == "cloudflare":
        return _cloudflare_base_url(os.getenv("CLOUDFLARE_BASE_URL_OR_ACCOUNT_ID"))
    return OPENAI_COMPAT_BASE_URLS.get(provider)


def _provider_specific_credentials(
    provider: str,
    key_vaults: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    creds: dict[str, Any] = {}
    if provider == "azure":
        creds["api_base"] = key_vaults.get("baseURL") or key_vaults.get("endpoint") or os.getenv("AZURE_ENDPOINT")
        creds["api_version"] = (
            key_vaults.get("apiVersion")
            or config.get("apiVersion")
            or os.getenv("AZURE_API_VERSION")
        )
    elif provider == "azureai":
        creds["api_base"] = key_vaults.get("baseURL") or os.getenv("AZUREAI_ENDPOINT")
    elif provider == "bedrock":
        mapping = {
            "accessKeyId": "aws_access_key_id",
            "secretAccessKey": "aws_secret_access_key",
            "sessionToken": "aws_session_token",
            "region": "aws_region_name",
        }
        for source_key, target_key in mapping.items():
            if key_vaults.get(source_key):
                creds[target_key] = key_vaults[source_key]
        creds.setdefault("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID"))
        creds.setdefault("aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY"))
        creds.setdefault("aws_session_token", os.getenv("AWS_SESSION_TOKEN"))
        creds.setdefault("aws_region_name", os.getenv("AWS_REGION"))
    elif provider == "cloudflare":
        account_or_url = key_vaults.get("baseURLOrAccountID") or os.getenv("CLOUDFLARE_BASE_URL_OR_ACCOUNT_ID")
        creds["cloudflare_account_or_url"] = account_or_url
        creds["api_base"] = _cloudflare_base_url(account_or_url)
    elif provider == "comfyui":
        creds["api_base"] = key_vaults.get("baseURL") or _env_base_url("comfyui") or "http://localhost:8188"
        creds["auth_headers"] = comfyui_auth_headers(key_vaults)
    elif provider == "githubcopilot":
        creds["bearer_token"] = key_vaults.get("bearerToken")
        creds["oauth_access_token"] = key_vaults.get("oauthAccessToken")
        creds["bearer_token_expires_at"] = key_vaults.get("bearerTokenExpiresAt")
    elif provider == "ollama":
        creds["api_base"] = key_vaults.get("baseURL") or _env_base_url("ollama")
    elif provider == "vertexai":
        creds["vertex_credentials"] = key_vaults.get("apiKey") or os.getenv("VERTEXAI_CREDENTIALS")
        creds["vertex_region"] = key_vaults.get("region") or os.getenv("VERTEXAI_LOCATION")
        creds["vertex_project"] = config.get("project") or os.getenv("VERTEXAI_PROJECT")
    return creds


def _cloudflare_base_url(account_or_url: Optional[str]) -> Optional[str]:
    if not account_or_url:
        return None
    if account_or_url.startswith("http"):
        return account_or_url if account_or_url.endswith("/") else f"{account_or_url}/"
    return f"https://api.cloudflare.com/client/v4/accounts/{account_or_url}/ai/run/"


def model_for_litellm(runtime: ProviderRuntimeConfig, model: str) -> str:
    if "/" in model:
        return model
    if runtime.runtime_provider == "azure":
        return f"azure/{model}"
    if runtime.runtime_provider == "ollama":
        return f"ollama/{model}"
    if runtime.runtime_provider == "bedrock":
        model = _bedrock_inference_profile_model_id(model)
    prefix = LITELLM_PREFIXES.get(runtime.runtime_provider)
    if prefix:
        return f"{prefix}/{model}"
    if runtime.api_base:
        return f"openai/{model}"
    return model


def _bedrock_inference_profile_model_id(model: str) -> str:
    if model.startswith(("global.", "us.", "eu.", "apac.")):
        return model
    if model.startswith(
        (
            "anthropic.claude-sonnet-4",
            "anthropic.claude-opus-4",
            "anthropic.claude-haiku-4",
        )
    ):
        return f"global.{model}"
    if model.startswith("anthropic.claude-3-7-sonnet"):
        return f"us.{model}"
    return model


def chat_extra_kwargs(runtime: ProviderRuntimeConfig, body: dict[str, Any]) -> dict[str, Any]:
    ignored = {
        "apiMode",
        "deploymentName",
        "frequency_penalty",
        "max_tokens",
        "messages",
        "model",
        "presence_penalty",
        "provider",
        "stream",
        "temperature",
        "top_p",
    }
    extra = {k: v for k, v in body.items() if k not in ignored and v is not None}
    extra.update(runtime.extra_kwargs)
    if body.get("top_p") is not None:
        extra["top_p"] = body["top_p"]
    if runtime.runtime_provider == "bedrock":
        # Bedrock models do not support OpenAI penalty params. Let LiteLLM
        # drop any other provider-specific unsupported OpenAI params instead
        # of failing connectivity checks and normal chat requests.
        extra["drop_params"] = True
        return extra
    if body.get("presence_penalty") is not None:
        extra["presence_penalty"] = body["presence_penalty"]
    if body.get("frequency_penalty") is not None:
        extra["frequency_penalty"] = body["frequency_penalty"]
    return extra


async def list_remote_models(runtime: ProviderRuntimeConfig) -> list[dict[str, Any]] | None:
    if runtime.runtime_provider == "bedrock":
        return await _list_bedrock_models(runtime)
    if runtime.runtime_provider == "ollama":
        return await _list_ollama_models(runtime)
    if runtime.runtime_provider == "cloudflare":
        return await _list_cloudflare_models(runtime)
    if runtime.runtime_provider == "comfyui":
        return await _list_comfyui_models(runtime)
    if runtime.api_base and runtime.api_key:
        return await _list_openai_compatible_models(runtime)
    return None


async def _list_bedrock_models(runtime: ProviderRuntimeConfig) -> list[dict[str, Any]]:
    region = runtime.extra_kwargs.get("aws_region_name") or os.getenv("AWS_REGION") or "us-east-1"

    client_kwargs = {
        "aws_access_key_id": runtime.extra_kwargs.get("aws_access_key_id"),
        "aws_secret_access_key": runtime.extra_kwargs.get("aws_secret_access_key"),
        "aws_session_token": runtime.extra_kwargs.get("aws_session_token"),
        "region_name": region,
    }
    client_kwargs = {key: value for key, value in client_kwargs.items() if value}

    def list_models() -> list[dict[str, Any]]:
        client = boto3.client("bedrock", **client_kwargs)
        summaries = client.list_foundation_models().get("modelSummaries", [])
        inference_profile_by_model = _bedrock_inference_profile_map(client, region)
        return [
            _bedrock_model_card(summary, inference_profile_by_model.get(summary.get("modelId")))
            for summary in summaries
            if summary.get("modelId")
        ]

    try:
        models = await asyncio.to_thread(list_models)
        return models or BEDROCK_FALLBACK_MODELS
    except (BotoCoreError, ClientError):
        return BEDROCK_FALLBACK_MODELS


def _bedrock_inference_profile_map(client: Any, region: str) -> dict[str, str]:
    try:
        profiles = client.list_inference_profiles().get("inferenceProfileSummaries", [])
    except (BotoCoreError, ClientError, AttributeError):
        return {}

    candidates: dict[str, list[str]] = {}
    for profile in profiles:
        profile_id = profile.get("inferenceProfileId")
        if not profile_id:
            continue
        for model in profile.get("models") or []:
            model_arn = model.get("modelArn") or ""
            model_id = model_arn.rsplit("/", 1)[-1]
            if model_id:
                candidates.setdefault(model_id, []).append(profile_id)

    region_prefix = region.split("-", 1)[0]
    return {
        model_id: sorted(
            profile_ids,
            key=lambda profile_id: (
                0 if profile_id.startswith("global.") else 1,
                0 if profile_id.startswith(f"{region_prefix}.") else 1,
                profile_id,
            ),
        )[0]
        for model_id, profile_ids in candidates.items()
    }


def _bedrock_model_card(summary: dict[str, Any], inference_profile_id: str | None = None) -> dict[str, Any]:
    model_id = summary.get("modelId")
    input_modalities = set(summary.get("inputModalities") or [])
    output_modalities = set(summary.get("outputModalities") or [])
    display_name = summary.get("modelName") or model_id
    provider_name = summary.get("providerName")
    model_lifecycle = summary.get("modelLifecycle") or {}
    is_legacy = model_lifecycle.get("status") == "LEGACY"

    model_type = "chat"
    if "EMBEDDING" in output_modalities:
        model_type = "embedding"
    elif "IMAGE" in output_modalities and "TEXT" not in output_modalities:
        model_type = "image"

    return {
        "abilities": {
            "functionCall": provider_name == "Anthropic",
            "vision": "IMAGE" in input_modalities,
        },
        "displayName": display_name,
        "enabled": not is_legacy,
        "id": inference_profile_id or model_id,
        "type": model_type,
    }


async def _list_openai_compatible_models(runtime: ProviderRuntimeConfig) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"{runtime.api_base.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {runtime.api_key}"},
        )
    res.raise_for_status()
    data = res.json()
    models = data.get("data", data if isinstance(data, list) else [])
    return [_model_card(item.get("id") if isinstance(item, dict) else str(item)) for item in models]


async def _list_ollama_models(runtime: ProviderRuntimeConfig) -> list[dict[str, Any]]:
    if not runtime.api_base:
        return []
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f"{runtime.api_base.rstrip('/')}/api/tags")
    res.raise_for_status()
    data = res.json()
    return [_model_card(item.get("name")) for item in data.get("models", []) if item.get("name")]


async def _list_cloudflare_models(runtime: ProviderRuntimeConfig) -> list[dict[str, Any]]:
    account_or_url = runtime.extra_kwargs.get("cloudflare_account_or_url")
    if not account_or_url or str(account_or_url).startswith("http") or not runtime.api_key:
        return []
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_or_url}/ai/models/search"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, headers={"Authorization": f"Bearer {runtime.api_key}"})
    res.raise_for_status()
    data = res.json()
    return [_model_card(item.get("name")) for item in data.get("result", []) if item.get("name")]


async def _list_comfyui_models(runtime: ProviderRuntimeConfig) -> list[dict[str, Any]]:
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
    return [_model_card(f"comfyui/{name}", model_type="image") for name in names]


def _model_card(model_id: str, model_type: str = "chat") -> dict[str, Any]:
    return {
        "abilities": {},
        "displayName": model_id,
        "enabled": True,
        "id": model_id,
        "type": model_type,
    }


async def stream_ollama_pull(
    runtime: ProviderRuntimeConfig,
    model: str,
    insecure: bool = False,
) -> AsyncIterator[bytes]:
    if not runtime.api_base:
        raise ValueError("Ollama baseURL is required")
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{runtime.api_base.rstrip('/')}/api/pull",
            json={"insecure": insecure, "model": model, "stream": True},
        ) as res:
            res.raise_for_status()
            async for chunk in res.aiter_bytes():
                yield chunk


def comfyui_auth_headers(options: dict[str, Any]) -> dict[str, str]:
    auth_type = options.get("authType") or os.getenv("COMFYUI_AUTH_TYPE") or "none"
    api_key = options.get("apiKey") or os.getenv("COMFYUI_API_KEY")
    username = options.get("username") or os.getenv("COMFYUI_USERNAME")
    password = options.get("password") or os.getenv("COMFYUI_PASSWORD")
    custom_headers = options.get("customHeaders") or _json_env("COMFYUI_CUSTOM_HEADERS")
    if auth_type == "basic" and username and password:
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    if auth_type == "bearer" and api_key:
        return {"Authorization": f"Bearer {api_key}"}
    if auth_type == "custom" and isinstance(custom_headers, dict):
        return {str(k): str(v) for k, v in custom_headers.items()}
    return {}


def _json_env(key: str) -> Any:
    value = os.getenv(key)
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None
