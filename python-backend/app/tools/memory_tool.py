"""Memory builtin tool — search and store user memories from within a chat.

Supports 5-layer memory model: event, semantic, episodic, procedural, persona.
Context-aware handlers use embedding-based vector search and auto-embedding storage.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.tools.registry import register, register_context_handler

logger = logging.getLogger(__name__)

MEMORY_IDENTIFIER = "lobe-user-memory"
MEMORY_APIS = [
    "addActivityMemory",
    "addContextMemory",
    "addExperienceMemory",
    "addIdentityMemory",
    "addPreferenceMemory",
    "queryTaxonomyOptions",
    "removeIdentityMemory",
    "searchUserMemory",
    "updateIdentityMemory",
]

MEMORY_LAYER_KEYS = {
    "activity": "activities",
    "context": "contexts",
    "experience": "experiences",
    "identity": "identities",
    "preference": "preferences",
}
MEMORY_KEYS = list(MEMORY_LAYER_KEYS.values())


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _success(content: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"content": content, "success": True}
    if state is not None:
        result["state"] = state
    return result


def _failure(content: str) -> dict[str, Any]:
    return {"content": content, "success": False}


def _read_only(arguments: dict[str, Any]) -> bool:
    return arguments.get("toolPermission") == "read-only"


def _get(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _format_date(value: Any) -> Any:
    if not value:
        return value
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value


def _append_attr(attrs: list[str], name: str, value: Any, *, quoted: bool = True) -> None:
    if value is None:
        return
    if value == "":
        return
    attrs.append(f'{name}="{value}"' if quoted else f"{name}={value}")


def _format_named_refs(items: list[dict[str, Any]] | None) -> str:
    refs = []
    for item in items or []:
        name = item.get("name")
        if not name:
            continue
        ref_type = item.get("type")
        refs.append(f"{name} ({ref_type})" if ref_type else name)
    return ", ".join(refs)


def _format_context_result(item: dict[str, Any]) -> str:
    attrs = [f'id="{item.get("id") or ""}"']
    _append_attr(attrs, "title", item.get("title"))
    _append_attr(attrs, "urgency", _get(item, "scoreUrgency", "score_urgency"), quoted=False)
    _append_attr(attrs, "impact", _get(item, "scoreImpact", "score_impact"), quoted=False)
    _append_attr(attrs, "type", item.get("type"))
    _append_attr(attrs, "status", _get(item, "currentStatus", "current_status"))

    children = []
    if item.get("description"):
        children.append(f"    {item['description']}")
    subjects = _format_named_refs(_get(item, "associatedSubjects", "associated_subjects"))
    if subjects:
        children.append(f"    <subjects>{subjects}</subjects>")
    objects = _format_named_refs(_get(item, "associatedObjects", "associated_objects"))
    if objects:
        children.append(f"    <objects>{objects}</objects>")

    children_xml = "\n".join(children)
    content = f"\n{children_xml}\n  " if children else ""
    return f"  <context {' '.join(attrs)}>{content}</context>"


def _format_activity_result(item: dict[str, Any]) -> str:
    attrs = [f'id="{item.get("id") or ""}"']
    _append_attr(attrs, "type", item.get("type"))
    _append_attr(attrs, "status", item.get("status"))
    _append_attr(attrs, "startsAt", _format_date(_get(item, "startsAt", "starts_at")))
    _append_attr(attrs, "endsAt", _format_date(_get(item, "endsAt", "ends_at")))
    _append_attr(attrs, "timezone", item.get("timezone"))

    children = []
    if item.get("feedback"):
        children.append(f"    <feedback>{item['feedback']}</feedback>")
    if item.get("narrative"):
        children.append(f"    <narrative>{item['narrative']}</narrative>")
    if item.get("notes"):
        children.append(f"    <notes>{item['notes']}</notes>")

    children_xml = "\n".join(children)
    content = f"\n{children_xml}\n  " if children else ""
    return f"  <activity {' '.join(attrs)}>{content}</activity>"


def _format_experience_result(item: dict[str, Any]) -> str:
    attrs = [f'id="{item.get("id") or ""}"']
    _append_attr(attrs, "type", item.get("type"))
    _append_attr(attrs, "confidence", _get(item, "scoreConfidence", "score_confidence"), quoted=False)

    children = []
    if item.get("situation"):
        children.append(f"    <situation>{item['situation']}</situation>")
    key_learning = _get(item, "keyLearning", "key_learning")
    if key_learning:
        children.append(f"    <keyLearning>{key_learning}</keyLearning>")

    children_xml = "\n".join(children)
    content = f"\n{children_xml}\n  " if children else ""
    return f"  <experience {' '.join(attrs)}>{content}</experience>"


def _format_preference_result(item: dict[str, Any]) -> str:
    attrs = [f'id="{item.get("id") or ""}"']
    _append_attr(attrs, "type", item.get("type"))
    _append_attr(attrs, "priority", _get(item, "scorePriority", "score_priority"), quoted=False)
    return f"  <preference {' '.join(attrs)}>{item.get('conclusionDirectives') or ''}</preference>"


def _format_identity_result(item: dict[str, Any]) -> str:
    attrs = [f'id="{item.get("id") or ""}"']
    _append_attr(attrs, "type", item.get("type"))
    _append_attr(attrs, "relationship", item.get("relationship"))
    _append_attr(attrs, "role", item.get("role"))
    return f"  <identity {' '.join(attrs)}>{item.get('description') or ''}</identity>"


def _format_memory_search_results(query: str, results: dict[str, Any]) -> str:
    activities = results.get("activities") or []
    contexts = results.get("contexts") or []
    experiences = results.get("experiences") or []
    identities = results.get("identities") or []
    preferences = results.get("preferences") or []
    total = len(activities) + len(contexts) + len(experiences) + len(identities) + len(preferences)

    if total == 0:
        return f"""<memories query="{query}">
  <status>No memories found matching the query.</status>
