"""Onboarding service — mirrors TS ``OnboardingService``.

Manages user onboarding flow: agent creation, topic lifecycle,
structured field collection, document management, and phase derivation.

Mirrors: src/server/services/onboarding/index.ts
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.agent_ops import AgentDocument
from app.models.file import Document
from app.models.message import Message
from app.models.persona import UserPersonaDocument, UserPersonaDocumentHistory
from app.models.topic import Topic
from app.models.user import User, UserSettings
from app.models._helpers import _utcnow, id_generator, create_nanoid

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

BUILTIN_SLUG_INBOX = "inbox"
BUILTIN_SLUG_WEB_ONBOARDING = "web-onboarding"

CURRENT_ONBOARDING_VERSION = 2
MAX_ONBOARDING_STEPS = 5
MIN_DISCOVERY_USER_MESSAGES = 3
RECOMMENDED_DISCOVERY_USER_MESSAGES = 5

SOUL_FILENAME = "SOUL.md"

SAVE_USER_QUESTION_FIELDS = frozenset(
    {"agentName", "agentEmoji", "fullName", "interests", "responseLanguage"}
)

STRUCTURED_FIELD_LABELS = {
    "agentEmoji": "agent emoji",
    "agentName": "agent name",
    "fullName": "full name",
    "interests": "interests",
    "responseLanguage": "response language",
}

MarkdownPatchErrorDetail = dict[str, Any]


class MarkdownPatchError(ValueError):
    def __init__(self, error: MarkdownPatchErrorDetail) -> None:
        self.error = error
        super().__init__(format_markdown_patch_error(error))


def format_markdown_patch_error(error: MarkdownPatchErrorDetail) -> str:
    idx = error.get("hunkIndex")
    code = error.get("code")
    if code == "EMPTY_HUNKS":
        return "No hunks provided. Include at least one hunk (replace / delete / deleteLines / insertAt / replaceLines)."
    if code == "EMPTY_SEARCH":
        return f"Hunk #{idx} has empty search. Provide a non-empty substring to locate."
    if code == "HUNK_NOT_FOUND":
        return (
            f"Hunk #{idx} search not found. Ensure the search string matches the current document "
            "byte-exact (whitespace, punctuation, casing). Re-read the document if unsure."
        )
    if code == "HUNK_AMBIGUOUS":
        return (
            f"Hunk #{idx} search matches {error.get('occurrences', 0)} locations. Add surrounding "
            "context to uniquify, or set replaceAll=true to replace every occurrence."
        )
    if code == "INVALID_LINE_RANGE":
        return f"Hunk #{idx} has endLine < startLine. Use inclusive 1-based line numbers where endLine >= startLine."
    if code == "LINE_OUT_OF_RANGE":
        total = error.get("totalLines", 0)
        return (
            f"Hunk #{idx} references a line outside [1, {total}] (insertAt may also target line "
            f"{total + 1} to append). Re-check the injected document's line numbers."
        )
    if code == "LINE_OVERLAP":
        return (
            f"Hunk #{idx} overlaps another line-based hunk in the same call. Split them across "
            "multiple updateDocument calls or merge them into one hunk."
        )
    return f"Markdown patch failed at hunk #{idx}."


def _count_occurrences(source: str, needle: str) -> int:
    if not needle:
        return 0
    count = 0
    start = 0
    while True:
        index = source.find(needle, start)
        if index == -1:
            return count
        count += 1
        start = index + len(needle)


def _patch_mode(hunk: dict[str, Any]) -> str:
    return hunk.get("mode") or "replace"


def _is_line_based_hunk(hunk: dict[str, Any]) -> bool:
    return _patch_mode(hunk) in {"deleteLines", "insertAt", "replaceLines"}


def _split_markdown_lines(source: str) -> list[str]:
    if source == "":
        return []
    return (source[:-1] if source.endswith("\n") else source).split("\n")


def _join_markdown_lines(lines: list[str], preserve_trailing_newline: bool) -> str:
    joined = "\n".join(lines)
    return f"{joined}\n" if preserve_trailing_newline and lines else joined


def _validate_line_hunk(
    hunk: dict[str, Any],
    total_lines: int,
    hunk_index: int,
) -> MarkdownPatchErrorDetail | None:
    mode = _patch_mode(hunk)
    if mode == "insertAt":
        line = hunk.get("line")
        if type(line) is not int or line < 1 or line > total_lines + 1:
            return {
                "code": "LINE_OUT_OF_RANGE",
                "hunkIndex": hunk_index,
                "line": line,
                "totalLines": total_lines,
            }
        return None

    start_line = hunk.get("startLine")
    end_line = hunk.get("endLine")
    if type(start_line) is not int or type(end_line) is not int:
        return {"code": "LINE_OUT_OF_RANGE", "hunkIndex": hunk_index, "totalLines": total_lines}
    if end_line < start_line:
        return {"code": "INVALID_LINE_RANGE", "hunkIndex": hunk_index}
    if start_line < 1 or end_line > total_lines:
        return {"code": "LINE_OUT_OF_RANGE", "hunkIndex": hunk_index, "totalLines": total_lines}
    return None


def _line_anchor(indexed_hunk: dict[str, Any]) -> int:
    hunk = indexed_hunk["hunk"]
    return hunk["line"] if _patch_mode(hunk) == "insertAt" else hunk["startLine"]


def _line_range(indexed_hunk: dict[str, Any]) -> tuple[int, int]:
    hunk = indexed_hunk["hunk"]
    if _patch_mode(hunk) == "insertAt":
        line = hunk["line"]
        return line, line
    return hunk["startLine"], hunk["endLine"]


def _line_ranges_overlap_or_touch(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_start, left_end = _line_range(left)
    right_start, right_end = _line_range(right)
    return left_start <= right_end and right_start <= left_end


def _apply_line_hunk(lines: list[str], hunk: dict[str, Any]) -> list[str]:
    mode = _patch_mode(hunk)
    next_lines = lines.copy()
    if mode == "insertAt":
        content = hunk.get("content", "")
        inserted = [""] if content == "" else str(content).split("\n")
        next_lines[hunk["line"] - 1:hunk["line"] - 1] = inserted
        return next_lines

    start = hunk["startLine"] - 1
    end = hunk["endLine"]
    if mode == "deleteLines":
        del next_lines[start:end]
        return next_lines

    content = hunk.get("content", "")
    replacement = [] if content == "" else str(content).split("\n")
    next_lines[start:end] = replacement
    return next_lines


def apply_markdown_patch(source: str, hunks: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(hunks, list) or not hunks:
        return {"error": {"code": "EMPTY_HUNKS", "hunkIndex": -1}, "ok": False}

    current = source
    applied = 0
    line_hunks: list[dict[str, Any]] = []

    for hunk_index, hunk in enumerate(hunks):
        if _is_line_based_hunk(hunk):
            line_hunks.append({"hunk": hunk, "index": hunk_index})
            continue

        search = hunk.get("search", "")
        if not search:
            return {"error": {"code": "EMPTY_SEARCH", "hunkIndex": hunk_index}, "ok": False}

        occurrences = _count_occurrences(current, search)
        if occurrences == 0:
            return {
                "error": {"code": "HUNK_NOT_FOUND", "hunkIndex": hunk_index, "search": search},
                "ok": False,
            }
        if occurrences > 1 and not hunk.get("replaceAll", False):
            return {
                "error": {
                    "code": "HUNK_AMBIGUOUS",
                    "hunkIndex": hunk_index,
                    "occurrences": occurrences,
                },
                "ok": False,
            }

        replacement = "" if _patch_mode(hunk) == "delete" else hunk.get("replace", "")
        if hunk.get("replaceAll", False):
            current = current.replace(search, replacement)
        else:
            current = current.replace(search, replacement, 1)
        applied += occurrences if hunk.get("replaceAll", False) else 1

    if not line_hunks:
        return {"applied": applied, "content": current, "ok": True}

    sorted_hunks = sorted(line_hunks, key=_line_anchor, reverse=True)
    preserve_trailing_newline = current.endswith("\n")
    lines = _split_markdown_lines(current)
    baseline_total_lines = len(lines)

    for indexed in sorted_hunks:
        error = _validate_line_hunk(indexed["hunk"], baseline_total_lines, indexed["index"])
        if error:
            return {"error": error, "ok": False}

    for i, left in enumerate(sorted_hunks[:-1]):
        for right in sorted_hunks[i + 1:]:
            if _line_ranges_overlap_or_touch(left, right):
                return {"error": {"code": "LINE_OVERLAP", "hunkIndex": left["index"]}, "ok": False}

    for indexed in sorted_hunks:
        lines = _apply_line_hunk(lines, indexed["hunk"])
        applied += 1

    return {"applied": applied, "content": _join_markdown_lines(lines, preserve_trailing_newline), "ok": True}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_natural_list(items: list[str]) -> str:
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


class OnboardingService:
    """Port of the TS OnboardingService."""

    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self._db = db
        self._user_id = user_id
        self._cached_inbox_agent_id: Optional[str] = None

    # ── Agent helpers ────────────────────────────────────────────────

    async def get_inbox_agent_id(self) -> str:
        if self._cached_inbox_agent_id:
            return self._cached_inbox_agent_id

        result = await self._db.execute(
            select(Agent.id).where(
                and_(Agent.slug == BUILTIN_SLUG_INBOX, Agent.user_id == self._user_id)
            )
        )
        agent_id = result.scalar_one_or_none()
        if not agent_id:
            raise ValueError("Inbox agent not found")
        self._cached_inbox_agent_id = agent_id
        return agent_id

    async def _get_builtin_agent(self, slug: str) -> Optional[Agent]:
        result = await self._db.execute(
            select(Agent).where(
                and_(Agent.slug == slug, Agent.user_id == self._user_id)
            )
        )
        return result.scalar_one_or_none()

    async def _ensure_builtin_agent(self, slug: str) -> Agent:
        agent = await self._get_builtin_agent(slug)
        if agent:
            return agent
        agent = Agent(
            slug=slug,
            user_id=self._user_id,
        )
        self._db.add(agent)
        await self._db.flush()
        return agent

    # ── User state helpers ───────────────────────────────────────────

    async def _get_user(self) -> Optional[User]:
        result = await self._db.execute(
            select(User).where(User.id == self._user_id)
        )
        return result.scalar_one_or_none()

    async def _get_user_settings(self) -> Optional[UserSettings]:
        result = await self._db.execute(
            select(UserSettings).where(UserSettings.user_id == self._user_id)
        )
        return result.scalar_one_or_none()

    async def _update_user(self, **kwargs: Any) -> None:
        await self._db.execute(
            update(User).where(User.id == self._user_id).values(**kwargs)
        )

    async def _upsert_user_settings(self, **kwargs: Any) -> None:
        existing = await self._get_user_settings()
        if existing:
            kwargs["updated_at"] = _now()
            await self._db.execute(
                update(UserSettings)
                .where(UserSettings.user_id == self._user_id)
                .values(**kwargs)
            )
        else:
            us = UserSettings(user_id=self._user_id, **kwargs)
            self._db.add(us)
            await self._db.flush()

    # ── Document helpers ─────────────────────────────────────────────

    async def _get_document_by_filename(
        self, agent_id: str, filename: str
    ) -> Optional[dict]:
        """Get a document linked to an agent by its filename."""
        result = await self._db.execute(
            select(Document)
            .join(AgentDocument, AgentDocument.document_id == Document.id)
            .where(
                and_(
                    AgentDocument.agent_id == agent_id,
                    AgentDocument.user_id == self._user_id,
                    AgentDocument.deleted_at.is_(None),
                    Document.filename == filename,
                )
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return None
        return {
            "id": doc.id,
            "content": doc.content,
            "filename": doc.filename,
        }

    async def _upsert_document_by_filename(
        self, agent_id: str, filename: str, content: str
    ) -> dict:
        """Create or update a document linked to an agent, keyed by filename."""
        # Check if exists
        result = await self._db.execute(
            select(Document.id, AgentDocument.id)
            .select_from(Document)
            .join(AgentDocument, AgentDocument.document_id == Document.id)
            .where(
                and_(
                    AgentDocument.agent_id == agent_id,
                    AgentDocument.user_id == self._user_id,
                    AgentDocument.deleted_at.is_(None),
                    Document.filename == filename,
                )
            )
        )
        row = result.first()

        if row:
            doc_id = row[0]
            await self._db.execute(
                update(Document)
                .where(Document.id == doc_id)
                .values(
                    content=content,
                    total_char_count=len(content),
                    total_line_count=content.count("\n") + 1,
                    updated_at=_now(),
                )
            )
            return {"id": doc_id}
        else:
            doc = Document(
                filename=filename,
                content=content,
                file_type="text/markdown",
                source_type="api",
                source="onboarding",
                user_id=self._user_id,
                total_char_count=len(content),
                total_line_count=content.count("\n") + 1,
            )
            self._db.add(doc)
            await self._db.flush()

            agent_doc = AgentDocument(
                agent_id=agent_id,
                document_id=doc.id,
                user_id=self._user_id,
            )
            self._db.add(agent_doc)
            await self._db.flush()
            return {"id": doc.id}

    # ── Persona helpers ──────────────────────────────────────────────

    async def _get_latest_persona(self) -> Optional[UserPersonaDocument]:
        result = await self._db.execute(
            select(UserPersonaDocument).where(
                UserPersonaDocument.user_id == self._user_id
            )
        )
        return result.scalar_one_or_none()

    async def _upsert_persona(
        self, content: str, edited_by: str = "agent_tool"
    ) -> dict:
        existing = await self._get_latest_persona()
        if existing:
            await self._db.execute(
                update(UserPersonaDocument)
                .where(UserPersonaDocument.id == existing.id)
                .values(persona=content, updated_at=_now())
            )
            return {"id": existing.id}
        else:
            doc = UserPersonaDocument(
                user_id=self._user_id,
                profile="default",
                persona=content,
            )
            self._db.add(doc)
            await self._db.flush()
            return {"id": doc.id}

    # ── Topic helpers ────────────────────────────────────────────────

    async def _ensure_topic(
        self, state: dict, agent_id: str
    ) -> tuple[str, bool]:
        """Return (topic_id, created)."""
        existing_id = state.get("activeTopicId")
        if existing_id:
            result = await self._db.execute(
                select(Topic.id).where(
                    and_(Topic.id == existing_id, Topic.user_id == self._user_id)
                )
            )
            if result.scalar_one_or_none():
                return existing_id, False

        topic = Topic(
            user_id=self._user_id,
            agent_id=agent_id,
            title="Onboarding",
        )
        self._db.add(topic)
        await self._db.flush()
        return topic.id, True

    async def _count_topic_user_messages(self, topic_id: str) -> int:
        result = await self._db.execute(
            select(func.count(Message.id)).where(
                and_(
                    Message.topic_id == topic_id,
                    Message.user_id == self._user_id,
                    Message.role == "user",
                )
            )
        )
        return result.scalar_one() or 0

    # ── State management ─────────────────────────────────────────────

    def _ensure_state(self, raw: Optional[dict]) -> dict:
        if not raw or (raw.get("version", 0) or 0) < CURRENT_ONBOARDING_VERSION:
            return {"version": CURRENT_ONBOARDING_VERSION}
        # Strip deprecated keys
        state = dict(raw)
        for key in ("agentIdentity", "completedNodes", "currentNode", "draft", "executionGuard", "profile"):
            state.pop(key, None)
        state.setdefault("version", CURRENT_ONBOARDING_VERSION)
        return state

    async def _save_state(self, state: dict) -> dict:
        normalized = self._ensure_state(state)
        await self._update_user(agent_onboarding=normalized)
        return normalized

    # ── Phase derivation ─────────────────────────────────────────────

    async def _get_missing_structured_fields(self) -> list[str]:
        user = await self._get_user()
        user_settings = await self._get_user_settings()
        missing: list[str] = []

        inbox_agent = await self._get_builtin_agent(BUILTIN_SLUG_INBOX)
        if not inbox_agent or not (inbox_agent.title or "").strip():
            missing.append("agentName")
        if not inbox_agent or not (inbox_agent.avatar or "").strip():
            missing.append("agentEmoji")

        if not user or not (user.full_name or "").strip():
            missing.append("fullName")
        if not user or not (user.interests or []):
            missing.append("interests")

        response_lang = ""
        if user_settings and user_settings.general:
            response_lang = (user_settings.general.get("responseLanguage") or "").strip()
        if not response_lang:
            missing.append("responseLanguage")

        return missing

    async def _derive_phase(
        self,
        missing: list[str],
        discovery_context: Optional[dict] = None,
    ) -> str:
        if "agentName" in missing:
            return "agent_identity"
        if "fullName" in missing:
            return "user_identity"
        if "interests" in missing or "responseLanguage" in missing:
            return "discovery"

        if discovery_context:
            exchanges = (
                discovery_context["currentUserMessageCount"]
                - discovery_context["startUserMessageCount"]
            )
            if exchanges < MIN_DISCOVERY_USER_MESSAGES:
                return "discovery"

        return "summary"

    # ── Public API ───────────────────────────────────────────────────

    async def get_state(self) -> dict:
        """Return UserAgentOnboardingContext."""
        user = await self._get_user()
        state = self._ensure_state(user.agent_onboarding if user else None)
        missing = await self._get_missing_structured_fields()
        topic_id = state.get("activeTopicId")

        if state.get("finishedAt"):
            return {
                "finished": True,
                "missingStructuredFields": missing,
                "phase": "summary",
                "topicId": topic_id,
                "version": state.get("version", CURRENT_ONBOARDING_VERSION),
            }

        discovery_context: Optional[dict] = None
        if topic_id:
            past_pre_discovery = "agentName" not in missing and "fullName" not in missing
            if past_pre_discovery:
                current_count = await self._count_topic_user_messages(topic_id)
                if state.get("discoveryStartUserMessageCount") is None:
                    state["discoveryStartUserMessageCount"] = current_count
                    await self._save_state(state)

                discovery_context = {
                    "currentUserMessageCount": current_count,
                    "startUserMessageCount": state.get("discoveryStartUserMessageCount", 0),
                }

        phase = await self._derive_phase(missing, discovery_context)

        result: dict[str, Any] = {
            "finished": False,
            "missingStructuredFields": missing,
            "phase": phase,
            "topicId": topic_id,
            "version": state.get("version", CURRENT_ONBOARDING_VERSION),
        }

        if discovery_context:
            dm_count = (
                discovery_context["currentUserMessageCount"]
                - discovery_context["startUserMessageCount"]
            )
            result["discoveryUserMessageCount"] = dm_count
            result["remainingDiscoveryExchanges"] = max(
                0, RECOMMENDED_DISCOVERY_USER_MESSAGES - dm_count
            )

        return result

    async def get_or_create_state(self) -> dict:
        """Get or create onboarding state — creates agent + topic if needed."""
        onboarding_agent = await self._ensure_builtin_agent(BUILTIN_SLUG_WEB_ONBOARDING)

        user = await self._get_user()
        state = self._ensure_state(user.agent_onboarding if user else None)
        topic_id, created = await self._ensure_topic(state, onboarding_agent.id)

        if created or topic_id != state.get("activeTopicId"):
            state["activeTopicId"] = topic_id
            state = await self._save_state(state)

        topic = (
            await self._db.execute(
                select(Topic).where(
                    and_(Topic.id == topic_id, Topic.user_id == self._user_id)
                )
            )
        ).scalar_one_or_none()

        context = await self.get_state()

        return {
            "agentId": onboarding_agent.id,
            "agentOnboarding": state,
            "context": context,
            "feedbackSubmitted": bool(
                topic
                and topic.metadata_
                and topic.metadata_.get("onboardingFeedback")
            ),
            "topicId": topic_id,
        }

    async def get_onboarding_agent_context(self) -> dict:
        """Return persona + soul content + phase guidance."""
        persona_doc = await self._get_latest_persona()
        persona_content = persona_doc.persona if persona_doc else None

        soul_content = None
        try:
            inbox_agent_id = await self.get_inbox_agent_id()
            soul_doc = await self._get_document_by_filename(inbox_agent_id, SOUL_FILENAME)
            soul_content = soul_doc["content"] if soul_doc else None
        except Exception:
            pass

        context = await self.get_state()
        phase = context.get("phase", "")
        phase_guidance = f"Current onboarding phase: {phase}" if phase else ""

        return {
            "personaContent": persona_content,
            "phaseGuidance": phase_guidance,
            "soulContent": soul_content,
        }

    async def save_user_question(self, input_: dict) -> dict:
        """Save structured fields from onboarding questions."""
        raw = input_ if isinstance(input_, dict) else {}
        ignored_fields = [k for k in raw if k not in SAVE_USER_QUESTION_FIELDS]
        saved_fields: list[str] = []
        unchanged_fields: list[str] = []

        user = await self._get_user()

        # fullName
        full_name = (raw.get("fullName") or "").strip() if isinstance(raw.get("fullName"), str) else ""
        if full_name:
            if full_name == (user.full_name if user else ""):
                unchanged_fields.append("fullName")
            else:
                await self._update_user(full_name=full_name)
                saved_fields.append("fullName")

        # interests
        interests = raw.get("interests")
        if isinstance(interests, list):
            interests = [i.strip() for i in interests if isinstance(i, str) and i.strip()]
        else:
            interests = None
        if interests:
            current = user.interests or [] if user else []
            if json.dumps(interests) == json.dumps(current):
                unchanged_fields.append("interests")
            else:
                await self._update_user(interests=interests)
                saved_fields.append("interests")

        # responseLanguage
        response_lang = (raw.get("responseLanguage") or "").strip() if isinstance(raw.get("responseLanguage"), str) else ""
        if response_lang:
            us = await self._get_user_settings()
            current_lang = (us.general or {}).get("responseLanguage", "") if us else ""
            if response_lang == current_lang:
                unchanged_fields.append("responseLanguage")
            else:
                new_general = dict(us.general or {}) if us else {}
                new_general["responseLanguage"] = response_lang
                await self._upsert_user_settings(general=new_general)
                saved_fields.append("responseLanguage")

        # agentName + agentEmoji
        agent_name = (raw.get("agentName") or "").strip() if isinstance(raw.get("agentName"), str) else ""
        agent_emoji = (raw.get("agentEmoji") or "").strip() if isinstance(raw.get("agentEmoji"), str) else ""
        if agent_name or agent_emoji:
            try:
                inbox_agent_id = await self.get_inbox_agent_id()
                patch: dict[str, Any] = {}
                if agent_name:
                    patch["title"] = agent_name
                if agent_emoji:
                    patch["avatar"] = agent_emoji

                await self._db.execute(
                    update(Agent).where(Agent.id == inbox_agent_id).values(**patch)
                )

                # Also update web-onboarding agent
                wb_agent = await self._get_builtin_agent(BUILTIN_SLUG_WEB_ONBOARDING)
                if wb_agent:
                    await self._db.execute(
                        update(Agent).where(Agent.id == wb_agent.id).values(**patch)
                    )

                if agent_name:
                    saved_fields.append("agentName")
                if agent_emoji:
                    saved_fields.append("agentEmoji")
            except Exception as exc:
                logger.error("Failed to update inbox agent identity: %s", exc)

        if not saved_fields and not unchanged_fields:
            return {
                "content": "No supported structured fields were provided. Use document tools for markdown-based onboarding content.",
                "ignoredFields": ignored_fields,
                "success": False,
            }

        parts: list[str] = []
        if saved_fields:
            parts.append(f"Saved {_format_natural_list([STRUCTURED_FIELD_LABELS[f] for f in saved_fields])}.")
        if unchanged_fields:
            parts.append(
                f"{_format_natural_list([STRUCTURED_FIELD_LABELS[f] for f in unchanged_fields])} already matched the current state."
            )
        if ignored_fields:
            parts.append(
                f"Ignored {_format_natural_list(ignored_fields)}; use document tools for markdown-based content."
            )

        return {
            "content": " ".join(parts),
            "ignoredFields": ignored_fields,
            "savedFields": saved_fields,
            "success": True,
            "unchangedFields": unchanged_fields,
        }

    async def read_onboarding_document(self, doc_type: str) -> dict:
        """Read soul or persona onboarding document."""
        if doc_type == "soul":
            try:
                inbox_agent_id = await self.get_inbox_agent_id()
                doc = await self._get_document_by_filename(inbox_agent_id, SOUL_FILENAME)
                return {
                    "content": doc["content"] if doc else "",
                    "id": doc["id"] if doc else None,
                    "type": "soul",
                }
            except Exception:
                return {"content": "", "id": None, "type": "soul"}

        # persona
        persona = await self._get_latest_persona()
        return {
            "content": persona.persona if persona else "",
            "id": persona.id if persona else None,
            "type": "persona",
        }

    async def update_onboarding_document(self, doc_type: str, content: str) -> dict:
        """Create or update soul or persona onboarding document."""
        if doc_type == "soul":
            inbox_agent_id = await self.get_inbox_agent_id()
            doc = await self._upsert_document_by_filename(
                inbox_agent_id, SOUL_FILENAME, content
            )
            return {"id": doc["id"], "type": "soul"}

        # persona
        result = await self._upsert_persona(content, edited_by="agent_tool")
        return {"id": result["id"], "type": "persona"}

    async def patch_onboarding_document(self, doc_type: str, hunks: list[dict]) -> dict:
        """Apply search/replace hunks to soul or persona document."""
        # Read current content
        if doc_type == "soul":
            inbox_agent_id = await self.get_inbox_agent_id()
            doc = await self._get_document_by_filename(inbox_agent_id, SOUL_FILENAME)
            current = doc["content"] if doc else ""
        else:
            persona = await self._get_latest_persona()
            current = persona.persona if persona else ""

        result = apply_markdown_patch(current, hunks)
        if not result["ok"]:
            raise MarkdownPatchError(result["error"])

        # Write back
        doc_result = await self.update_onboarding_document(doc_type, result["content"])
        return {"applied": result["applied"], "id": doc_result["id"], "type": doc_type}

    async def finish_onboarding(self) -> dict:
        """Mark onboarding as complete."""
        user = await self._get_user()
        state = self._ensure_state(user.agent_onboarding if user else None)
        inbox_agent_id = await self.get_inbox_agent_id()

        if state.get("finishedAt"):
            return {
                "agentId": inbox_agent_id,
                "content": "Agent onboarding already completed.",
                "finishedAt": state["finishedAt"],
                "success": True,
                "topicId": state.get("activeTopicId"),
            }

        finished_at = _now_iso()

        await self._update_user(
            agent_onboarding={
                **state,
                "finishedAt": finished_at,
                "version": CURRENT_ONBOARDING_VERSION,
            },
            onboarding={
                "currentStep": MAX_ONBOARDING_STEPS,
                "finishedAt": finished_at,
                "version": CURRENT_ONBOARDING_VERSION,
            },
        )

        # Transfer onboarding topic to inbox agent
        topic_id = state.get("activeTopicId")
        if topic_id:
            try:
                await self._db.execute(
                    update(Topic)
                    .where(and_(Topic.id == topic_id, Topic.user_id == self._user_id))
                    .values(agent_id=inbox_agent_id, updated_at=_now())
                )
                await self._db.execute(
                    update(Message)
                    .where(and_(Message.topic_id == topic_id, Message.user_id == self._user_id))
                    .values(agent_id=inbox_agent_id, updated_at=_now())
                )
            except Exception as exc:
                logger.error("Failed to transfer topic to inbox: %s", exc)

        return {
            "agentId": inbox_agent_id,
            "content": "Agent onboarding completed successfully.",
            "finishedAt": finished_at,
            "success": True,
            "topicId": topic_id,
        }

    async def reset(self) -> dict:
        """Reset onboarding state."""
        default_state = {"version": CURRENT_ONBOARDING_VERSION}

        await self._update_user(
            agent_onboarding=default_state,
            full_name=None,
            interests=[],
        )

        # Reset responseLanguage in user settings
        try:
            us = await self._get_user_settings()
            if us:
                new_general = dict(us.general or {})
                new_general["responseLanguage"] = None
                await self._upsert_user_settings(general=new_general)
        except Exception as exc:
            logger.error("Failed to reset responseLanguage: %s", exc)

        # Reset persona documents
        try:
            await self._db.execute(
                delete(UserPersonaDocumentHistory).where(
                    UserPersonaDocumentHistory.user_id == self._user_id
                )
            )
            await self._db.execute(
                delete(UserPersonaDocument).where(
                    UserPersonaDocument.user_id == self._user_id
                )
            )
        except Exception as exc:
            logger.error("Failed to reset persona documents: %s", exc)

        # Reset inbox agent title and avatar
        try:
            inbox_agent_id = await self.get_inbox_agent_id()
            await self._db.execute(
                update(Agent)
                .where(Agent.id == inbox_agent_id)
                .values(avatar=None, title=None)
            )
        except Exception as exc:
            logger.error("Failed to reset inbox agent: %s", exc)

        return default_state
