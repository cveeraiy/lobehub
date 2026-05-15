"""Lobe Agent server runtime tool — visual media analysis.

Ports TS ``serverRuntimes/lobeAgent.ts``:
- analyzeVisualMedia: Analyze images/videos using a vision-capable model

Simplified version — does not include the full ref-based visual file
resolution from message history. Supports URL-based visual analysis.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

LOBE_AGENT_IDENTIFIER = "lobehub_lobe_agent"


async def lobe_agent_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    **kwargs: Any,
) -> str:
    """Lobe Agent tool — visual media analysis."""
    from app.config import settings

    if api_name == "analyzeVisualMedia":
        question = arguments.get("question")
        urls = arguments.get("urls", [])

        if not question:
            return json.dumps({
                "success": False,
                "content": "question is required.",
                "error": {"code": "INVALID_ARGUMENTS", "message": "question is required."},
            })

        if not urls:
            return json.dumps({
                "success": False,
                "content": "At least one URL is required.",
                "error": {"code": "INVALID_ARGUMENTS", "message": "At least one URL is required."},
            })

        # Validate URLs
        valid_urls = []
        for url in urls:
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                valid_urls.append(url)

        if not valid_urls:
            return json.dumps({
                "success": False,
                "content": "No valid URLs provided.",
                "error": {"code": "UNSUPPORTED_VISUAL_MEDIA_URLS", "message": "No valid URLs."},
            })

        # Build vision message content
        content_parts: list[dict[str, Any]] = []
        for url in valid_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url},
            })
        content_parts.append({
            "type": "text",
            "text": question,
        })

        # Use configured visual model or default
        model = getattr(settings, "visual_understanding_model", None) or "openai/gpt-4o"
        provider = getattr(settings, "visual_understanding_provider", None)

        model_str = f"{provider}/{model}" if provider and "/" not in model else model

        try:
            from app.services import llm_service

            response = await llm_service.chat(
                [{"role": "user", "content": content_parts}],
                model=model_str,
                stream=False,
                max_tokens=2000,
            )

            result_content = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
            }

            return json.dumps({
                "success": True,
                "content": result_content.strip(),
                "state": {
                    "model": model_str,
                    "trigger": "lobe-agent.analyzeVisualMedia",
                    "files": [{"type": "image", "url": u} for u in valid_urls],
                    "usage": usage,
                },
            })

        except Exception as exc:
            logger.error("analyzeVisualMedia failed: %s", exc)
            return json.dumps({
                "success": False,
                "content": f"Visual analysis failed: {exc}",
                "error": {"code": "VISUAL_ANALYSIS_FAILED", "message": str(exc)},
            })

    return json.dumps({"error": f"Unknown lobeAgent API: {api_name}"})


@register(
    LOBE_AGENT_IDENTIFIER,
    description="Lobe Agent — analyze visual media (images, videos) using vision models. "
                "APIs: analyzeVisualMedia.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "enum": ["analyzeVisualMedia"],
            },
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def lobe_agent_tool_stub(args: dict[str, Any]) -> str:
    return json.dumps({"error": "LobeAgent tool requires server context (session + user_id)."})


register_context_handler(LOBE_AGENT_IDENTIFIER, lobe_agent_with_context)
