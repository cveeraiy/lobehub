# Agent Runtime System Functional Specification

## Purpose

This document specifies the portable behavior of the core agent runtime. It is written so the architecture can be reimplemented in another language while preserving the same agent capabilities, runtime contracts, and operational semantics.

The implementation referenced by this specification is the current LobeHub agent stack:

- Agent runtime package: `packages/agent-runtime`
- Model provider runtime: `packages/model-runtime`
- Context engineering: `packages/context-engine`, `src/services/chat/mecha`, `src/server/modules/Mecha`
- Tool engineering: `packages/context-engine`, `src/helpers/toolEngineering`, `src/server/services/toolExecution`
- Server operation runtime: `src/server/services/agentRuntime`, `src/server/modules/AgentRuntime`
- Memory: `packages/memory-user-memory`, `packages/database/src/schemas/userMemories`, `src/server/services/memory/userMemory`
- Agent Signal: `packages/agent-signal`, `src/server/services/agentSignal`

Related portability specs:

- [Portable Design](./design.md)
- [Implementation Contract](./implementation-contract.md)
- [API Contract](./api-contract.md)
- [Runtime Event Protocol](./runtime-event-protocol.md)
- [Provider Adapter Specification](./provider-adapter-spec.md)
- [Persistence And DDL Specification](./persistence-ddl-spec.md)
- [UI Functional Specification](./ui-functional-spec.md)
- [Conformance Test Plan](./conformance-test-plan.md)

## Scope

The system shall support single-agent chat, graph-driven agents, multi-agent orchestration, tools, MCP tools, builtin tools, skills, memory, human intervention, task execution, context compression, streaming, server-side operation persistence, tracing, and background signal processing.

The system shall not require any specific programming language, UI framework, queue backend, database, or LLM provider. Those are adapters behind stable domain interfaces.

## Glossary

| Term                | Meaning                                                                                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Agent               | Stateless decision component. It reads runtime context plus state and returns the next instruction or instructions.                                                |
| Agent Runtime       | Stateful execution engine. It executes agent instructions, mutates state, emits events, and schedules the next context.                                            |
| Model Runtime       | Provider adapter layer. It normalizes LLM chat, streaming, tool-call, and embedding behavior across providers.                                                     |
| Context Engine      | Prompt/context assembly pipeline. It prepares messages for the model by injecting system role, tools, skills, memory, files, topic context, and dynamic variables. |
| Tool                | Callable capability exposed to the model or runtime. Tools may be builtin, MCP, local/client, server, markdown, or standalone.                                     |
| Skill               | Higher-level capability package with prompt content and optional associated tools.                                                                                 |
| MCP                 | Model Context Protocol integration for external tool servers.                                                                                                      |
| Memory              | Durable user memory stored outside the conversation and retrieved by semantic search or persona lookup.                                                            |
| Operation           | Durable execution instance with an `operationId`, state, stream, and scheduling metadata.                                                                          |
| Step                | One runtime execution turn: agent decides instruction, executor runs it, state/events/next context are produced.                                                   |
| Human Intervention  | Pause state requiring user approval, free-form input, or selection before runtime can continue.                                                                    |
| Graph Agent         | Agent implementation that drives execution through declarative graph states and transitions.                                                                       |
| Group Orchestration | Multi-agent supervisor/executor loop for speak, broadcast, delegate, and async task collaboration.                                                                 |
| Agent Signal        | Background semantic event pipeline for runtime, client, bot, and feedback events.                                                                                  |

## Core Functional Requirements

### F-001 Agent abstraction

The system shall define an agent as a stateless component with a `runner(context, state)` function.

The runner shall return either one instruction or an ordered list of instructions. Instructions must be serializable data.

The agent may optionally provide:

- custom instruction executors
- usage calculation
- cost calculation
- model runtime override
- local tool registry

The runtime must not depend on concrete agent classes. It must accept any object that implements the agent contract.

### F-002 Runtime instruction execution

The runtime shall execute serializable instructions produced by agents.

Supported instruction types:

