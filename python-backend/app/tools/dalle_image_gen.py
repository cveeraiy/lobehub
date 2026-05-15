"""DALL-E image generation builtin tool."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.tools._http import get_client
from app.tools.registry import register

logger = logging.getLogger(__name__)


@register(
    "dalle_image_gen",
    description="Generate an image using OpenAI DALL-E. Returns image URL(s).",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Image description prompt"},
            "model": {
                "type": "string",
                "description": "DALL-E model (default: dall-e-3)",
                "default": "dall-e-3",
            },
            "size": {
                "type": "string",
                "description": "Image size",
                "enum": ["1024x1024", "1024x1792", "1792x1024"],
                "default": "1024x1024",
            },
            "quality": {
                "type": "string",
                "description": "Image quality",
                "enum": ["standard", "hd"],
                "default": "standard",
            },
            "n": {
                "type": "integer",
                "description": "Number of images (default 1)",
                "default": 1,
            },
        },
        "required": ["prompt"],
    },
)
async def dalle_image_gen(arguments: dict[str, Any]) -> str:
    prompt = arguments.get("prompt", "")
    if not prompt:
        return json.dumps({"error": "prompt is required"})

    model = arguments.get("model", "dall-e-3")
    size = arguments.get("size", "1024x1024")
    quality = arguments.get("quality", "standard")
    n = arguments.get("n", 1)

    api_key = settings.openai_api_key
    if not api_key:
        return json.dumps({"error": "OPENAI_API_KEY not configured"})

    base_url = settings.openai_proxy_url or "https://api.openai.com/v1"

    try:
        client = get_client()
        resp = await client.post(
            f"{base_url}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "prompt": prompt,
                "n": n,
                "size": size,
                "quality": quality,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        images = []
        for item in data.get("data", []):
            images.append({
                "url": item.get("url", ""),
                "revised_prompt": item.get("revised_prompt", ""),
            })

        return json.dumps({
            "prompt": prompt,
            "model": model,
            "images": images,
        })

    except Exception as exc:
        logger.error("DALL-E generation failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Image generation failed: {exc}"})
