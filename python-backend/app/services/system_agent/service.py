"""System Agent Service — LLM chains for automated tasks.

Ports TS ``systemAgent/index.ts``:
- Topic title generation (structured output)
- Translation (future)
- Agent meta generation (future)
- Brief synthesis (future)

Each method reads the user's preferred model/provider from settings,
falls back to sensible defaults, and calls the LLM via litellm.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Default system agent model config (mirrors TS DEFAULT_SYSTEM_AGENT_CONFIG)
_DEFAULTS: dict[str, dict[str, str]] = {
    "topic": {"model": "gpt-4o-mini", "provider": "openai"},
    "translation": {"model": "gpt-4o-mini", "provider": "openai"},
    "agentMeta": {"model": "gpt-4o-mini", "provider": "openai"},
    "historyCompress": {"model": "gpt-4o-mini", "provider": "openai"},
}

TOPIC_TITLE_SCHEMA = {
    "name": "topic_title",
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "A concise topic title"},
        },
        "required": ["title"],
        "additionalProperties": False,
    },
    "strict": True,
}


class SystemAgentService:
    """Server-side service for SystemAgent automated tasks.

    Encapsulates the common pattern: read user config → build prompt
    → call LLM → return structured result.
    """

    def __init__(self, session: AsyncSession, user_id: str) -> None:
        self._db = session
        self._uid = user_id

    # ── Public Methods ────────────────────────────────────────────────

    async def generate_topic_title(
        self,
        user_prompt: str,
        last_assistant_content: str,
    ) -> Optional[str]:
        """Generate a concise topic title from user prompt + assistant reply.

        Returns the generated title string, or None on failure.
        """
        try:
            config = await self._get_task_model_config("topic")
            locale = await self._get_user_locale()

            logger.debug(
                "generateTopicTitle: locale=%s, model=%s/%s",
                locale, config["provider"], config["model"],
            )

            system_prompt = (
                f"You are a title generator. Generate a concise, descriptive title "
                f"(2-8 words) for the following conversation. "
                f"Respond in {locale} language. "
                f"Return JSON with a single 'title' field."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": last_assistant_content},
            ]

            from app.services import llm_service

            response = await llm_service.chat(
                messages,
                model=f"{config['provider']}/{config['model']}",
                stream=False,
                temperature=0.3,
                max_tokens=100,
                extra_kwargs={
                    "response_format": {"type": "json_object"},
                },
            )

            content = response.choices[0].message.content or ""
            try:
                data = json.loads(content)
                title = data.get("title", "").strip()
            except (json.JSONDecodeError, AttributeError):
                title = content.strip()

            if not title:
                logger.debug("generateTopicTitle: LLM returned empty title")
                return None

            logger.debug("generateTopicTitle: generated title=%r", title)
            return title

        except Exception:
            logger.error("SystemAgentService.generateTopicTitle failed", exc_info=True)
            return None

    async def translate_text(
        self,
        text: str,
        target_locale: str,
        *,
        source_locale: Optional[str] = None,
    ) -> Optional[str]:
        """Translate text to the target locale.

        Returns translated text, or None on failure.
        """
        try:
            config = await self._get_task_model_config("translation")

            source_hint = f" from {source_locale}" if source_locale else ""
            system_prompt = (
                f"You are a translator. Translate the following text{source_hint} "
                f"to {target_locale}. Return only the translated text, nothing else."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ]

            from app.services import llm_service

            response = await llm_service.chat(
                messages,
                model=f"{config['provider']}/{config['model']}",
                stream=False,
                temperature=0.2,
                max_tokens=2000,
            )

            content = response.choices[0].message.content or ""
            return content.strip() or None

        except Exception:
            logger.error("SystemAgentService.translateText failed", exc_info=True)
            return None

    async def generate_brief_synthesis(
        self,
        conversation_messages: list[dict[str, Any]],
        task_name: str,
    ) -> Optional[dict[str, str]]:
        """Synthesize a brief (title + summary) from conversation history.

        Returns ``{"title": "...", "summary": "..."}`` or None on failure.
        """
        try:
            config = await self._get_task_model_config("topic")
            locale = await self._get_user_locale()

            # Trim conversation to last 20 messages to stay within context
            recent = conversation_messages[-20:]
            conversation_text = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
                for m in recent
            )

            system_prompt = (
                f"You are a brief synthesizer for task '{task_name}'. "
                f"Analyze the conversation and produce a JSON object with:\n"
                f"- \"title\": a concise title (3-8 words)\n"
                f"- \"summary\": a 1-3 sentence summary of the key outcome or decision\n"
                f"Respond in {locale} language."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": conversation_text},
            ]

            from app.services import llm_service

            response = await llm_service.chat(
                messages,
                model=f"{config['provider']}/{config['model']}",
                stream=False,
                temperature=0.3,
                max_tokens=300,
                extra_kwargs={
                    "response_format": {"type": "json_object"},
                },
            )

            content = response.choices[0].message.content or ""
            data = json.loads(content)
            title = data.get("title", "").strip()
            summary = data.get("summary", "").strip()

            if not title or not summary:
                return None

            return {"title": title, "summary": summary}

        except Exception:
            logger.error("SystemAgentService.generateBriefSynthesis failed", exc_info=True)
            return None

    async def generate_task_handoff(
        self,
        task_context: dict[str, Any],
        source_agent_name: str,
        target_agent_name: str,
    ) -> Optional[str]:
        """Generate a handoff instruction from one agent to another.

        Returns the handoff instruction text, or None on failure.
        """
        try:
            config = await self._get_task_model_config("topic")

            system_prompt = (
                f"You are a task coordinator. Agent '{source_agent_name}' needs to "
                f"hand off work to agent '{target_agent_name}'. "
                f"Generate a clear, actionable handoff instruction that includes:\n"
                f"- What has been done so far\n"
                f"- What needs to be done next\n"
                f"- Any important context or constraints\n"
                f"Be concise (2-4 paragraphs)."
            )

            context_text = json.dumps(task_context, indent=2, default=str)[:4000]

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Task context:\n{context_text}"},
            ]

            from app.services import llm_service

            response = await llm_service.chat(
                messages,
                model=f"{config['provider']}/{config['model']}",
                stream=False,
                temperature=0.4,
                max_tokens=500,
            )

            content = response.choices[0].message.content or ""
            return content.strip() or None

        except Exception:
            logger.error("SystemAgentService.generateTaskHandoff failed", exc_info=True)
            return None

    # ── Private Helpers ───────────────────────────────────────────────

    async def _get_task_model_config(
        self,
        task_key: str,
    ) -> dict[str, str]:
        """Get model/provider for a specific systemAgent task type.

        Falls back to defaults when user has no custom settings.
        """
        defaults = _DEFAULTS.get(task_key, _DEFAULTS["topic"])

        try:
            from app.models.user import UserSettings
            stmt = select(UserSettings).where(UserSettings.id == self._uid)
            result = await self._db.execute(stmt)
            setting = result.scalar_one_or_none()

            if setting and setting.system_agent:
                task_config = setting.system_agent.get(task_key, {})
                return {
                    "model": task_config.get("model") or defaults["model"],
                    "provider": task_config.get("provider") or defaults["provider"],
                }
        except Exception:
            logger.debug("Failed to load user systemAgent config, using defaults")

        return defaults

    async def _get_user_locale(self) -> str:
        """Get the user's preferred response language."""
        try:
            from app.models.user import UserSettings
            stmt = select(UserSettings).where(UserSettings.id == self._uid)
            result = await self._db.execute(stmt)
            setting = result.scalar_one_or_none()

            if setting and setting.general:
                return setting.general.get("language", "en-US")
        except Exception:
            pass
        return "en-US"