| Instruction             | Required behavior                                                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `call_llm`              | Call model runtime with prepared messages, provider, model, and optional tools. Stream chunks and persist the assistant result. |
| `call_tool`             | Execute one tool call and append or update the corresponding tool message.                                                      |
| `call_tools_batch`      | Execute multiple tool calls in one step and merge all tool results without duplicating prior tool messages.                     |
| `resolve_aborted_tools` | Mark pending tool calls as cancelled or resolved after user abort.                                                              |
| `exec_task`             | Execute one async agent task, usually as a child thread or operation.                                                           |
| `exec_tasks`            | Execute multiple async tasks and report batch results.                                                                          |
| `exec_client_task`      | Dispatch one client-side task for desktop/local capabilities.                                                                   |
| `exec_client_tasks`     | Dispatch multiple client-side tasks.                                                                                            |
| `request_human_approve` | Pause for approval of pending tool calls.                                                                                       |
| `request_human_prompt`  | Pause for free-form user input.                                                                                                 |
| `request_human_select`  | Pause for single or multi-select user input.                                                                                    |
| `compress_context`      | Compress message history into a compact summary/baseline.                                                                       |
| `finish`                | End the operation with a standardized finish reason.                                                                            |

Instructions may include a `stepLabel` for display, tracing, and graph-node labeling.

### F-003 Runtime phases

The runtime context shall include a phase. Supported phases:

- `init`
- `user_input`
- `llm_result`
- `tool_result`
- `tools_batch_result`
- `task_result`
- `tasks_batch_result`
- `human_response`
- `human_approved_tool`
- `human_abort`
- `compression_result`
- `error`

The phase determines how the agent interprets the current payload and decides the next instruction.

### F-004 Runtime state

The runtime shall maintain serializable `AgentState`.

Required state domains:

- operation identity: `operationId`
- state machine status: `idle`, `running`, `waiting_for_human`, `done`, `error`, `interrupted`
- message list
- metadata map
- step count
- timestamps: created and last modified
- model runtime config
- tool manifests, tool executors, tool source map, active tool list
- immutable operation-level tool set snapshot
- pending human prompts, selects, or tool approvals
- intervention/security config
- usage and cost
- optional cost limits
- optional max steps
- optional force-finish flag
- optional interruption record
- optional activated step tools and skills

State must be portable across processes. A server implementation must be able to persist and reload it between steps.

### F-005 Runtime events

The runtime shall emit structured events.

Required events:

- `init`
- `llm_start`
- `llm_stream`
- `llm_result`
- `tool_pending`
- `tool_result`
- `human_approve_required`
- `human_prompt_required`
- `human_select_required`
- `done`
- `error`
- `interrupted`
- `resumed`
- `compression_complete`
- `compression_error`

Events must be streamable to clients and storable in execution traces.

### F-006 Finish reasons

The runtime shall complete with a normalized finish reason:

- `completed`
- `user_requested`
- `user_aborted`
- `max_steps_exceeded`
- `max_steps_completed`
- `cost_limit_exceeded`
- `timeout`
- `agent_decision`
- `queued_message_interrupt`
- `error_recovery`
- `system_shutdown`

### F-007 Default chat agent

The system shall provide a default general chat agent.

Required behavior:

1. On user input, call the LLM.
2. On LLM result with tool calls, determine whether each tool requires human intervention.
3. Execute safe tools immediately.
4. Pause for approval where required.
5. Feed tool results back to the LLM.
6. Repeat until the model returns no tool calls or the agent chooses to finish.
7. If context is too large and compression is enabled, request context compression.
8. If max step limit is exceeded, enter force-finish mode: allow currently pending tools to complete, strip future tools, and ask the model for a final answer.

### F-008 Graph agent

The system shall support graph-driven agent execution.

A graph shall contain:

- `name`
- optional `description`
- `entry` state id
- `terminal` state id
- `maxBacktracks`
- state map
- ordered transition list

Each graph state shall define:

- `type`: `agent` or `llm`
- `prompt`
- `outputSchema`

Graph behavior:

- The graph context must persist in agent state metadata.
- The first graph step initializes graph context using the latest user input.
- `agent` nodes delegate to the general chat agent with tools enabled and no forced JSON schema.
- After an `agent` node finishes, the graph agent must run an extra extraction LLM call with tools disabled to produce structured node output.
- `llm` nodes run one structured LLM call with tools disabled.
- Completed node outputs are stored by node id.
- Transitions are evaluated programmatically in order. First true transition wins.
- If no transition matches, the graph advances to the next state in declaration order.
- Backtracking is bounded by `maxBacktracks`.
- The whole graph finishes only when the terminal state completes.

