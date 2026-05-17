"""Skill store builtin tool — search marketplace, import skills."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.tools._http import get_client
from app.tools._safety import escape_like, get_skill_import_allowlist, validate_url
from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

LOBEHUB_MARKET_URL = "https://chat-agents.lobehub.com"


# ── Context-aware implementations ────────────────────────────────────


async def skill_store_with_context(
    api_name: str,
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Skill store — search marketplace, import skills from URL/GitHub/market."""
    if api_name == "searchSkill":
        keyword = arguments.get("keyword", "")
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 10)

        try:
            client = get_client()
            resp = await client.get(
                f"{LOBEHUB_MARKET_URL}/api/skill/search",
                params={"q": keyword, "page": page, "pageSize": page_size},
            )
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({
                    "items": data.get("items", data.get("skills", [])),
                    "total": data.get("total", data.get("totalCount", 0)),
                    "page": page,
                    "page_size": page_size,
                })
            return await _local_skill_search(session, user_id, keyword, page_size)
        except Exception:
            logger.warning("Market search failed, falling back to local", exc_info=True)
            return await _local_skill_search(session, user_id, keyword, page_size)

    if api_name == "importFromUrl":
        url = arguments.get("url", "")
        if not url:
            return json.dumps({"error": "url is required"})
        valid, err = validate_url(url, domain_allowlist=get_skill_import_allowlist())
        if not valid:
            return json.dumps({"error": f"Blocked URL: {err}"})
        return await _import_skill_from_url(session, user_id, url)

    if api_name == "importFromGitHub":
        git_url = arguments.get("git_url", "")
        if not git_url:
            return json.dumps({"error": "git_url is required"})

        raw_url = _github_to_raw_manifest(git_url)
        if not raw_url:
            return json.dumps({"error": f"Cannot resolve manifest from: {git_url}"})
        valid, err = validate_url(raw_url, domain_allowlist=get_skill_import_allowlist())
        if not valid:
            return json.dumps({"error": f"Blocked URL: {err}"})
        return await _import_skill_from_url(session, user_id, raw_url)

    if api_name == "importFromMarket":
        identifier = arguments.get("identifier", "")
        if not identifier:
            return json.dumps({"error": "identifier is required"})

        download_url = f"{LOBEHUB_MARKET_URL}/api/skill/download/{identifier}"
        # Marketplace URL is trusted — skip full validation
        return await _import_skill_from_url(session, user_id, download_url)

    return json.dumps({"error": f"Unknown skill_store API: {api_name}"})


# ── Helpers ──────────────────────────────────────────────────────────


def _github_to_raw_manifest(git_url: str) -> str | None:
    """Convert a GitHub URL to a raw manifest.json URL."""
    import re as _re

    m = _re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$", git_url)
    if m:
        owner, repo = m.group(1), m.group(2)
        return f"https://raw.githubusercontent.com/{owner}/{repo}/main/manifest.json"
    return None


async def _import_skill_from_url(session: Any, user_id: str, url: str) -> str:
    """Fetch a skill manifest from a URL and create an AgentSkill record."""
    from sqlalchemy import and_, select
    from app.models.skill import AgentSkill

    try:
        client = get_client()
        resp = await client.get(url)
        resp.raise_for_status()

        data = resp.json()
        manifest = data if isinstance(data, dict) else {}

        identifier = manifest.get("identifier") or manifest.get("name", "").lower().replace(" ", "-")
        if not identifier:
            return json.dumps({"error": "Manifest missing 'identifier' or 'name'"})

        # Check if already exists
        stmt = select(AgentSkill).where(
            and_(AgentSkill.identifier == identifier, AgentSkill.user_id == user_id)
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            return json.dumps({
                "status": "already_exists",
                "skill": {"id": existing.id, "name": existing.display_name},
            })

        name = manifest.get("name") or manifest.get("meta", {}).get("title", identifier)
        description = (
            manifest.get("description")
            or manifest.get("meta", {}).get("description", "")
        )

        skill = AgentSkill(
            identifier=identifier,
            user_id=user_id,
            display_name=name,
            description=description,
            avatar=manifest.get("meta", {}).get("avatar"),
            manifest=manifest,
        )
        session.add(skill)
        await session.flush()

        return json.dumps({
            "status": "imported",
            "skill": {"id": skill.id, "name": name, "identifier": identifier},
        })

    except Exception as exc:
        logger.error("Skill import failed from %s: %s", url, exc, exc_info=True)
        return json.dumps({"error": f"Import failed: {exc}"})


async def _local_skill_search(session: Any, user_id: str, keyword: str, limit: int) -> str:
    """Fallback: search user's installed skills locally."""
    from sqlalchemy import and_, desc, select
    from app.models.skill import AgentSkill

    escaped = escape_like(keyword)
    pattern = f"%{escaped}%"
    stmt = (
        select(AgentSkill)
        .where(
            and_(
                AgentSkill.user_id == user_id,
                (
                    AgentSkill.display_name.ilike(pattern, escape="\\")
                    | AgentSkill.description.ilike(pattern, escape="\\")
                ),
            )
        )
        .order_by(desc(AgentSkill.updated_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    items = [
        {
            "identifier": s.identifier,
            "name": s.display_name,
            "description": s.description,
            "source": "local",
        }
        for s in rows
    ]
    return json.dumps({"items": items, "total": len(items), "source": "local"})


# ── Dispatcher for double-underscore routing ─────────────────────────


async def _skill_store_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    return await skill_store_with_context(api_name, arguments, session, user_id)


# ── Registered tools (stubs) ────────────────────────────────────────


@register(
    "skill_store__searchSkill",
    description="Search the Ethos skill marketplace for skills to install.",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Search keyword"},
            "page": {"type": "integer", "description": "Page number (default 1)", "default": 1},
            "page_size": {"type": "integer", "description": "Results per page (default 10)", "default": 10},
        },
        "required": ["keyword"],
    },
)
async def _search_skill_stub(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skill_store requires DB context"})


@register(
    "skill_store__importFromUrl",
    description="Import a skill from a URL pointing to a skill manifest JSON.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to the skill manifest JSON"},
        },
        "required": ["url"],
    },
)
async def _import_url_stub(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skill_store requires DB context"})


@register(
    "skill_store__importFromGitHub",
    description="Import a skill from a GitHub repository (fetches manifest.json from main branch).",
    parameters={
        "type": "object",
        "properties": {
            "git_url": {"type": "string", "description": "GitHub repository URL"},
        },
        "required": ["git_url"],
    },
)
async def _import_github_stub(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skill_store requires DB context"})


@register(
    "skill_store__importFromMarket",
    description="Import a skill from the Ethos marketplace by its identifier.",
    parameters={
        "type": "object",
        "properties": {
            "identifier": {"type": "string", "description": "Marketplace skill identifier"},
        },
        "required": ["identifier"],
    },
)
async def _import_market_stub(arguments: dict[str, Any]) -> str:
    return json.dumps({"error": "skill_store requires DB context"})


# Register context handlers
for _api in ("searchSkill", "importFromUrl", "importFromGitHub", "importFromMarket"):
    register_context_handler(f"skill_store__{_api}", _skill_store_context_dispatch)
