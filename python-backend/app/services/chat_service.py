"""Chat service — core chat loop with RAG + memory injection + streaming.

Orchestrates:
1. Retrieve relevant context (RAG chunks + user memories)
2. Inject system prompt / skill context
3. Call LLM (streaming or non-streaming)
4. Optionally execute tool calls

This is a high-level orchestrator; individual pieces are in their own
service modules.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import knowledge_service, llm_service, memory_service

logger = logging.getLogger(__name__)


async def build_context(
    session: AsyncSession,
    user_id: str,
    messages: list[dict[str, Any]],
    *,
    kb_ids: Optional[list[str]] = None,
    enable_memory: bool = True,
    embed_model: str = "openai/text-embedding-3-small",
    api_key: Optional[str] = None,
    rag_limit: int = 5,
    memory_limit: int = 5,
) -> list[dict[str, Any]]:
    """Build augmented context by prepending RAG chunks and memory to messages.

    The last user message is used as the query for retrieval.
    Returns a new messages list with injected system context.
    """
    # Extract the latest user message as query
    query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            query = content if isinstance(content, str) else str(content)
            break

    if not query:
        return messages

    context_parts: list[str] = []

    # ── RAG retrieval (parallel across KBs) ─────────────────────────────
    if kb_ids:
        try:
            query_vectors = await llm_service.embed(
                [query], model=embed_model, api_key=api_key
            )
            qv = query_vectors[0]

            async def _search_kb(kb_id: str) -> list[dict[str, Any]]:
                return await knowledge_service.vector_search(
                    session, user_id, qv, kb_id=kb_id, limit=rag_limit,
                )

            all_results = await asyncio.gather(
                *[_search_kb(kid) for kid in kb_ids],
                return_exceptions=True,
            )
            for results in all_results:
                if isinstance(results, BaseException):
                    logger.warning("RAG search for one KB failed: %s", results)
                    continue
                for r in results:
                    if r.get("text"):
                        context_parts.append(r["text"])
        except Exception:
            logger.warning("RAG retrieval failed", exc_info=True)

    # ── Memory retrieval ─────────────────────────────────────────────
    if enable_memory:
        try:
            mem_results = await memory_service.search_memories_by_text(
                session, user_id, query,
                model=embed_model, api_key=api_key,
                limit=memory_limit,
            )
            for m in mem_results:
                if m.get("summary"):
                    context_parts.append(f"[Memory] {m['summary']}")
        except Exception:
            logger.warning("Memory retrieval failed", exc_info=True)

    if not context_parts:
        return messages

    # ── Inject context as a system message ───────────────────────────
    context_text = "\n\n".join(context_parts)
    context_msg: dict[str, Any] = {
        "role": "system",
        "content": (
            "Below is relevant context retrieved from the knowledge base and user memories. "
            "Use it to inform your response.\n\n"
            f"{context_text}"
        ),
    }

    # Insert after the first system message (or at index 0)
    augmented = list(messages)
    insert_idx = 0
    for i, msg in enumerate(augmented):
        if msg.get("role") == "system":
            insert_idx = i + 1
            break

    augmented.insert(insert_idx, context_msg)
    return augmented


async def chat(
    session: AsyncSession,
    user_id: str,
    messages: list[dict[str, Any]],
    *,
    model: str = "openai/gpt-4o",
    stream: bool = True,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
    kb_ids: Optional[list[str]] = None,
    enable_memory: bool = True,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    max_tool_rounds: int = 10,
    extra_kwargs: Optional[dict[str, Any]] = None,
) -> Any | AsyncIterator[Any]:
    """Full chat pipeline: context augmentation → LLM call → tool loop.

    Parameters
    ----------
    session : AsyncSession
        DB session for RAG/memory lookups.
    user_id : str
        Authenticated user.
    messages : list[dict]
        Conversation history (OpenAI format).
    model : str
        litellm model string.
    stream : bool
        Stream response chunks.
    system_prompt : str | None
        Prepended as the first system message if set.
    kb_ids : list[str] | None
        Knowledge base IDs for RAG retrieval.
    enable_memory : bool
        Whether to inject user memory context.
    api_key, api_base : str | None
        Provider credentials override.
    tools : list[dict] | None
        OpenAI function-calling tool schemas.
    max_tool_rounds : int
        Max tool-call → LLM iterations (prevents infinite loops).

    Returns
    -------
    ModelResponse | AsyncIterator
    """
    # Prepend system prompt
    final_messages = list(messages)
    if system_prompt:
        final_messages.insert(0, {"role": "system", "content": system_prompt})

    # Augment with RAG + memory
    final_messages = await build_context(
        session, user_id, final_messages,
        kb_ids=kb_ids,
        enable_memory=enable_memory,
        api_key=api_key,
    )

    llm_kwargs: dict[str, Any] = {}
    if tools:
        llm_kwargs["tools"] = tools

    # ── Non-streaming tool loop ──────────────────────────────────────
    if not stream:
        for _round in range(max_tool_rounds):
            response = await llm_service.chat(
                final_messages,
                model=model,
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                api_base=api_base,
                extra_kwargs={**(extra_kwargs or {}), **llm_kwargs},
            )

            choice = response.choices[0]  # type: ignore[attr-defined]
            assistant_msg = choice.message

            # No tool calls → return final response
            if not getattr(assistant_msg, "tool_calls", None):
                return response

            # Append assistant message with tool_calls
            final_messages.append(assistant_msg.model_dump())

            # Execute each tool call
            for tc in assistant_msg.tool_calls:
                fn = tc.function
                try:
                    args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
                except json.JSONDecodeError:
                    args = {}

                from app.services.tool_execution import execute_tool_call_with_context
                result = await execute_tool_call_with_context(
                    fn.name, args, session=session, user_id=user_id,
                )
                final_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # Exhausted rounds — return last response without tools
        llm_kwargs.pop("tools", None)
        return await llm_service.chat(
            final_messages,
            model=model,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            api_base=api_base,
            extra_kwargs=extra_kwargs,
        )

    # ── Streaming tool loop ─────────────────────────────────────────
    return _stream_with_tool_loop(
        final_messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        api_base=api_base,
        tools=tools,
        max_tool_rounds=max_tool_rounds,
        extra_kwargs=extra_kwargs,
        session=session,
        user_id=user_id,
    )


async def _stream_with_tool_loop(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: Optional[float],
    max_tokens: Optional[int],
    api_key: Optional[str],
    api_base: Optional[str],
    tools: Optional[list[dict[str, Any]]],
    max_tool_rounds: int,
    extra_kwargs: Optional[dict[str, Any]],
    session: AsyncSession,
    user_id: str,
) -> AsyncIterator[Any]:
    """Streaming with tool-call loop.

    Yields SSE chunks to the client. When the model emits tool_calls:
    1. Accumulates the full tool_call deltas
    2. Executes them
    3. Re-calls the model with tool results (streaming again)
    4. Repeats up to max_tool_rounds
    """
    from app.services.tool_execution import execute_tool_call_with_context

    llm_kwargs: dict[str, Any] = {}
    if tools:
        llm_kwargs["tools"] = tools

    final_messages = list(messages)

    async def _generate():
        nonlocal final_messages

        for _round in range(max_tool_rounds):
            stream_response = await llm_service.chat(
                final_messages,
                model=model,
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                api_base=api_base,
                extra_kwargs={**(extra_kwargs or {}), **llm_kwargs},
            )

            # Accumulate content and tool_calls from the stream
            accumulated_content = ""
            tool_calls_acc: dict[int, dict[str, Any]] = {}  # index -> {id, name, arguments}
            has_tool_calls = False

            async for chunk in stream_response:
                # Yield chunk to client
                yield chunk

                # Extract delta
                if hasattr(chunk, "choices") and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        accumulated_content += delta.content
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        has_tool_calls = True
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": getattr(tc_delta, "id", None) or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc_delta.id:
                                tool_calls_acc[idx]["id"] = tc_delta.id
                            if hasattr(tc_delta, "function") and tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_acc[idx]["name"] = tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

            # If no tool calls, we're done
            if not has_tool_calls:
                return

            # Build assistant message with tool_calls
            assistant_tool_calls = []
            for idx in sorted(tool_calls_acc.keys()):
                tc = tool_calls_acc[idx]
                assistant_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })

            final_messages.append({
                "role": "assistant",
                "content": accumulated_content or None,
                "tool_calls": assistant_tool_calls,
            })

            # Execute tool calls
            for tc in assistant_tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}

                result = await execute_tool_call_with_context(
                    fn_name, args, session=session, user_id=user_id,
                )
                final_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # Loop: re-call LLM with tool results (stream again)

        # Exhausted rounds — final call without tools
        llm_kwargs.pop("tools", None)
        final_stream = await llm_service.chat(
            final_messages,
            model=model,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            api_base=api_base,
            extra_kwargs=extra_kwargs,
        )
        async for chunk in final_stream:
            yield chunk

    return _generate()