Security requirement: if graph definitions are user-authored or otherwise untrusted, transition expressions must use a safe expression evaluator, not arbitrary code execution.

### F-009 Group orchestration

The system shall support multi-agent collaboration through a supervisor/executor loop.

Supervisor instructions:

- `call_supervisor`
- `call_agent`
- `parallel_call_agents`
- `exec_async_task`
- `exec_client_async_task`
- `batch_exec_async_tasks`
- `delegate`
- `finish`

Executor results:

- `init`
- `supervisor_decided`
- `agent_spoke`
- `agents_broadcasted`
- `task_completed`
- `tasks_completed`
- `delegated`

Supported collaboration decisions:

- `speak`: one agent responds
- `broadcast`: multiple agents respond in parallel
- `delegate`: control moves to another agent
- `execute_task`: one async task
- `execute_tasks`: multiple async tasks
- `finish`: end group orchestration

### F-010 Model provider abstraction

The system shall isolate provider-specific details in a model runtime.

The agent runtime shall request:

- chat completion
- streaming chat completion
- tool-call capable completion
- structured generation where supported or emulated
- embeddings for memory/search

Provider adapters shall normalize:

- message shape
- system/user/assistant/tool messages
- tool schema shape
- tool-call deltas and final calls
- reasoning/thinking content where available
- usage metadata
- provider errors

The agent runtime must not contain provider-specific protocol logic except through model runtime interfaces.

### F-011 Context engineering

Before LLM calls, the system shall assemble request context through a composable pipeline.

The context pipeline shall support:

- history truncation
- system role
- system date/time and timezone
- enabled tool manifests
- selected skills and activated skill content
- file contents and knowledge base references
- memory injection
- agent documents
- group context
- agent management context
- GTD plan and todos
- credentials context
- cron job context
- topic references
- page/editor context
- onboarding or eval context
- model/provider capabilities
- variable substitution

The context engine shall keep the agent logic independent from prompt assembly details.

### F-012 Tool system

The system shall support multiple tool source types:

- builtin tools
- MCP tools
- installed plugin tools
- skill-provided tools
- Klavis or external integration tools
- local/client tools
- server tools
- markdown or standalone tools where applicable

Each tool shall have:

- stable identifier
- API name
- JSON argument schema
- manifest metadata for prompting/UI
- executor binding
- source metadata
- optional human intervention policy
- optional runtime environment constraints

Tool execution shall route to the correct executor by source map and executor map.

### F-013 MCP support

The system shall treat MCP tools as first-class tool sources.

MCP requirements:

- discover MCP tool manifests
- normalize MCP schemas into model tool schemas
- route calls to the correct MCP server/session
- return tool results as normal tool messages
- preserve tool identifier/API name mapping
- support user or agent enablement rules

### F-014 Skill support

The system shall support skills as reusable capability packages.

Skill requirements:

- discover installed skills
- expose selected skills to the context engine
- inject skill prompt/content when activated
- track activated step skills
- allow skills to contribute tools where applicable
- distinguish user-selected skills from runtime-activated skills

### F-015 Memory

The system shall support durable user memory.

Memory layers:

- persona
- identity
- context
- experience
- preference
- activity

Creation paths:

- explicit memory tool writes
- background extraction workflows over chat topics or other sources
- persona writer/update workflow

Storage requirements:

- store base memory records
- store layer-specific records
- store embeddings for semantic retrieval
- store metadata, tags, source ids, timestamps, and access stats
- preserve user isolation

Retrieval paths:

- automatic topic memory retrieval before chat
- persona retrieval
- tool-based memory search during agent execution
- background extraction retrieval of relevant existing memories

Both general chat agents and graph agents shall consume memory through the same context and tool paths.

### F-016 Human intervention

The system shall support human-in-the-loop controls.

Approval modes:

- manual
- allow-list
- auto-run
- headless

Intervention inputs:

- global security audits
- dynamic intervention audits
- per-tool or per-API intervention policies
- user allow-list
- unknown tool guard
- security blacklist

Intervention outputs:

- execute immediately
- request approval
- skip blocked tool in headless mode
- stop after rejection
- reject and continue where supported

