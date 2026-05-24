"""AiAgentService — unified orchestration layer for agent execution.

Architecture:
    exec_agent({ agent_id | slug, prompt })
        → resolve agent config from DB
        → create topic (if needed)
        → discover tools (plugins, skills)
        → ingest attachments
        → create user + assistant DB messages
        → fire agent signal event
        → create AgentRuntime operation
        → return ExecAgentResult

Also exposes:
    exec_group_agent() — Group Agent (Supervisor) execution
    exec_sub_agent_task() — SubAgent task with Thread isolation
    interrupt_task() — Interrupt a running task
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_context
from app.models.agent import Agent
from app.models.file import File
from app.models.message import Message, MessageFile, MessagePlugin
from app.models.persona import UserPersonaDocument
from app.models.skill import AgentSkill
from app.models.topic import Topic
from app.models.topic_ext import Thread
from app.services.agent_runtime import AgentRuntimeService, agent_runtime
from app.services.ai_agent.ingest_attachment import ingest_attachment
from app.services.ai_agent.types import (
    AgentErrorType,
    AppContext,
    ExecAgentParams,
    ExecAgentResult,
    ExecGroupAgentParams,
    ExecGroupAgentResult,
    ExecSubAgentTaskParams,
    ExecSubAgentTaskResult,
    ResumeApproval,
    ToolManifest,
)

logger = logging.getLogger(__name__)

# Placeholder for assistant message content (mirrors TS LOADING_FLAT)
LOADING_FLAT = "..."


def _format_error_for_metadata(error: Any) -> Optional[dict[str, Any]]:
    """Format error for storage in thread/message metadata."""
    if error is None:
        return None
    if isinstance(error, Exception):
        return {"name": type(error).__name__, "message": str(error)}
    if isinstance(error, dict) and "message" in error:
        return error
    return {"message": str(error)}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


class AiAgentService:
    """Unified agent execution service.

    Instantiated per-request with a user_id. All DB operations use
    short-lived sessions via ``get_db_context()``.
    """

    def __init__(
        self,
        user_id: str,
        *,
        runtime: Optional[AgentRuntimeService] = None,
    ) -> None:
        self.user_id = user_id
        self._runtime = runtime or agent_runtime

    # ------------------------------------------------------------------
    # Agent resolution
    # ------------------------------------------------------------------

    async def _resolve_agent_config(
        self,
        session: AsyncSession,
        identifier: str,
    ) -> Optional[Agent]:
        """Resolve agent by ID or slug, returning the Agent row."""
        # Try by ID first
        stmt = select(Agent).where(
            Agent.id == identifier,
            Agent.user_id == self.user_id,
        )
        agent = (await session.execute(stmt)).scalar_one_or_none()
        if agent:
            return agent

        # Try by slug
        stmt = select(Agent).where(
            Agent.slug == identifier,
            Agent.user_id == self.user_id,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Topic management
    # ------------------------------------------------------------------

    async def _ensure_topic(
        self,
        session: AsyncSession,
        agent_id: str,
        params: ExecAgentParams,
    ) -> str:
        """Create or reuse a topic. Returns topic_id."""
        app_ctx = params.app_context
        if app_ctx and app_ctx.topic_id:
            logger.debug("exec_agent: reusing topic %s", app_ctx.topic_id)
            return app_ctx.topic_id

        if params.resume:
            raise ValueError("Resume mode requires the parent message to belong to a topic")

        # Build topic metadata
        metadata: Optional[dict[str, Any]] = None
        if params.cron_job_id or params.task_id or params.bot_context:
            metadata = {}
            if params.cron_job_id:
                metadata["cronJobId"] = params.cron_job_id
            if params.task_id:
                metadata["taskId"] = params.task_id
            if params.bot_context:
                metadata["bot"] = params.bot_context

        title = params.title
        if title is None:
            title = params.prompt[:50] + ("..." if len(params.prompt) > 50 else "")

        topic = Topic(
            user_id=self.user_id,
            agent_id=agent_id,
            title=title,
            metadata_=metadata,
        )
        session.add(topic)
        await session.flush()
        logger.debug(
            "exec_agent: created topic %s (trigger=%s)",
            topic.id,
            params.trigger or "default",
        )
        return topic.id

    # ------------------------------------------------------------------
    # Message persistence
    # ------------------------------------------------------------------

    async def _create_user_message(
        self,
        session: AsyncSession,
        agent_id: str,
        topic_id: str,
        params: ExecAgentParams,
        file_ids: Optional[list[str]] = None,
    ) -> Optional[Message]:
        """Create user message in DB. Returns None in resume mode."""
        effective_resume = params.resume or (params.resume_approval is not None)
        if effective_resume:
            return None

        msg = Message(
            role="user",
            content=params.prompt,
            user_id=self.user_id,
            agent_id=agent_id,
            topic_id=topic_id,
            thread_id=(params.app_context.thread_id if params.app_context else None),
            session_id=(params.app_context.session_id if params.app_context else None),
        )
        session.add(msg)
        await session.flush()

        # Link files
        if file_ids:
            for fid in file_ids:
                mf = MessageFile(
                    message_id=msg.id,
                    file_id=fid,
                    user_id=self.user_id,
                )
                session.add(mf)
            await session.flush()

        logger.debug("exec_agent: created user message %s", msg.id)
        return msg

    async def _create_assistant_message(
        self,
        session: AsyncSession,
        agent_id: str,
        topic_id: str,
        params: ExecAgentParams,
        parent_id: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Message:
        """Create assistant placeholder message in DB."""
        msg = Message(
            role="assistant",
            content=LOADING_FLAT,
            user_id=self.user_id,
            agent_id=agent_id,
            topic_id=topic_id,
            thread_id=(params.app_context.thread_id if params.app_context else None),
            session_id=(params.app_context.session_id if params.app_context else None),
            parent_id=parent_id,
            model=model,
            provider=provider,
        )
        session.add(msg)
        await session.flush()
        logger.debug("exec_agent: created assistant message %s", msg.id)
        return msg

    async def _update_message(
        self,
        session: AsyncSession,
        message_id: str,
        content: Optional[str] = None,
        error: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update a message's content and/or error."""
        values: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}
        if content is not None:
            values["content"] = content
        if error is not None:
            values["error"] = error
        stmt = (
            update(Message)
            .where(Message.id == message_id, Message.user_id == self.user_id)
            .values(**values)
        )
        await session.execute(stmt)

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    async def _discover_tools(
        self,
        session: AsyncSession,
        agent: Agent,
    ) -> tuple[
        Optional[list[dict[str, Any]]],  # tools (OpenAI function format)
        dict[str, ToolManifest],  # manifest map
        list[str],  # enabled tool IDs
    ]:
        """Discover and generate tool definitions for the agent.

        Returns (tools, manifest_map, enabled_tool_ids).
        """
        agent_plugins = list(agent.plugins or [])
        manifest_map: dict[str, ToolManifest] = {}
        enabled_ids: list[str] = []

        # Discover user-installed skills from DB
        stmt = select(AgentSkill).where(AgentSkill.user_id == self.user_id)
        skills = (await session.execute(stmt)).scalars().all()

        for skill in skills:
            if skill.manifest:
                manifest = ToolManifest(
                    identifier=skill.identifier,
                    api=skill.manifest.get("api", []),
                    meta=skill.manifest.get("meta"),
                    type=skill.manifest.get("type", "default"),
                )
                manifest_map[skill.identifier] = manifest

        # Build tool definitions from agent's configured plugins
        tools: list[dict[str, Any]] = []
        for plugin_id in agent_plugins:
            if plugin_id in manifest_map:
                manifest = manifest_map[plugin_id]
                enabled_ids.append(plugin_id)
                for api in manifest.api:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": f"{plugin_id}____{api.get('name', '')}",
                            "description": api.get("description", ""),
                            "parameters": api.get("parameters", {}),
                        },
                    })

        # Add builtin tools that are always available
        builtin_tools = self._get_builtin_tool_definitions()
        tools.extend(builtin_tools)
        for bt in builtin_tools:
            fn = bt.get("function", {})
            bt_id = fn.get("name", "").split("____")[0] if "____" in fn.get("name", "") else fn.get("name", "")
            if bt_id and bt_id not in enabled_ids:
                enabled_ids.append(bt_id)

        return tools if tools else None, manifest_map, enabled_ids

    @staticmethod
    def _get_builtin_tool_definitions() -> list[dict[str, Any]]:
        """Return builtin tool definitions that are always available.

        These map to the Python tool_execution service's registered tools.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information on a topic.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "max_results": {"type": "integer", "description": "Max results", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # File ingestion
    # ------------------------------------------------------------------

    async def _ingest_files(
        self,
        session: AsyncSession,
        params: ExecAgentParams,
    ) -> tuple[
        Optional[list[str]],  # file_ids
        Optional[list[dict[str, Any]]],  # image_list
        Optional[list[dict[str, Any]]],  # video_list
        Optional[list[dict[str, Any]]],  # file_list
        list[str],  # warnings
    ]:
        """Ingest external files and resolve attached file IDs.

        Returns (file_ids, image_list, video_list, file_list, warnings).
        """
        file_ids: list[str] = []
        image_list: list[dict[str, Any]] = []
        video_list: list[dict[str, Any]] = []
        file_list: list[dict[str, Any]] = []
        warnings: list[str] = []

        # 1. Ingest external files (from bot platforms, etc.)
        if params.files:
            for file_spec in params.files:
                try:
                    result = await ingest_attachment(
                        file_spec, session, self.user_id,
                    )
                    file_ids.append(result.file_id)

                    if result.is_image:
                        image_list.append({
                            "alt": file_spec.get("name", "image"),
                            "id": result.file_id,
                            "url": result.resolved_url,
                        })
                    elif result.is_video:
                        video_list.append({
                            "alt": file_spec.get("name", "video"),
                            "id": result.file_id,
                            "url": result.resolved_url,
                        })
                    else:
                        file_list.append({
                            "fileType": result.file_type,
                            "id": result.file_id,
                            "name": file_spec.get("name", "file"),
                            "size": file_spec.get("size", 0),
                            "url": result.resolved_url,
                        })
                except Exception as exc:
                    fname = file_spec.get("name") or file_spec.get("url", "unknown")
                    logger.warning("exec_agent: failed to ingest file %s: %s", fname, exc)
                    warnings.append(f'File "{fname}" could not be uploaded and was skipped.')

        # 2. Resolve already-attached file IDs
        if params.file_ids:
            deduped = list(dict.fromkeys(params.file_ids))
            stmt = select(File).where(
                File.id.in_(deduped),
                File.user_id == self.user_id,
            )
            records = (await session.execute(stmt)).scalars().all()
            record_by_id = {r.id: r for r in records}

            for fid in deduped:
                f = record_by_id.get(fid)
                if not f:
                    warnings.append(f'Attachment "{fid}" was not found and skipped.')
                    continue

                file_ids.append(f.id)
                ft = f.file_type or ""

                if ft.startswith("image"):
                    image_list.append({
                        "alt": f.name or "image",
                        "id": f.id,
                        "url": f.url,
                    })
                elif ft.startswith("video"):
                    video_list.append({
                        "alt": f.name or "video",
                        "id": f.id,
                        "url": f.url,
                    })
                else:
                    file_list.append({
                        "fileType": ft or "application/octet-stream",
                        "id": f.id,
                        "name": f.name or "file",
                        "size": f.size,
                        "url": f.url,
                    })

        return (
            file_ids if file_ids else None,
            image_list if image_list else None,
            video_list if video_list else None,
            file_list if file_list else None,
            warnings,
        )

    # ------------------------------------------------------------------
    # User persona / memory
    # ------------------------------------------------------------------

    async def _fetch_user_persona(
        self,
        session: AsyncSession,
    ) -> Optional[dict[str, Any]]:
        """Fetch the latest user persona document for memory injection."""
        stmt = (
            select(UserPersonaDocument)
            .where(UserPersonaDocument.user_id == self.user_id)
            .order_by(UserPersonaDocument.version.desc())
            .limit(1)
        )
        persona = (await session.execute(stmt)).scalar_one_or_none()
        if not persona or not persona.persona:
            return None

        return {
            "fetched_at": time.time(),
            "memories": {
                "persona": {
                    "narrative": persona.persona,
                    "tagline": persona.tagline,
                },
                "contexts": [],
                "experiences": [],
                "preferences": [],
            },
        }

    # ------------------------------------------------------------------
    # History messages
    # ------------------------------------------------------------------

    async def _load_history_messages(
        self,
        session: AsyncSession,
        params: ExecAgentParams,
    ) -> list[dict[str, Any]]:
        """Load existing messages for context."""
        app_ctx = params.app_context

        if params.existing_message_ids:
            stmt = select(Message).where(
                Message.id.in_(params.existing_message_ids),
                Message.user_id == self.user_id,
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [self._message_to_dict(m) for m in rows]

        if app_ctx and app_ctx.topic_id:
            stmt = (
                select(Message)
                .where(
                    Message.topic_id == app_ctx.topic_id,
                    Message.user_id == self.user_id,
                )
                .order_by(Message.created_at)
            )
            if app_ctx.thread_id:
                stmt = stmt.where(Message.thread_id == app_ctx.thread_id)
            rows = (await session.execute(stmt)).scalars().all()
            return [self._message_to_dict(m) for m in rows]

        return []

    @staticmethod
    def _message_to_dict(msg: Message) -> dict[str, Any]:
        d: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
        if msg.tools:
            d["tool_calls"] = msg.tools
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        return d

    # ------------------------------------------------------------------
    # Resume / human approval
    # ------------------------------------------------------------------

    async def _handle_resume_approval(
        self,
        session: AsyncSession,
        approval: ResumeApproval,
        parent_message: Message,
    ) -> None:
        """Persist user's approval/rejection decision to the DB."""
        if parent_message.role != "tool":
            raise ValueError(
                f"resumeApproval.parentMessageId must point at role='tool', got '{parent_message.role}'"
            )

        # Fetch the plugin row for validation
        stmt = select(MessagePlugin).where(
            MessagePlugin.id == approval.parent_message_id,
        )
        plugin = (await session.execute(stmt)).scalar_one_or_none()
        if not plugin:
            raise ValueError(
                f"resumeApproval: no plugin row for tool message {approval.parent_message_id}"
            )
        if plugin.tool_call_id and plugin.tool_call_id != approval.tool_call_id:
            raise ValueError(
                f"resumeApproval.toolCallId mismatch: "
                f"stored={plugin.tool_call_id}, requested={approval.tool_call_id}"
            )

        if approval.decision == "approved":
            plugin.state = {**(plugin.state or {}), "intervention": {"status": "approved"}}
        else:
            rejection_content = (
                f"User reject this tool calling with reason: {approval.rejection_reason}"
                if approval.rejection_reason
                else "User reject this tool calling without reason"
            )
            parent_message.content = rejection_content
            plugin.state = {
                **(plugin.state or {}),
                "intervention": {
                    "status": "rejected",
                    "rejectedReason": approval.rejection_reason,
                },
            }
            session.add(parent_message)

        session.add(plugin)
        await session.flush()

        logger.debug(
            "exec_agent: resumeApproval decision=%s applied (toolCallId=%s)",
            approval.decision,
            approval.tool_call_id,
        )

    # ------------------------------------------------------------------
    # Agent Signal integration
    # ------------------------------------------------------------------

    async def _fire_signal(
        self,
        agent_id: str,
        topic_id: str,
        message_id: str,
        prompt: str,
        trigger: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> None:
        """Enqueue agent signal event for a user message."""
        try:
            from app.services.agent_signal import get_orchestrator

            orchestrator = get_orchestrator()
            await orchestrator.receive_signal({
                "source_type": "agent.user.message",
                "source_id": message_id,
                "payload": {
                    "agent_id": agent_id,
                    "topic_id": topic_id,
                    "message": prompt,
                    "message_id": message_id,
                    "trigger": trigger,
                    "thread_id": thread_id,
                },
            })
        except Exception:
            logger.debug("exec_agent: failed to fire agent signal", exc_info=True)

    # ------------------------------------------------------------------
    # Topic metadata
    # ------------------------------------------------------------------

    async def _update_topic_metadata(
        self,
        session: AsyncSession,
        topic_id: str,
        metadata_patch: dict[str, Any],
    ) -> None:
        """Merge metadata into a topic's metadata_ field."""
        stmt = select(Topic).where(
            Topic.id == topic_id,
            Topic.user_id == self.user_id,
        )
        topic = (await session.execute(stmt)).scalar_one_or_none()
        if not topic:
            return
        existing = topic.metadata_ or {}
        topic.metadata_ = {**existing, **metadata_patch}
        session.add(topic)
        await session.flush()

    # ==================================================================
    # exec_agent — main entry point
    # ==================================================================

    async def exec_agent(self, params: ExecAgentParams) -> ExecAgentResult:
        """Execute agent with a prompt.

        This is the primary entry point that:
        1. Resolves agent config from DB
        2. Manages topic lifecycle
        3. Discovers tools
        4. Ingests attachments
        5. Creates DB messages
        6. Delegates to AgentRuntimeService
        """
        if not params.agent_id and not params.slug:
            raise ValueError("Either agent_id or slug must be provided")

        identifier = params.agent_id or params.slug or ""

        async with get_db_context() as session:
            # 1. Resolve agent
            agent = await self._resolve_agent_config(session, identifier)
            if not agent:
                raise ValueError(f"Agent not found: {identifier}")

            resolved_agent_id = agent.id
            model = params.model or agent.model or "openai/gpt-4o"
            provider = params.provider or agent.provider or "openai"

            # 2. Build system role
            system_role = agent.system_role or ""
            if params.instructions:
                system_role = (
                    f"{system_role}\n\n{params.instructions}" if system_role else params.instructions
                )

            logger.debug(
                "exec_agent: agent=%s model=%s provider=%s",
                resolved_agent_id, model, provider,
            )

            # 3. Handle effective resume
            effective_resume = params.resume or (params.resume_approval is not None)
            resume_parent_message: Optional[Message] = None

            if effective_resume:
                if not params.parent_message_id:
                    raise ValueError("parent_message_id is required when resume is true")
                if not params.app_context or not params.app_context.topic_id:
                    raise ValueError("app_context.topic_id is required when resume is true")

                stmt = select(Message).where(
                    Message.id == params.parent_message_id,
                    Message.user_id == self.user_id,
                )
                resume_parent_message = (await session.execute(stmt)).scalar_one_or_none()
                if not resume_parent_message:
                    raise ValueError(f"Parent message not found: {params.parent_message_id}")

            # 3b. Human approval
            if params.resume_approval:
                if not resume_parent_message:
                    raise ValueError("resumeApproval requires parentMessageId")
                await self._handle_resume_approval(
                    session, params.resume_approval, resume_parent_message,
                )

            # 4. Ensure topic
            topic_id = await self._ensure_topic(session, resolved_agent_id, params)

            # 5. Tool discovery
            tools: Optional[list[dict[str, Any]]] = None
            manifest_map: dict[str, ToolManifest] = {}
            enabled_tool_ids: list[str] = []

            if not params.disable_tools:
                tools, manifest_map, enabled_tool_ids = await self._discover_tools(
                    session, agent,
                )

                # Inject client function tools (Response API)
                if params.function_tools:
                    for ft in params.function_tools:
                        if tools is None:
                            tools = []
                        tools.append({
                            "type": "function",
                            "function": {
                                "name": f"lobe-client-fn____{ft['name']}",
                                "description": ft.get("description", ""),
                                "parameters": ft.get("parameters", {}),
                            },
                        })
                    enabled_tool_ids.append("lobe-client-fn")

            # 6. Ingest files
            file_ids, image_list, video_list, file_list, warnings = (
                await self._ingest_files(session, params)
            )

            # 7. Fetch user persona for memory
            user_persona = None
            memory_enabled = (agent.chat_config or {}).get("memory", {}).get("enabled", False)
            if memory_enabled:
                try:
                    user_persona = await self._fetch_user_persona(session)
                except Exception:
                    logger.debug("exec_agent: failed to fetch persona", exc_info=True)

            # 8. Load history messages
            history_messages = await self._load_history_messages(session, params)

            # 9. Create user message
            user_msg = await self._create_user_message(
                session, resolved_agent_id, topic_id, params, file_ids,
            )

            # 10. Fire agent signal
            if user_msg:
                asyncio.create_task(
                    self._fire_signal(
                        agent_id=resolved_agent_id,
                        topic_id=topic_id,
                        message_id=user_msg.id,
                        prompt=params.prompt,
                        trigger=params.trigger,
                        thread_id=(params.app_context.thread_id if params.app_context else None),
                    )
                )

            # 11. Create assistant placeholder
            parent_id = params.parent_message_id or (user_msg.id if user_msg else None)
            assistant_msg = await self._create_assistant_message(
                session,
                resolved_agent_id,
                topic_id,
                params,
                parent_id=parent_id,
                model=model,
                provider=provider,
            )

            # 12. Build messages for runtime
            user_message_dict = {
                "role": "user",
                "content": params.prompt,
            }
            if image_list:
                user_message_dict["imageList"] = image_list
            if video_list:
                user_message_dict["videoList"] = video_list
            if file_list:
                user_message_dict["fileList"] = file_list

            all_messages = (
                history_messages
                if effective_resume
                else [*history_messages, user_message_dict]
            )

            # 13. Prepare system prompt
            full_system_prompt = system_role
            if user_persona and user_persona.get("memories"):
                persona_data = user_persona["memories"].get("persona", {})
                narrative = persona_data.get("narrative", "")
                if narrative:
                    persona_section = f"\n\n## User Persona\n{narrative}"
                    full_system_prompt = (
                        f"{full_system_prompt}{persona_section}" if full_system_prompt else persona_section
                    )

        # --- Outside DB session: create runtime operation ---

        try:
            op_result = await self._runtime.create_operation(
                user_id=self.user_id,
                messages=all_messages,
                model=model,
                system_prompt=full_system_prompt or None,
                tools=tools,
                enable_memory=memory_enabled,
                agent_id=resolved_agent_id,
                session_id=(params.app_context.session_id if params.app_context else None),
                max_steps=params.max_steps,
            )

            operation_id = op_result["operation_id"]

            # Auto-start if requested
            auto_started = False
            if params.auto_start:
                if params.stream:
                    # For streaming, the caller will consume the stream
                    auto_started = True
                else:
                    asyncio.create_task(
                        self._runtime.run_operation(operation_id)
                    )
                    auto_started = True

            # Persist running operation in topic metadata
            async with get_db_context() as session:
                await self._update_topic_metadata(session, topic_id, {
                    "runningOperation": {
                        "operationId": operation_id,
                        "assistantMessageId": assistant_msg.id,
                        "scope": (params.app_context.scope if params.app_context else None),
                        "threadId": (params.app_context.thread_id if params.app_context else None),
                    },
                })

            now_iso = _utcnow_iso()
            return ExecAgentResult(
                success=True,
                operation_id=operation_id,
                topic_id=topic_id,
                agent_id=resolved_agent_id,
                assistant_message_id=assistant_msg.id,
                user_message_id=user_msg.id if user_msg else (params.parent_message_id or ""),
                status="created",
                auto_started=auto_started,
                message="Agent operation created successfully",
                created_at=now_iso,
                timestamp=now_iso,
            )

        except Exception as exc:
            # Operation startup failed — update assistant message with error
            error_message = str(exc)
            logger.error(
                "exec_agent: createOperation failed: %s", error_message, exc_info=True,
            )

            try:
                async with get_db_context() as session:
                    await self._update_message(
                        session,
                        assistant_msg.id,
                        content="",
                        error={
                            "type": AgentErrorType.RUNTIME_ERROR.value,
                            "message": error_message,
                            "body": {"detail": error_message},
                        },
                    )
            except Exception:
                logger.error("exec_agent: failed to update assistant msg with error", exc_info=True)

            now_iso = _utcnow_iso()
            return ExecAgentResult(
                success=False,
                operation_id="",
                topic_id=topic_id,
                agent_id=resolved_agent_id,
                assistant_message_id=assistant_msg.id,
                user_message_id=user_msg.id if user_msg else (params.parent_message_id or ""),
                status="error",
                auto_started=False,
                error=error_message,
                message="Agent operation failed to start",
                created_at=now_iso,
                timestamp=now_iso,
            )

    # ==================================================================
    # exec_group_agent
    # ==================================================================

    async def exec_group_agent(
        self, params: ExecGroupAgentParams,
    ) -> ExecGroupAgentResult:
        """Execute Group Agent (Supervisor) in a single call.

        Creates a topic with groupId, then delegates to exec_agent.
        """
        topic_id = params.topic_id
        is_create_new_topic = False

        if params.new_topic or not params.topic_id:
            # Create topic with groupId
            async with get_db_context() as session:
                title = (
                    (params.new_topic or {}).get("title")
                    or params.message[:50] + ("..." if len(params.message) > 50 else "")
                )
                topic = Topic(
                    user_id=self.user_id,
                    agent_id=params.agent_id,
                    title=title,
                    # groupId is stored in metadata (no dedicated column)
                    metadata_={"groupId": params.group_id},
                )
                session.add(topic)
                await session.flush()
                topic_id = topic.id
                is_create_new_topic = True
                logger.debug(
                    "exec_group_agent: created topic %s with groupId %s",
                    topic_id, params.group_id,
                )

        result = await self.exec_agent(ExecAgentParams(
            agent_id=params.agent_id,
            prompt=params.message,
            app_context=AppContext(
                group_id=params.group_id,
                topic_id=topic_id,
            ),
            auto_start=True,
        ))

        return ExecGroupAgentResult(
            success=result.success,
            operation_id=result.operation_id,
            topic_id=result.topic_id,
            assistant_message_id=result.assistant_message_id,
            user_message_id=result.user_message_id,
            is_create_new_topic=is_create_new_topic,
            error=result.error,
        )

    # ==================================================================
    # exec_sub_agent_task
    # ==================================================================

    async def exec_sub_agent_task(
        self, params: ExecSubAgentTaskParams,
    ) -> ExecSubAgentTaskResult:
        """Execute SubAgent task with Thread isolation.

        Creates an isolated Thread, delegates to exec_agent, and tracks
        metrics via lifecycle hooks.
        """
        async with get_db_context() as session:
            # 1. Create Thread
            thread = Thread(
                topic_id=params.topic_id,
                user_id=self.user_id,
                title=params.title,
                source_message_id=params.parent_message_id,
                type="isolation",
                status="processing",
            )
            # Store groupId if present
            if params.group_id:
                # Thread model doesn't have a group_id column; store in metadata
                # via a separate update after flush
                pass
            session.add(thread)
            await session.flush()

            thread_id = thread.id
            logger.debug("exec_sub_agent_task: created thread %s", thread_id)

        # 2. Delegate to exec_agent with threadId
        result = await self.exec_agent(ExecAgentParams(
            agent_id=params.agent_id,
            prompt=params.instruction,
            app_context=AppContext(
                group_id=params.group_id,
                thread_id=thread_id,
                topic_id=params.topic_id,
            ),
            auto_start=True,
            user_intervention_config={"approvalMode": "headless"},
        ))

        # 3. Store operationId in thread metadata
        async with get_db_context() as session:
            stmt = select(Thread).where(Thread.id == thread_id)
            thread = (await session.execute(stmt)).scalar_one_or_none()
            if thread:
                # Thread model doesn't have metadata column — but topic_ext.py
                # doesn't define one. We update status instead.
                if not result.success:
                    thread.status = "failed"
                session.add(thread)
                await session.flush()

        return ExecSubAgentTaskResult(
            success=result.success,
            operation_id=result.operation_id,
            thread_id=thread_id,
            assistant_message_id=result.assistant_message_id,
            error=result.error,
        )

    # ==================================================================
    # interrupt_task
    # ==================================================================

    async def interrupt_task(
        self,
        *,
        thread_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Interrupt a running task by threadId or operationId."""
        resolved_operation_id = operation_id

        if thread_id:
            async with get_db_context() as session:
                stmt = select(Thread).where(
                    Thread.id == thread_id,
                    Thread.user_id == self.user_id,
                )
                thread = (await session.execute(stmt)).scalar_one_or_none()
                if not thread:
                    raise ValueError("Thread not found")
                # Thread doesn't have metadata; use operation_id if provided
                if not resolved_operation_id:
                    raise ValueError("operation_id is required when thread has no metadata")

        if not resolved_operation_id:
            raise ValueError("Operation ID not found")

        interrupted = await self._runtime.interrupt_operation(resolved_operation_id)

        if interrupted and thread_id:
            async with get_db_context() as session:
                stmt = (
                    update(Thread)
                    .where(Thread.id == thread_id, Thread.user_id == self.user_id)
                    .values(status="cancelled")
                )
                await session.execute(stmt)

        return {
            "success": interrupted,
            "operation_id": resolved_operation_id,
            "thread_id": thread_id,
        }