</memories>"""

    sections = []
    if contexts:
        contexts_xml = "\n".join(_format_context_result(item) for item in contexts)
        sections.append(
            f"""<contexts count="{len(contexts)}">
{contexts_xml}
</contexts>"""
        )
    if activities:
        activities_xml = "\n".join(_format_activity_result(item) for item in activities)
        sections.append(
            f"""<activities count="{len(activities)}">
{activities_xml}
</activities>"""
        )
    if experiences:
        experiences_xml = "\n".join(_format_experience_result(item) for item in experiences)
        sections.append(
            f"""<experiences count="{len(experiences)}">
{experiences_xml}
</experiences>"""
        )
    if identities:
        identities_xml = "\n".join(_format_identity_result(item) for item in identities)
        sections.append(
            f"""<identities count="{len(identities)}">
{identities_xml}
</identities>"""
        )
    if preferences:
        preferences_xml = "\n".join(_format_preference_result(item) for item in preferences)
        sections.append(
            f"""<preferences count="{len(preferences)}">
{preferences_xml}
</preferences>"""
        )

    sections_xml = "\n".join(sections)
    return f"""<memories query="{query}" total="{total}">
{sections_xml}
</memories>"""


def _start_of_utc_day(value: datetime) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _end_of_utc_day(value: datetime) -> datetime:
    return datetime(value.year, value.month, value.day, 23, 59, 59, 999000, tzinfo=UTC)


def _add_utc_days(value: datetime, days: int) -> datetime:
    return _start_of_utc_day(value) + timedelta(days=days)


def _start_of_utc_week(value: datetime) -> datetime:
    weekday = value.weekday()
    return _add_utc_days(value, -weekday)


def _start_of_utc_month(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=UTC)


def _end_of_utc_month(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year, 12, 31, 23, 59, 59, 999000, tzinfo=UTC)
    return _start_of_utc_month(year, month + 1) - timedelta(milliseconds=1)


def _start_of_utc_year(year: int) -> datetime:
    return datetime(year, 1, 1, tzinfo=UTC)


def _end_of_utc_year(year: int) -> datetime:
    return datetime(year, 12, 31, 23, 59, 59, 999000, tzinfo=UTC)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _time_range(start: datetime | None, end: datetime | None, field: str = "createdAt") -> dict[str, Any]:
    return {"end": end, "field": field, "start": start}


def _resolve_relative_day_anchor(anchor: Any, now: datetime) -> datetime | None:
    if anchor == "today":
        return now
    if anchor == "yesterday":
        return _add_utc_days(now, -1)
    if isinstance(anchor, dict):
        time_range = _resolve_time_intent(anchor, now)
        return time_range.get("start") or time_range.get("end") if time_range else None
    return None


def _resolve_time_intent(time_intent: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any] | None:
    if not time_intent:
        return None

    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    selector = time_intent.get("selector")

    if selector == "today":
        return _time_range(_start_of_utc_day(now), _end_of_utc_day(now))
    if selector == "yesterday":
        date = _add_utc_days(now, -1)
        return _time_range(_start_of_utc_day(date), _end_of_utc_day(date))
    if selector == "currentWeek":
        start = _start_of_utc_week(now)
        return _time_range(start, _end_of_utc_day(_add_utc_days(start, 6)))
    if selector == "lastWeek":
        start = _add_utc_days(_start_of_utc_week(now), -7)
        return _time_range(start, _end_of_utc_day(_add_utc_days(start, 6)))
    if selector == "lastWeekend":
        current_week_start = _start_of_utc_week(now)
        return _time_range(
            _add_utc_days(current_week_start, -2),
            _end_of_utc_day(_add_utc_days(current_week_start, -1)),
        )
    if selector == "lastWeekdays":
        start = _add_utc_days(_start_of_utc_week(now), -7)
        return _time_range(start, _end_of_utc_day(_add_utc_days(start, 4)))
    if selector == "currentMonth":
        return _time_range(_start_of_utc_month(now.year, now.month), _end_of_utc_month(now.year, now.month))
    if selector == "lastMonth":
        year = now.year if now.month > 1 else now.year - 1
        month = now.month - 1 if now.month > 1 else 12
        return _time_range(_start_of_utc_month(year, month), _end_of_utc_month(year, month))
    if selector == "currentYear":
        return _time_range(_start_of_utc_year(now.year), _end_of_utc_year(now.year))
    if selector == "lastYear":
        year = now.year - 1
        return _time_range(_start_of_utc_year(year), _end_of_utc_year(year))
    if selector == "day":
        date = _parse_datetime(time_intent.get("date"))
        return _time_range(_start_of_utc_day(date), _end_of_utc_day(date)) if date else None
    if selector == "month":
        year = time_intent.get("year")
        month = time_intent.get("month")
        return _time_range(_start_of_utc_month(year, month), _end_of_utc_month(year, month)) if year and month else None
    if selector == "year":
        year = time_intent.get("year")
        return _time_range(_start_of_utc_year(year), _end_of_utc_year(year)) if year else None
    if selector == "relativeDay":
        anchor = _resolve_relative_day_anchor(time_intent.get("anchor"), now)
        if not anchor:
            return None
        date = _add_utc_days(anchor, int(time_intent.get("offsetDays") or 0))
        return _time_range(_start_of_utc_day(date), _end_of_utc_day(date))
    if selector == "range":
        start = _parse_datetime(time_intent.get("start"))
        end = _parse_datetime(time_intent.get("end"))
        return _time_range(_start_of_utc_day(start) if start else None, _end_of_utc_day(end) if end else None)

    return None


def _normalize_search_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(arguments)
    if not normalized.get("timeRange") and normalized.get("timeIntent"):
        normalized["timeRange"] = _resolve_time_intent(normalized.get("timeIntent"))
        normalized["timeIntent"] = None

    layers = normalized.get("layers") or normalized.get("where", {}).get("layers")
    if layers:
        top_k = dict(normalized.get("topK") or {})
        for layer, key in MEMORY_LAYER_KEYS.items():
            if layer not in layers:
                top_k[key] = 0
        normalized["topK"] = top_k

    return normalized


def _as_set(values: Any) -> set[Any]:
    if not values:
        return set()
    if isinstance(values, list):
        return set(values)
    return {values}


def _matches_list_filter(value: Any, allowed: set[Any]) -> bool:
    if not allowed:
        return True
    if isinstance(value, list):
        return bool(allowed.intersection(value))
    return value in allowed


def _time_value(item: dict[str, Any], field: str) -> datetime | None:
    field_map = {
        "capturedAt": ("capturedAt", "captured_at"),
        "createdAt": ("createdAt", "created_at"),
        "endsAt": ("endsAt", "ends_at"),
        "episodicDate": ("episodicDate", "episodic_date"),
        "startsAt": ("startsAt", "starts_at"),
        "updatedAt": ("updatedAt", "updated_at"),
    }
    return _parse_datetime(_get(item, *field_map.get(field, (field,))))


def _matches_time_range(item: dict[str, Any], time_range: dict[str, Any] | None) -> bool:
    if not time_range:
        return True
    value = _time_value(item, time_range.get("field") or "createdAt")
    if not value:
        return True
    start = _parse_datetime(time_range.get("start"))
    end = _parse_datetime(time_range.get("end"))
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


def _matches_search_filters(item: dict[str, Any], arguments: dict[str, Any], layer: str) -> bool:
    if not _matches_list_filter(item.get("tags"), _as_set(arguments.get("tags"))):
        return False
    if not _matches_list_filter(item.get("type"), _as_set(arguments.get("types"))):
        return False
    if layer == "identity" and not _matches_list_filter(
        item.get("relationship"),
        _as_set(arguments.get("relationships")),
    ):
        return False
    if layer in {"activity", "context"} and not _matches_list_filter(
        _get(item, "status", "currentStatus", "current_status"), _as_set(arguments.get("status"))
    ):
        return False
    return _matches_time_range(item, arguments.get("timeRange"))


def _filter_search_result(result: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    layers = set(arguments.get("layers") or arguments.get("where", {}).get("layers") or [])
    filtered = dict(result)
    for layer, key in MEMORY_LAYER_KEYS.items():
        items = list(result.get(key) or [])
        if layers and layer not in layers:
            filtered[key] = []
        else:
            filtered[key] = [item for item in items if _matches_search_filters(item, arguments, layer)]

    meta = dict(result.get("meta") or {})
    layer_meta = dict(meta.get("layers") or {})
    for key in MEMORY_KEYS:
        count = len(filtered.get(key) or [])
        layer_meta[key] = {"hasMore": False, "returned": count, "total": count}
    meta["layers"] = layer_meta
    meta["appliedFilters"] = {
        key: value
        for key, value in arguments.items()
        if key in {"layers", "relationships", "status", "tags", "timeRange", "types"} and value
    }
    filtered["meta"] = meta
    return filtered


async def run_memory_api(
    api_name: str,
    arguments: dict[str, Any],
    *,
    session: Any,
    user_id: str,
) -> dict[str, Any]:
    from app.routers import user_memory

    if api_name == "searchUserMemory":
        normalized_arguments = _normalize_search_arguments(arguments)
        try:
            result = await user_memory.search_memory(
                user_memory.SearchMemoryBody(**normalized_arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"searchUserMemory with error detail: {exc}")

        result = _filter_search_result(result, normalized_arguments)
        queries = [q for q in (normalized_arguments.get("queries") or []) if q]
        query = " | ".join(queries) or "facet-only search"
        safe_result = {key: value for key, value in result.items() if key != "meta"}
        return _success(_format_memory_search_results(query, result), safe_result)

    if api_name == "queryTaxonomyOptions":
        try:
            result = await user_memory.query_taxonomy_options(
                layer=arguments.get("layer"),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"queryTaxonomyOptions with error detail: {exc}")
        return _success(_json(result), result)

    if api_name == "addContextMemory":
        if _read_only(arguments):
            return _failure("Memory tool is in read-only mode for this chat")
        try:
            result = await user_memory.tool_add_context_memory(
                user_memory.ToolAddContextBody(**arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"addContextMemory with error detail: {exc}")
        if not result.get("success"):
            return _failure(result.get("message") or "Failed to save memory")
        return _success(
            f'Context memory "{arguments.get("title")}" saved with memoryId: "{result.get("memoryId")}" '
            f'and contextId: "{result.get("contextId")}"',
            {"contextId": result.get("contextId"), "memoryId": result.get("memoryId")},
        )

    if api_name == "addActivityMemory":
        if _read_only(arguments):
            return _failure("Memory tool is in read-only mode for this chat")
        try:
            result = await user_memory.tool_add_activity_memory(
                user_memory.ToolAddActivityBody(**arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"addActivityMemory with error detail: {exc}")
        if not result.get("success"):
            return _failure(result.get("message") or "Failed to save memory")
        return _success(
            f'Activity memory "{arguments.get("title")}" saved with memoryId: "{result.get("memoryId")}" '
            f'and activityId: "{result.get("activityId")}"',
            {"activityId": result.get("activityId"), "memoryId": result.get("memoryId")},
        )

    if api_name == "addExperienceMemory":
        if _read_only(arguments):
            return _failure("Memory tool is in read-only mode for this chat")
        try:
            result = await user_memory.tool_add_experience_memory(
                user_memory.ToolAddExperienceBody(**arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"addExperienceMemory with error detail: {exc}")
        if not result.get("success"):
            return _failure(result.get("message") or "Failed to save memory")
        return _success(
            f'Experience memory "{arguments.get("title")}" saved with memoryId: "{result.get("memoryId")}" '
            f'and experienceId: "{result.get("experienceId")}"',
            {"experienceId": result.get("experienceId"), "memoryId": result.get("memoryId")},
        )

    if api_name == "addIdentityMemory":
        if _read_only(arguments):
            return _failure("Memory tool is in read-only mode for this chat")
        try:
            result = await user_memory.tool_add_identity_memory(
                user_memory.ToolAddIdentityBody(**arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"addIdentityMemory with error detail: {exc}")
        if not result.get("success"):
            return _failure(result.get("message") or "Failed to save identity memory")
        return _success(
            f'Identity memory "{arguments.get("title")}" saved with memoryId: "{result.get("memoryId")}" '
            f'and identityId: "{result.get("identityId")}"',
            {"identityId": result.get("identityId"), "memoryId": result.get("memoryId")},
        )

    if api_name == "addPreferenceMemory":
        if _read_only(arguments):
            return _failure("Memory tool is in read-only mode for this chat")
        try:
            result = await user_memory.tool_add_preference_memory(
                user_memory.ToolAddPreferenceBody(**arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"addPreferenceMemory with error detail: {exc}")
        if not result.get("success"):
            return _failure(result.get("message") or "Failed to save memory")
        return _success(
            f'Preference memory "{arguments.get("title")}" saved with memoryId: "{result.get("memoryId")}" '
            f'and preferenceId: "{result.get("preferenceId")}"',
            {"memoryId": result.get("memoryId"), "preferenceId": result.get("preferenceId")},
        )

    if api_name == "updateIdentityMemory":
        if _read_only(arguments):
            return _failure("Memory tool is in read-only mode for this chat")
        try:
            result = await user_memory.tool_update_identity_memory(
                user_memory.ToolUpdateIdentityBody(**arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"updateIdentityMemory with error detail: {exc}")
        if not result.get("success"):
            return _failure(result.get("message") or "Identity memory not found")
        return _success(f"Identity memory updated: {arguments.get('id')}", {"identityId": arguments.get("id")})

    if api_name == "removeIdentityMemory":
        if _read_only(arguments):
            return _failure("Memory tool is in read-only mode for this chat")
        try:
            result = await user_memory.tool_remove_identity_memory(
                user_memory.ToolRemoveIdentityBody(**arguments),
                user_id=user_id,
                session=session,
            )
        except Exception as exc:
            return _failure(f"removeIdentityMemory with error detail: {exc}")
        if not result.get("success"):
            return _failure(result.get("message") or "Identity memory not found")
        return _success(
            f"Identity memory removed: {arguments.get('id')}\nReason: {arguments.get('reason')}",
            {"identityId": arguments.get("id"), "reason": arguments.get("reason")},
        )

    return _failure(f"Unknown memory API: {api_name}")


async def _memory_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    del kwargs
    return _json(await run_memory_api(api_name, arguments, session=session, user_id=user_id))


# ── Context-aware implementations ────────────────────────────────────


async def memory_search_with_context(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Vector-based memory search with layer/category filters."""
    from app.services import llm_service, memory_service

    query = arguments.get("query", "")
    if not query:
        return json.dumps({"error": "query is required"})

    layer = arguments.get("layer")
    category = arguments.get("category")
    limit = min(arguments.get("limit", 10), 20)

    try:
        vectors = await llm_service.embed([query])
        query_embedding = vectors[0] if vectors else None
    except Exception as exc:
        logger.warning("Embedding failed, falling back to text search: %s", exc)
        query_embedding = None

    try:
        if query_embedding:
            results = await memory_service.search_memories_by_vector(
                session, user_id, query_embedding,
                layer=layer, category=category, limit=limit,
            )
        else:
            results = await memory_service.search_memories(
                session, user_id, query,
                layer=layer, category=category, limit=limit,
            )
    except Exception as exc:
        logger.error("Memory search failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Memory search failed: {exc}"})

    return json.dumps({
        "query": query,
        "total": len(results),
        "memories": [
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "summary": r.get("summary") or r.get("content", ""),
                "layer": r.get("layer"),
                "category": r.get("category"),
                "score": r.get("score"),
                "created_at": r.get("created_at"),
            }
            for r in results
        ],
    })


