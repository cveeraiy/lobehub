"""Task Template Service — reusable task templates with daily recommendations.

Ports TS ``taskTemplate/index.ts``:
- Seeded-shuffle daily recommendations based on user interests
- Skill-source eligibility filtering
- Fallback category filling
- Pure-function deterministic PRNG (mulberry32)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

RECOMMEND_COUNT = 3

# Fallback categories used when interest-matched templates are insufficient
FALLBACK_CATEGORIES = ["productivity", "research", "writing"]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class SkillRequirement:
    """Skill source required by a template."""
    source: str  # e.g. "web_search", "code_interpreter"


@dataclass
class TaskTemplate:
    """A reusable task template."""
    id: str
    name: str
    description: str
    category: str
    instruction: str
    interests: list[str] = field(default_factory=list)
    requires_skills: list[SkillRequirement] = field(default_factory=list)
    priority: int = 0
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helpers (stateless, deterministic)
# ---------------------------------------------------------------------------

def _hash_string(s: str) -> int:
    """Simple string hash matching the TS implementation."""
    h = 0
    for ch in s:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    return h


def _mulberry32(seed: int):
    """Mulberry32 PRNG — pure function of seed, same output as TS version."""
    t = seed & 0xFFFFFFFF

    def _next() -> float:
        nonlocal t
        t = (t + 0x6D2B79F5) & 0xFFFFFFFF
        r = t
        r = ((r ^ (r >> 15)) * (1 | r)) & 0xFFFFFFFF
        r = (r + (((r ^ (r >> 7)) * (61 | r)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        r = (r ^ (r >> 14)) & 0xFFFFFFFF
        return r / 4_294_967_296

    return _next


def _seeded_shuffle(items: list, seed: int) -> list:
    """Fisher-Yates shuffle with seeded PRNG."""
    arr = list(items)
    rand = _mulberry32(seed)
    for i in range(len(arr) - 1, 0, -1):
        j = int(rand() * (i + 1))
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def _normalize(s: str) -> str:
    return s.strip().lower()


def _has_intersection(template: TaskTemplate, user_interests: list[str]) -> bool:
    if not user_interests:
        return False
    normalized = {_normalize(i) for i in user_interests}
    return any(_normalize(i) in normalized for i in template.interests)


def _get_utc_date_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")


def is_template_skill_source_eligible(
    template: TaskTemplate,
    enabled_skill_sources: Optional[set[str]] = None,
) -> bool:
    """A template is eligible only if every required skill source is enabled.

    When a template has no skill requirements, it is always eligible.
    When the caller passes no enabled_skill_sources, any template with
    requirements is filtered out (conservative default).
    """
    if not template.requires_skills:
        return True
    if enabled_skill_sources is None:
        return False
    return all(s.source in enabled_skill_sources for s in template.requires_skills)


# ---------------------------------------------------------------------------
# Built-in templates registry (extensible)
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: list[TaskTemplate] = []


def register_template(template: TaskTemplate) -> None:
    """Add a template to the builtin registry."""
    _BUILTIN_TEMPLATES.append(template)


def get_all_templates() -> list[TaskTemplate]:
    """Return all registered templates."""
    return list(_BUILTIN_TEMPLATES)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TaskTemplateService:
    """Service for task template recommendations."""

    def __init__(self, user_id: str) -> None:
        self._uid = user_id

    def list_daily_recommend(
        self,
        interest_keys: list[str],
        *,
        enabled_skill_sources: Optional[set[str]] = None,
        exclude_ids: Optional[list[str]] = None,
        date_str: Optional[str] = None,
        templates: Optional[list[TaskTemplate]] = None,
    ) -> list[TaskTemplate]:
        """Return up to RECOMMEND_COUNT daily recommended templates.

        Recommendations are seeded by user_id + date so they stay stable
        within a single day but rotate daily.

        Args:
            interest_keys: User's interest area keys.
            enabled_skill_sources: Set of enabled skill source names.
            exclude_ids: Template IDs to exclude (e.g. already used).
            date_str: Override UTC date string for testing.
            templates: Override template list for testing.
        """
        all_templates = templates if templates is not None else _BUILTIN_TEMPLATES
        date = date_str or _get_utc_date_str()
        excluded = set(exclude_ids or [])
        seed = _hash_string(f"{self._uid}:{date}")

        # Filter eligible candidates
        candidates = [
            t for t in all_templates
            if t.id not in excluded
            and is_template_skill_source_eligible(t, enabled_skill_sources)
        ]

        # Phase 1: interest-matched
        matched = [t for t in candidates if _has_intersection(t, interest_keys)]
        result = _seeded_shuffle(matched, seed)[:RECOMMEND_COUNT]

        # Phase 2: fill from fallback categories
        if len(result) < RECOMMEND_COUNT:
            seen = {t.id for t in result}
            fallback_pool = [
                t for t in candidates
                if t.id not in seen and t.category in FALLBACK_CATEGORIES
            ]
            remaining = _seeded_shuffle(fallback_pool, seed)[: RECOMMEND_COUNT - len(result)]
            result.extend(remaining)

        # Phase 3: fill from any remaining candidate
        if len(result) < RECOMMEND_COUNT:
            seen = {t.id for t in result}
            any_pool = [t for t in candidates if t.id not in seen]
            remaining = _seeded_shuffle(any_pool, seed)[: RECOMMEND_COUNT - len(result)]
            result.extend(remaining)

        return result

    def list_all(
        self,
        *,
        category: Optional[str] = None,
        templates: Optional[list[TaskTemplate]] = None,
    ) -> list[TaskTemplate]:
        """List all templates, optionally filtered by category."""
        all_templates = templates if templates is not None else _BUILTIN_TEMPLATES
        if category:
            return [t for t in all_templates if t.category == category]
        return list(all_templates)

    def get_by_id(
        self,
        template_id: str,
        *,
        templates: Optional[list[TaskTemplate]] = None,
    ) -> Optional[TaskTemplate]:
        """Look up a template by ID."""
        all_templates = templates if templates is not None else _BUILTIN_TEMPLATES
        for t in all_templates:
            if t.id == template_id:
                return t
        return None