Paused operations must be resumable with enough state to execute approved tools without creating duplicate tool messages.

### F-017 Task execution

The system shall support spawning async tasks from an agent.

Task requirements:

- instruction
- description/title
- optional inherited messages
- optional timeout
- optional client/local execution flag
- result with success flag, content or error, thread id, and task message id

Task execution may create child threads, child operations, or client-side local operations depending on runtime environment.

### F-018 Server operation runtime

The system shall support durable server-side operation execution.

Required behavior:

- create operation metadata
- save initial `AgentState`
- schedule first and subsequent steps
- load state before each step
- atomically claim each step to avoid duplicate execution
- publish step start and step completion events
- save step results
- publish operation end when entering stream-terminal states
- support queue-backed and local/in-memory execution
- support abort/interruption
- support reconnect/resume via persisted operation id and stream

Stream-terminal states:

- `done`
- `error`
- `interrupted`
- `waiting_for_human`

`waiting_for_human` is terminal for the current stream but state-resumable through a later resume operation.

### F-019 Client runtime

The system may run the agent loop in the browser/desktop client when local tools or SPA-only state are required.

Client runtime requirements:

- create local agent state
- resolve enabled tools
- compute step context
- execute client/local tools
- send chat completions through client services where configured
- emit client runtime Agent Signal events
- bridge to server/gateway runtime where needed

### F-020 Gateway streaming

The system shall support gateway-style streaming for server operations.

Gateway requirements:

- start server operation
- stream operation events to client
- propagate operation id to message metadata
- support reconnect using persisted operation id
- forward human intervention responses
- forward client tool results when tools execute locally
- emit client gateway source events for Agent Signal

### F-021 Hooks and webhooks

The system shall expose lifecycle hooks.

Hook points:

- `beforeStep`
- `afterStep`
- `beforeToolCall`
- `afterToolCall`
- `onToolCallError`
- `beforeCompact`
- `afterCompact`
- `onCompactError`
- `beforeHumanIntervention`
- `afterHumanIntervention`
- `onStopByHumanIntervention`
- `beforeCallAgent`
- `afterCallAgent`
- `onCallAgentError`
- `onComplete`
- `onError`

Hooks may be local callbacks or serialized webhooks. Tool-call hooks may mock tool results in local/test mode.

### F-022 Context compression

The system shall support context compression.

Compression requirements:

- detect when message history exceeds token policy
- compress selected messages into a summary or summary group
- preserve enough context for future steps
- emit before/after/error hooks
- emit compression events
- continue execution from compressed baseline
- support incremental compression with existing summary

### F-023 Usage and cost tracking

The system shall track:

- LLM API call count
- LLM processing time
- input/output/total tokens
- tool call count
- per-tool call/error/time stats
- human approval/prompt/select counts
- human waiting time
- LLM cost by provider/model
- tool cost by tool
- total cost

The system shall support cost limits with actions:

- `stop`
- `warn`
- `interrupt`

### F-024 Tracing and observability

The system shall support execution snapshots.

Trace data should include:

- operation id
- step index
- step type
- baseline and delta messages
- context engineering input metadata
- LLM payload summary
- tool payloads and results
- user memory presence and optionally content
- Agent Signal events
- errors
- final status

Snapshots should be inspectable offline and should avoid storing unnecessarily large or sensitive payloads where possible.

### F-025 Agent Signal

The system shall support background semantic signals.

Source events include:

- agent execution completed
- agent execution failed
- runtime before step
- runtime after step
- agent user message
- bot message merged
- client runtime start/complete
- client gateway stream/error/step/runtime-end

Agent Signal requirements:

- normalize source events
- derive scope keys
- deduplicate events
- execute policies
- produce semantic signals
- execute resulting actions
- persist observability projection
- optionally hand off to async workflow

### F-026 Security

The system shall enforce security boundaries:

- user isolation in memory and operations
- authenticated server APIs
- tool approval policies
- security blacklist and dynamic audits
- local tool path-scope restrictions
- unknown tool guard
- SSRF-safe fetch for web access where applicable
- schema validation for tool arguments
- safe handling of provider errors
- safe graph transition evaluation for untrusted graphs

### F-027 Provider and tool schema normalization

The system shall normalize schemas before sending to providers.

