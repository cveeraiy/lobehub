from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import webapi


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(api_base="http://comfyui.test", extra_kwargs={"auth_headers": {"X-Test": "1"}})


def test_build_comfyui_checkpoint_workflow_text_to_image():
    workflow = webapi._build_comfyui_checkpoint_workflow(
        {
            "cfg": 6.5,
            "height": 768,
            "prompt": "a clean product render",
            "samplerName": "dpmpp_2m",
            "scheduler": "karras",
            "seed": 123,
            "steps": 25,
            "width": 1024,
        },
        "sd_xl_base_1.0.safetensors",
    )

    assert workflow["1"]["inputs"]["ckpt_name"] == "sd_xl_base_1.0.safetensors"
    assert workflow["2"]["inputs"]["text"] == "a clean product render"
    assert workflow["4"]["class_type"] == "EmptyLatentImage"
    assert workflow["4"]["inputs"] == {"batch_size": 1, "height": 768, "width": 1024}
    assert workflow["5"]["inputs"]["latent_image"] == ["4", 0]
    assert workflow["5"]["inputs"]["seed"] == 123
    assert workflow["7"]["class_type"] == "SaveImage"


def test_build_comfyui_checkpoint_workflow_image_to_image():
    workflow = webapi._build_comfyui_checkpoint_workflow(
        {
            "imageUrl": "input.png",
            "prompt": "make it brighter",
            "strength": 0.42,
        },
        "v1-5-pruned.safetensors",
    )

    assert "4" not in workflow
    assert workflow["8"]["class_type"] == "LoadImage"
    assert workflow["8"]["inputs"]["image"] == "input.png"
    assert workflow["9"]["class_type"] == "VAEEncode"
    assert workflow["5"]["inputs"]["latent_image"] == ["9", 0]
    assert workflow["5"]["inputs"]["denoise"] == 0.42


async def test_resolve_comfyui_workflow_accepts_json_string():
    workflow = await webapi._resolve_comfyui_workflow(
        {"workflow": '{"1":{"class_type":"SaveImage","inputs":{}}}'},
        _runtime(),
    )

    assert workflow == {"1": {"class_type": "SaveImage", "inputs": {}}}


async def test_resolve_comfyui_checkpoint_uses_available_candidate(monkeypatch):
    async def fake_available(runtime):
        return ["other.safetensors", "sd_xl_base_1.0.safetensors"]

    monkeypatch.setattr(webapi, "_available_comfyui_checkpoints", fake_available)

    checkpoint = await webapi._resolve_comfyui_checkpoint(_runtime(), "comfyui/stable-diffusion-xl")

    assert checkpoint == "sd_xl_base_1.0.safetensors"


async def test_resolve_comfyui_checkpoint_reports_unavailable(monkeypatch):
    async def fake_available(runtime):
        return ["other.safetensors"]

    monkeypatch.setattr(webapi, "_available_comfyui_checkpoints", fake_available)

    with pytest.raises(HTTPException) as exc_info:
        await webapi._resolve_comfyui_checkpoint(_runtime(), "comfyui/stable-diffusion-xl")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["model"] == "stable-diffusion-xl"