async def memory_store_with_context(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
) -> str:
    """Store a memory with auto-embedding, supporting all 5 layers."""
    from app.services import llm_service, memory_service

    summary = arguments.get("summary", "")
    if not summary:
        return json.dumps({"error": "summary is required"})

    title = arguments.get("title")
    details = arguments.get("details")
    layer = arguments.get("layer", "semantic")
    memory_type = arguments.get("memory_type")
    category = arguments.get("category")
    tags = arguments.get("tags")

    # Generate embedding
    embed_text = f"{title or ''} {summary} {details or ''}".strip()
    try:
        vectors = await llm_service.embed([embed_text])
        embedding = vectors[0] if vectors else None
    except Exception as exc:
        logger.warning("Embedding generation failed: %s", exc)
        embedding = None

    try:
        memory = await memory_service.create_memory(
            session,
            user_id=user_id,
            content=summary,
            title=title,
            layer=layer,
            memory_type=memory_type,
            category=category,
            tags=tags,
            embedding=embedding,
            metadata={"details": details} if details else None,
        )
        return json.dumps({
            "status": "stored",
            "memory_id": memory.get("id") if isinstance(memory, dict) else str(memory.id),
            "layer": layer,
            "summary": summary[:100],
        })
    except Exception as exc:
        logger.error("Memory store failed: %s", exc, exc_info=True)
        return json.dumps({"error": f"Memory store failed: {exc}"})