Requirements:

- tool input schemas must be objects
- invalid or string schemas must be converted or filtered
- provider-specific tool schema constraints must be handled in model runtime/context builder
- non-object tool-call chunks must be ignored or sanitized before validation

### F-028 Error handling

The system shall classify and surface errors consistently.

Error handling requirements:

- state transitions to `error` on unrecoverable failures
- final stream event for terminal error states
- formatted user-visible chat error
- provider error classification
- retry-safe step claiming
- queue retry metadata
- abort-aware startup and step execution
- cleanup for failed startup
- no duplicate terminal stream event

### F-029 Portability

A compliant reimplementation shall preserve:

- domain contracts: agent, state, context, instruction, event, tool, memory, hook
- state machine semantics
- instruction execution semantics
- model runtime boundary
- context-engine boundary
- tool-source routing boundary
- human intervention semantics
- graph and group orchestration semantics
- traceability and durable operation behavior

It may replace:

- TypeScript with another language
- Zustand/SWR/React with any client state model
- TRPC with REST, gRPC, GraphQL, or message bus
- Redis with another durable state/stream backend
- Upstash/QStash with another queue/workflow system
- Drizzle/Postgres with another persistence layer, if vector search and transactional semantics are preserved

### F-030 Persistence schema

The system shall define durable persistence for user memory, persona, chat/task source material, agent operations, stream events, execution traces, tool/skill metadata, and Agent Signal events.

The current implementation stores core user memory in relational tables and uses Redis or in-memory stores for live agent operation state and streams. A portable implementation may choose a relational database, document database, Redis-like store, object storage, or a hybrid, but it must preserve the following logical schema.

#### Required memory tables

`user_memories` is the base memory table. It shall include:

- `id`
- `user_id`
- `memory_category`
- `memory_layer`
- `memory_type`
- `metadata`
- `tags`
- `title`
- `summary`
- `summary_vector_1024`
- `details`
- `details_vector_1024`
- `status`
- `accessed_count`
- `last_accessed_at`
- `captured_at`
- `created_at`
- `updated_at`

Required indexes:

- user id index
- vector index on summary vector
- vector index on details vector

`user_memories_contexts` shall include:

- `id`
- `user_id`
- `user_memory_ids`
- `metadata`
- `tags`
- `associated_objects`
- `associated_subjects`
- `title`
- `description`
- `description_vector`
- `type`
- `current_status`
- `score_impact`
- `score_urgency`
- `captured_at`
- `created_at`
- `updated_at`

Required indexes:

- user id index
- type index
- vector index on description vector

`user_memories_preferences` shall include:

- `id`
- `user_id`
- `user_memory_id`
- `metadata`
- `tags`
- `conclusion_directives`
- `conclusion_directives_vector`
- `type`
- `suggestions`
- `score_priority`
- `captured_at`
- `created_at`
- `updated_at`

Required indexes:

- user id index
- base memory id index
- vector index on conclusion directives vector

`user_memories_activities` shall include:

- `id`
- `user_id`
- `user_memory_id`
- `metadata`
- `tags`
- `type`
- `status`
- `timezone`
- `starts_at`
- `ends_at`
- `associated_objects`
- `associated_subjects`
- `associated_locations`
- `notes`
- `narrative`
- `narrative_vector`
- `feedback`
- `feedback_vector`
- `captured_at`
- `created_at`
- `updated_at`

Required indexes:

- user id index
- base memory id index
- type index
- status index
- vector index on narrative vector
- vector index on feedback vector

`user_memories_identities` shall include:

- `id`
- `user_id`
- `user_memory_id`
- `metadata`
- `tags`
- `type`
- `description`
- `description_vector`
- `episodic_date`
- `relationship`
- `role`
- `captured_at`
- `created_at`
- `updated_at`

Required indexes:

- user id index
- base memory id index
- type index
- vector index on description vector

`user_memories_experiences` shall include:

- `id`
- `user_id`
- `user_memory_id`
- `metadata`
- `tags`
- `type`
- `situation`
- `situation_vector`
- `reasoning`
- `possible_outcome`
- `action`
- `action_vector`
- `key_learning`
- `key_learning_vector`
- `score_confidence`
- `captured_at`
- `created_at`
- `updated_at`

Required indexes:

