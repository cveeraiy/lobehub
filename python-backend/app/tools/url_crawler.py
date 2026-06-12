"""URL crawler builtin tool — fetch and extract readable content from a URL."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools._http import get_client
from app.tools._safety import validate_url
from app.tools.registry import register

logger = logging.getLogger(__name__)


@register(
    "url_crawler",
    description="Fetch and extract readable text content from a URL.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_length": {
                "type": "integer",
                "description": "Max content chars (default 8000)",
                "default": 8000,
            },
        },
        "required": ["url"],
    },
)
async def url_crawler(arguments: dict[str, Any]) -> str:
    url = arguments.get("url", "")
    if not url:
        return json.dumps({"error": "url is required"})

    # SSRF protection: block private IPs, allow http for public sites
    valid, err = validate_url(url, allow_http=True)
    if not valid:
        return json.dumps({"error": f"Blocked URL: {err}"})

    max_length = arguments.get("max_length", 8000)

    try:
        client = get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        if "text/html" in content_type:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove script/style/nav elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            # Try to get article or main content
            main = soup.find("article") or soup.find("main") or soup.find("body")
            if main:
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else ""
                text = main.get_text(separator="\n", strip=True)
            else:
                title = ""
                text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            if len(text) > max_length:
                text = text[:max_length] + "\n\n[... content truncated]"

            return json.dumps({
                "url": url,
                "title": title,
                "content": text,
                "content_type": "html",
                "length": len(text),
            })
        else:
            # Non-HTML: return raw text
            text = resp.text[:max_length]
            return json.dumps({
                "url": url,
                "title": "",
                "content": text,
                "content_type": content_type.split(";")[0],
                "length": len(text),
            })

    except Exception as exc:
        logger.error("URL crawl failed for %s: %s", url, exc, exc_info=True)
        return json.dumps({"error": f"Failed to fetch URL: {exc}"})
