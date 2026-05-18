"""Provider-specific runtime helpers for /webapi compatibility."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx
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
    prefix = LITELLM_PREFIXES.get(runtime.runtime_provider)
    if prefix:
        return f"{prefix}/{model}"
    if runtime.api_base:
        return f"openai/{model}"
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
    if body.get("presence_penalty") is not None:
        extra["presence_penalty"] = body["presence_penalty"]
    if body.get("frequency_penalty") is not None:
        extra["frequency_penalty"] = body["frequency_penalty"]
    return extra


async def list_remote_models(runtime: ProviderRuntimeConfig) -> list[dict[str, Any]] | None:
    if runtime.runtime_provider == "ollama":
        return await _list_ollama_models(runtime)
    if runtime.runtime_provider == "cloudflare":
        return await _list_cloudflare_models(runtime)
    if runtime.runtime_provider == "comfyui":
        return await _list_comfyui_models(runtime)
    if runtime.api_base and runtime.api_key:
        return await _list_openai_compatible_models(runtime)
    return None


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