- user id index
- base memory id index
- type index
- vector index on situation vector
- vector index on action vector
- vector index on key learning vector

`user_memory_persona_documents` shall include:

- `id`
- `user_id`
- `profile`
- `tagline`
- `persona`
- `memory_ids`
- `source_ids`
- `metadata`
- `version`
- `captured_at`
- `created_at`
- `updated_at`

Required constraints and indexes:

- unique `(user_id, profile)`
- user id index

`user_memory_persona_document_histories` shall include:

- `id`
- `user_id`
- `persona_id`
- `profile`
- `snapshot_persona`
- `snapshot_tagline`
- `reasoning`
- `diff_persona`
- `diff_tagline`
- `snapshot`
- `summary`
- `edited_by`
- `memory_ids`
- `source_ids`
- `metadata`
- `previous_version`
- `next_version`
- `captured_at`
- `created_at`
- `updated_at`

Required indexes:

- persona id index
- user id index
- profile index

#### Required operation persistence

For durable server execution, the system shall persist or emulate these logical records:

`agent_runtime_operations`:

- `operation_id`
- `user_id`
- `agent_id`
- `topic_id`
- `thread_id`
- `task_id`
- `status`
- `agent_config`
- `model_runtime_config`
- `metadata`
- `total_steps`
- `total_cost`
- `created_at`
- `last_active_at`
- `expires_at`

`agent_runtime_states`:

- `operation_id`
- `state`
- `step_count`
- `status`
- `updated_at`
- `expires_at`

`agent_runtime_steps`:

- `id`
- `operation_id`
- `step_index`
- `status`
- `context`
- `next_context`
- `events`
- `execution_time_ms`
- `cost`
- `created_at`

`agent_runtime_stream_events`:

- `id`
- `operation_id`
- `step_index`
- `type`
- `data`
- `timestamp`
- `sequence`

`agent_runtime_step_locks`:

- `operation_id`
- `step_index`
- `lock_token`
- `expires_at`
- unique `(operation_id, step_index)`

Redis keys, queues, append-only logs, or document records are acceptable substitutes if they implement the same load, save, stream, history, cleanup, and atomic step-claim behavior.

#### Required trace persistence

The system shall persist execution snapshots or equivalent trace records with:

- operation id
- trace id
- user id
- agent id
- topic id
- provider/model
- started/completed timestamps
- completion reason
- total steps/tokens/cost
- error summary
- ordered step snapshots

Each step snapshot shall store enough data to reconstruct the step timeline, including baseline/delta messages, context phase, events, tool calls/results, token usage, cost, and errors.

#### Required source material

Memory retrieval and extraction require source conversation data. A portable implementation shall persist:

- users
- topics or conversation scopes
- messages with role, content, metadata, parent/tree links where used, and timestamps
- task/topic links when async tasks create child topics

At minimum, memory retrieval for a topic must be able to build a query from recent or summarized user messages.

#### Required agent definition tables

The system shall persist agent definitions:

`agents`:

- `id`
- `slug`
- `title`
- `description`
- `tags`
- `editor_data`
- `avatar`
- `background_color`
- `market_identifier`
- `plugins`
- `client_id`
- `user_id`
- `agency_config`
- `chat_config`
- `few_shots`
- `model`
- `params`
- `provider`
- `system_role`
- `tts`
- `virtual`
- `pinned`
- `opening_message`
- `opening_questions`
- `session_group_id`
- `created_at`
- `updated_at`

Required indexes and constraints:

- unique `(client_id, user_id)`
- unique `(slug, user_id)`
- user id index
- title/description indexes where search requires them

`agents_files`:

- `agent_id`
- `file_id`
- `user_id`
- `enabled`
- timestamps

`agents_knowledge_bases`:

- `agent_id`
- `knowledge_base_id`
- `user_id`
- `enabled`
- timestamps

#### Required group-agent tables

The system shall persist group chat definitions:

`chat_groups`:

- `id`
- `title`
- `description`
- `avatar`
- `background_color`
- `market_identifier`
- `content`
- `editor_data`
- `config`
- `client_id`
- `user_id`
- `group_id`
- `pinned`
- timestamps

`chat_groups_agents`:

- `chat_group_id`
- `agent_id`
- `user_id`
- `enabled`
- `order`
- `role`
- timestamps

