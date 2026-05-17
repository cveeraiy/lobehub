"""MCP content-block processor.

Handles rich content returned by MCP tool calls:
- **Image** blocks: decode base64 → upload to S3 → replace data with proxy URL
- **Audio** blocks: decode base64 → upload to S3 → replace data with proxy URL
- **Text / Resource** blocks: pass through

Also provides ``content_blocks_to_string`` to flatten blocks into a single
markdown-friendly string for the LLM.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Content block → string ───────────────────────────────────────────

def content_blocks_to_string(blocks: Optional[list[dict[str, Any]]]) -> str:
    """Convert MCP content blocks to a single string.

    - text  → extract ``text`` field
    - image → ``![](url)``
    - audio → ``<resource type="audio" url="..." />``
    - resource → ``<resource type="resource">json</resource>``
    """
    if not blocks:
        return ""

    parts: list[str] = []
    for item in blocks:
        block_type = item.get("type", "")

        if block_type == "text":
            text = item.get("text", "")
            if text:
                parts.append(text)

        elif block_type == "image":
            data = item.get("data", "")
            if data:
                parts.append(f"![]({data})")

        elif block_type == "audio":
            data = item.get("data", "")
            if data:
                parts.append(f'<resource type="audio" url="{data}" />')

        elif block_type == "resource":
            resource = item.get("resource")
            if resource:
                parts.append(f'<resource type="resource">{json.dumps(resource)}</resource>')

    return "\n\n".join(parts)


# ── Upload helpers ───────────────────────────────────────────────────

async def process_content_blocks(
    blocks: list[dict[str, Any]],
    s3_client: Any,
    *,
    s3_file_prefix: str = "files",
) -> list[dict[str, Any]]:
    """Process MCP content blocks, uploading binary data to S3.

    Parameters
    ----------
    blocks:
        The ``content`` array from an MCP tool call result.
    s3_client:
        An ``S3Client`` instance (from ``app.services.file_service``).
    s3_file_prefix:
        Path prefix inside the S3 bucket.

    Returns
    -------
    A new list of blocks with image/audio data replaced by S3 URLs.
    """
    today = date.today().isoformat()  # e.g. "2025-05-14"
    result: list[dict[str, Any]] = []

    for block in blocks:
        block_type = block.get("type", "")

        if block_type == "image":
            url = await _upload_base64_block(
                block, s3_client, s3_file_prefix, today, "images",
            )
            result.append({**block, "data": url})

        elif block_type == "audio":
            url = await _upload_base64_block(
                block, s3_client, s3_file_prefix, today, "audio",
            )
            result.append({**block, "data": url})

        else:
            result.append(block)

    return result


async def _upload_base64_block(
    block: dict[str, Any],
    s3_client: Any,
    prefix: str,
    today: str,
    category: str,
) -> str:
    """Decode a base64 block and upload to S3, returning the key or URL."""
    raw_data = block.get("data", "")
    mime_type = block.get("mimeType", f"{category}/{'png' if category == 'images' else 'mp3'}")
    ext = mime_type.split("/")[-1] if "/" in mime_type else "bin"

    key = f"{prefix}/mcp/{category}/{today}/{uuid.uuid4().hex}.{ext}"

    try:
        decoded = base64.b64decode(raw_data)
        s3_client.upload_bytes(key, decoded, mime_type)
        logger.info("Uploaded MCP %s block to %s", category, key)

        # If the S3 client exposes a public domain, build a full URL
        public_domain = getattr(s3_client, "_public_domain", None)
        if public_domain:
            return f"{public_domain.rstrip('/')}/{key}"
        return key
    except Exception as exc:
        logger.error("Failed to upload MCP %s block: %s", category, exc)
        # Return original data on failure so the LLM still gets something
        return raw_data