# ── Registered tools (context-backed) ────────────────────────────────


@register(
    "memory_search",
    description="Search user memories by semantic similarity. Supports 5 layers: "
    "event, semantic, episodic, procedural, persona.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "layer": {
                "type": "string",
                "enum": ["event", "semantic", "episodic", "procedural", "persona"],
                "description": "Filter by memory layer",
            },
            "category": {
                "type": "string",
                "description": "Filter by category",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10, max 20)",
                "default": 10,
            },
        },
        "required": ["query"],
    },
)
async def memory_search(arguments: dict[str, Any]) -> str:
    """Context-required fallback; real implementation uses memory_search_with_context."""
    return json.dumps({"error": "memory_search requires DB context"})


@register(
    "memory_store",
    description="Store a new user memory with automatic embedding. Supports 5 layers: "
    "event, semantic, episodic, procedural, persona.",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Brief summary of the memory"},
            "title": {"type": "string", "description": "Optional title"},
            "details": {"type": "string", "description": "Detailed content of the memory"},
            "layer": {
                "type": "string",
                "description": "Memory layer",
                "enum": ["event", "semantic", "episodic", "procedural", "persona"],
                "default": "semantic",
            },
            "memory_type": {"type": "string", "description": "Sub-type within the layer"},
            "category": {"type": "string", "description": "Category tag"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for organization",
            },
        },
        "required": ["summary"],
    },
)
async def memory_store(arguments: dict[str, Any]) -> str:
    """Context-required fallback; real implementation uses memory_store_with_context."""
    return json.dumps({"error": "memory_store requires DB context"})


register_context_handler("memory_search", memory_search_with_context)
register_context_handler("memory_store", memory_store_with_context)


@register(
    MEMORY_IDENTIFIER,
    description="User Memory — search and manage structured user memory.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {"type": "string", "enum": MEMORY_APIS},
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def memory_tool_context_required(args: dict[str, Any]) -> str:
    return _json({"error": "Memory tool requires server context (session + user_id)."})


for _api in MEMORY_APIS:
    register_context_handler(f"{MEMORY_IDENTIFIER}__{_api}", _memory_context_dispatch)