#### Required model/provider configuration tables

The system shall persist provider and model configuration:

`ai_providers`:

- `id`
- `user_id`
- `name`
- `sort`
- `enabled`
- `fetch_on_client`
- `check_model`
- `logo`
- `description`
- `key_vaults`
- `source`
- `settings`
- `config`
- timestamps

`ai_models`:

- `id`
- `provider_id`
- `user_id`
- `display_name`
- `description`
- `organization`
- `enabled`
- `type`
- `sort`
- `pricing`
- `parameters`
- `config`
- `abilities`
- `context_window_tokens`
- `source`
- `released_at`
- `settings`
- timestamps

Primary keys shall include user scope, provider id, and model id as appropriate.

#### Required knowledge and file tables

The system shall persist files, documents, knowledge bases, chunks, and embeddings:

`global_files`:

- `hash_id`
- `file_type`
- `size`
- `url`
- `metadata`
- `creator`
- `created_at`
- `accessed_at`

`files`:

- `id`
- `user_id`
- `file_type`
- `file_hash`
- `name`
- `size`
- `url`
- `source`
- `parent_id`
- `client_id`
- `metadata`
- `chunk_task_id`
- `embedding_task_id`
- timestamps

`documents`:

- `id`
- `title`
- `description`
- `content`
- `file_type`
- `filename`
- `total_char_count`
- `total_line_count`
- `metadata`
- `pages`
- `source_type`
- `source`
- `file_id`
- `knowledge_base_id`
- `parent_id`
- `user_id`
- `client_id`
- `editor_data`
- `slug`
- timestamps

`knowledge_bases`:

- `id`
- `name`
- `description`
- `avatar`
- `type`
- `user_id`
- `client_id`
- `is_public`
- `settings`
- timestamps

`knowledge_base_files`:

- `knowledge_base_id`
- `file_id`
- `user_id`
- timestamps

`chunks`:

- `id`
- `text`
- `abstract`
- `metadata`
- `index`
- `type`
- `client_id`
- `user_id`
- timestamps

`unstructured_chunks`:

- `id`
- `text`
- `metadata`
- `index`
- `type`
- `parent_id`
- `composite_id`
- `client_id`
- `user_id`
- `file_id`
- timestamps

`embeddings`:

- `id`
- `chunk_id`
- `embeddings`
- `model`
- `client_id`
- `user_id`

`document_chunks`:

- `document_id`
- `chunk_id`
- `page_index`
- `user_id`
- `created_at`

Indexes shall support user filtering, file/document lookup, knowledge-base lookup, chunk lookup, and vector search.

#### Required tool and skill metadata

The system shall persist or be able to reconstruct:

- builtin tool registry
- installed plugin tools
- MCP server/tool registry
- skill registry and installed skills
- per-agent enabled tools and skills
- tool manifests, schemas, executor refs, and source refs

Static registries may live in code, but user-installed tools, MCP servers, and skills require durable configuration.

`agent_skills` shall persist user/builtin/market skills:

- `id`
- `name`
- `description`
- `identifier`
- `source`
- `manifest`
- `content`
- `editor_data`
- `resources`
- `zip_file_hash`
- `user_id`
- timestamps

`agent_documents` shall persist agent document policy and access:

- `id`
- `user_id`
- `agent_id`
- `document_id`
- `template_id`
- `access_self`
- `access_shared`
- `access_public`
- `policy_load`
- `policy`
- `policy_load_position`
- `policy_load_format`
- `policy_load_rule`
- `deleted_at`
- `deleted_by_user_id`
- `deleted_by_agent_id`
- `delete_reason`
- timestamps

#### Required task, schedule, and async job tables

The system shall persist async task and schedule state:

`async_tasks`:

- `id`
- `type`
- `status`
- `error`
- `inference_id`
- `user_id`
- `duration`
- `parent_id`
- `metadata`
- timestamps

`tasks`:

- `id`
- `identifier`
- `seq`
- `created_by_user_id`
- `created_by_agent_id`
- `assignee_user_id`
- `assignee_agent_id`
- `parent_task_id`
- `name`
- `description`
- `instruction`
- `status`
- `priority`
- `sort_order`
- `automation_mode`
- `heartbeat_interval`
- `heartbeat_timeout`
- `last_heartbeat_at`
- `schedule_pattern`
- `schedule_timezone`
- `total_topics`
- `max_topics`
- `current_topic_id`
- `context`
- `config`
- `error`
- `started_at`
- `completed_at`
- timestamps

