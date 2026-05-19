import pytest

from app.services import provider_runtime
from app.services.provider_runtime import (
    ProviderRuntimeConfig,
    chat_extra_kwargs,
    list_remote_models,
    model_for_litellm,
)


def test_chat_extra_kwargs_drops_openai_penalties_for_bedrock():
    runtime = ProviderRuntimeConfig(
        provider="bedrock",
        runtime_provider="bedrock",
        extra_kwargs={
            "aws_access_key_id": "access",
            "aws_region_name": "us-east-1",
            "aws_secret_access_key": "secret",
        },
    )

    kwargs = chat_extra_kwargs(
        runtime,
        {
            "frequency_penalty": 0,
            "messages": [{"content": "hello", "role": "user"}],
            "model": "anthropic.claude-instant-v1",
            "presence_penalty": 0,
            "provider": "bedrock",
            "stream": False,
            "temperature": 0.5,
            "top_p": 0.9,
        },
    )

    assert "presence_penalty" not in kwargs
    assert "frequency_penalty" not in kwargs
    assert kwargs["drop_params"] is True
    assert kwargs["top_p"] == 0.9
    assert kwargs["aws_access_key_id"] == "access"
    assert kwargs["aws_secret_access_key"] == "secret"
    assert kwargs["aws_region_name"] == "us-east-1"


def test_chat_extra_kwargs_keeps_openai_penalties_for_non_bedrock():
    runtime = ProviderRuntimeConfig(provider="openai", runtime_provider="openai")

    kwargs = chat_extra_kwargs(
        runtime,
        {
            "frequency_penalty": 0.2,
            "messages": [{"content": "hello", "role": "user"}],
            "model": "gpt-4o-mini",
            "presence_penalty": 0.1,
            "provider": "openai",
            "stream": False,
        },
    )

    assert kwargs["presence_penalty"] == 0.1
    assert kwargs["frequency_penalty"] == 0.2
    assert "drop_params" not in kwargs


def test_model_for_litellm_uses_bedrock_inference_profile_for_claude_4():
    runtime = ProviderRuntimeConfig(provider="bedrock", runtime_provider="bedrock")

    model = model_for_litellm(runtime, "anthropic.claude-sonnet-4-20250514-v1:0")

    assert model == "bedrock/global.anthropic.claude-sonnet-4-20250514-v1:0"


@pytest.mark.asyncio
async def test_list_remote_models_returns_bedrock_models(monkeypatch):
    class FakeBedrockClient:
        def list_foundation_models(self):
            return {
                "modelSummaries": [
                    {
                        "inputModalities": ["TEXT", "IMAGE"],
                        "modelId": "anthropic.claude-sonnet-test-v1:0",
                        "modelName": "Claude Test",
                        "outputModalities": ["TEXT"],
                        "providerName": "Anthropic",
                    },
                    {
                        "inputModalities": ["TEXT"],
                        "modelId": "amazon.titan-embed-text-test-v1:0",
                        "modelName": "Titan Embed Test",
                        "outputModalities": ["EMBEDDING"],
                        "providerName": "Amazon",
                    }
                ]
            }

        def list_inference_profiles(self):
            return {
                "inferenceProfileSummaries": [
                    {
                        "inferenceProfileId": "us.anthropic.claude-sonnet-test-v1:0",
                        "models": [
                            {
                                "modelArn": (
                                    "arn:aws:bedrock:us-east-1::foundation-model/"
                                    "anthropic.claude-sonnet-test-v1:0"
                                )
                            }
                        ],
                    },
                    {
                        "inferenceProfileId": "global.anthropic.claude-sonnet-test-v1:0",
                        "models": [
                            {
                                "modelArn": (
                                    "arn:aws:bedrock:us-east-1::foundation-model/"
                                    "anthropic.claude-sonnet-test-v1:0"
                                )
                            }
                        ],
                    },
                ]
            }

    def fake_client(service_name, **kwargs):
        assert service_name == "bedrock"
        assert kwargs["aws_access_key_id"] == "access"
        assert kwargs["aws_secret_access_key"] == "secret"
        assert kwargs["region_name"] == "us-east-1"
        return FakeBedrockClient()

    monkeypatch.setattr(provider_runtime.boto3, "client", fake_client)

    models = await list_remote_models(
        ProviderRuntimeConfig(
            provider="bedrock",
            runtime_provider="bedrock",
            extra_kwargs={
                "aws_access_key_id": "access",
                "aws_region_name": "us-east-1",
                "aws_secret_access_key": "secret",
            },
        )
    )

    assert models == [
        {
            "abilities": {
                "functionCall": True,
                "vision": True,
            },
            "displayName": "Claude Test",
            "enabled": True,
            "id": "global.anthropic.claude-sonnet-test-v1:0",
            "type": "chat",
        },
        {
            "abilities": {
                "functionCall": False,
                "vision": False,
            },
            "displayName": "Titan Embed Test",
            "enabled": True,
            "id": "amazon.titan-embed-text-test-v1:0",
            "type": "embedding",
        }
    ]


@pytest.mark.asyncio
async def test_list_remote_models_falls_back_for_bedrock_errors(monkeypatch):
    def fake_client(*_args, **_kwargs):
        raise provider_runtime.BotoCoreError(error_msg="no local aws config")

    monkeypatch.setattr(provider_runtime.boto3, "client", fake_client)

    models = await list_remote_models(
        ProviderRuntimeConfig(provider="bedrock", runtime_provider="bedrock")
    )

    assert models
    assert models[0]["id"].startswith("global.anthropic.")