`task_dependencies`:

- `id`
- `task_id`
- `depends_on_id`
- `user_id`
- `type`
- `condition`
- `created_at`

`task_documents`:

- `id`
- `task_id`
- `document_id`
- `user_id`
- `pinned_by`
- `created_at`

`task_topics`:

- `id`
- `task_id`
- `topic_id`
- `user_id`
- `seq`
- `operation_id`
- `status`
- `handoff`
- `review_passed`
- `review_score`
- `review_scores`
- `review_iteration`
- `reviewed_at`
- timestamps

`agent_cron_jobs`:

- `id`
- `agent_id`
- `group_id`
- `user_id`
- `name`
- `description`
- `enabled`
- `cron_pattern`
- `timezone`
- `content`
- `edit_data`
- `max_executions`
- `remaining_executions`
- `execution_conditions`
- `last_executed_at`
- `total_executions`
- timestamps

#### Required hook, intervention, and audit tables

The system shall persist or derive:

`agent_runtime_hooks`:

- `id`
- `user_id`
- `agent_id`
- `operation_id`
- `hook_type`
- `target`
- `config`
- `enabled`
- timestamps

`agent_runtime_interventions`:

- `id`
- `operation_id`
- `step_index`
- `user_id`
- `agent_id`
- `type`
- `status`
- `pending_tools`
- `prompt`
- `options`
- `response`
- `decision`
- `rejection_reason`
- timestamps

`agent_runtime_audit_events`:

- `id`
- `operation_id`
- `step_index`
- `user_id`
- `agent_id`
- `event_type`
- `severity`
- `subject`
- `payload`
- timestamps

These can be stored as standalone tables or embedded in operation state/trace if the implementation does not need queryable intervention/audit history.

#### Required Agent Signal persistence

The system shall persist or emulate:

- source events
- dedupe keys
- scope locks
- generated signals
- planned actions
- action results
- observability projections

Source event type strings and scope keys must be stable because they are used in dedupe, traces, and workflow payloads.

## Non-Functional Requirements

### Reliability

- Step execution must be idempotent at the operation/step boundary.
- Duplicate queue deliveries must not execute the same step twice.
- Terminal events must publish once.
- Tool messages must not duplicate across repeated batch steps.
- Runtime should recover cleanly from client reconnect.

### Performance

- Memory retrieval for normal chat send should be preloaded/cache-based where possible.
- Context assembly should avoid unnecessary network calls on the hot path.
- Tool batch execution should support parallelism where tools are independent.
- Streaming should start as soon as practical after LLM response begins.

### Observability

- Every operation should be identifiable by operation id.
- Every step should be indexed.
- Errors should include machine-readable and human-readable forms.
- Agent Signal and runtime traces should be correlatable.

### Extensibility

- New agent implementations must plug in through the `Agent` contract.
- New instruction executors must plug in by instruction type.
- New providers must plug in through model runtime adapters.
- New tool sources must plug in through manifest, executor, and source maps.
- New memory layers must define extraction, storage, search, and injection behavior.

### Compatibility

- Existing message histories must remain valid.
- Tool identifiers and API names must be stable once persisted.
- Source event names must be stable because they appear in traces, dedupe keys, and workflow payloads.
- Operation state should tolerate additional metadata fields.

## Acceptance Criteria For A Reimplementation

1. It can run the default chat loop with tool calls and final answer.
2. It can execute one and multiple tool calls without duplicate tool messages.
3. It can pause for human approval and resume approved tool execution.
4. It can execute with at least two different model providers through the same runtime interface.
5. It can inject memory into LLM context and write/search memory through a tool.
6. It can execute a graph with at least one `agent` node, one `llm` node, a transition, and a terminal node.
7. It can run a group orchestration flow with speak, broadcast, and finish.
8. It can persist operation state, resume from persisted state, and stream events.
9. It can compress context and continue execution.
10. It can emit hooks and trace snapshots for debugging.
11. It can emit and process Agent Signal source events.
12. It enforces security/intervention policies before executing tools.
