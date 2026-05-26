# Agent Core Persistence And DDL Specification

## Purpose

This document turns the portable persistence requirements from the SFS and design docs into implementation-ready relational schema guidance.

It is not a literal dump of the current Drizzle schema. It is a portable DDL contract that can be implemented in PostgreSQL, MySQL, SQLite, SQL Server, or another durable database with equivalent constraints and indexes.

## Design Rules

- All user-owned rows must include `user_id`.
- All tables should include `created_at` and `updated_at` unless they are immutable append-only event tables.
- Use JSON columns for provider/tool/model-specific metadata that changes frequently.
- Use normalized join tables for many-to-many relationships.
- Use vector columns or a separate vector store for embeddings.
- Use append-only event tables for runtime operations, audit, and traces.
- Use soft delete only where product needs recovery; otherwise hard delete with proper cascade rules is acceptable.
- Persist immutable operation snapshots so provider/tool/skill changes do not mutate in-flight operations.

## SQL Type Mapping

| Logical type | PostgreSQL                | Portable fallback                 |
| ------------ | ------------------------- | --------------------------------- |
| ID           | `text` or `uuid`          | `varchar(191)`                    |
| Timestamp    | `timestamptz`             | ISO string or UTC datetime        |
| JSON         | `jsonb`                   | text JSON with validation in app  |
| Vector       | `vector(n)`               | separate vector DB or binary/blob |
| Boolean      | `boolean`                 | tinyint                           |
| Enum         | `text` + check constraint | varchar + application validation  |

## Core User And Settings Tables

```sql
create table users (
  id text primary key,
  username text,
  email text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table user_settings (
  user_id text primary key references users(id) on delete cascade,
  language_model jsonb,
  memory jsonb,
  preferences jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## Provider And Model Tables

```sql
create table ai_providers (
  id text primary key,
  user_id text references users(id) on delete cascade,
  name text not null,
  source text not null,
  enabled boolean not null default true,
  config jsonb,
  capabilities jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index ai_providers_user_id_idx on ai_providers(user_id);

create table ai_models (
  id text not null,
  provider_id text not null references ai_providers(id) on delete cascade,
  user_id text references users(id) on delete cascade,
  display_name text,
  enabled boolean not null default true,
  abilities jsonb not null default '{}'::jsonb,
  context_window integer,
  max_output integer,
  pricing jsonb,
  config jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (provider_id, id)
);

create index ai_models_user_id_idx on ai_models(user_id);
```

Credentials should be stored in a separate encrypted secret store or encrypted column table:

```sql
create table provider_secrets (
  id text primary key,
  user_id text references users(id) on delete cascade,
  provider_id text not null,
  secret_ref text,
  encrypted_payload bytea,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## Agent Tables

```sql
create table agents (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  title text,
  description text,
  avatar text,
  tags jsonb,
  config jsonb not null default '{}'::jsonb,
  chat_config jsonb,
  few_shots jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index agents_user_id_idx on agents(user_id);
create index agents_user_updated_at_idx on agents(user_id, updated_at desc);

create table agent_files (
  agent_id text not null references agents(id) on delete cascade,
  file_id text not null,
  user_id text not null references users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (agent_id, file_id)
);

create table agent_knowledge_bases (
  agent_id text not null references agents(id) on delete cascade,
  knowledge_base_id text not null,
  user_id text not null references users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (agent_id, knowledge_base_id)
);
```

## Session, Topic, Thread, And Message Tables

```sql
create table session_groups (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  name text,
  sort_order integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table sessions (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  group_id text references session_groups(id) on delete set null,
  title text,
  type text,
  config jsonb,
  pinned boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index sessions_user_updated_at_idx on sessions(user_id, updated_at desc);

create table agents_to_sessions (
  agent_id text not null references agents(id) on delete cascade,
  session_id text not null references sessions(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (agent_id, session_id)
);

create table topics (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  session_id text references sessions(id) on delete cascade,
  agent_id text references agents(id) on delete set null,
  group_id text,
  title text,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index topics_session_updated_at_idx on topics(session_id, updated_at desc);

create table threads (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  topic_id text references topics(id) on delete cascade,
  parent_thread_id text references threads(id) on delete set null,
  source_message_id text,
  agent_id text references agents(id) on delete set null,
  group_id text,
  title text,
  type text,
  status text,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index threads_topic_idx on threads(topic_id);
```

Messages:

```sql
create table messages (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  session_id text references sessions(id) on delete cascade,
  topic_id text references topics(id) on delete cascade,
  thread_id text references threads(id) on delete cascade,
  parent_id text references messages(id) on delete set null,
  agent_id text references agents(id) on delete set null,
  group_id text,
  role text not null,
  content text,
  editor_data jsonb,
  tools jsonb,
  tool_call_id text,
  plugin jsonb,
  provider text,
  model text,
  metadata jsonb,
  error jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index messages_topic_created_at_idx on messages(topic_id, created_at);
create index messages_thread_created_at_idx on messages(thread_id, created_at);
create index messages_session_created_at_idx on messages(session_id, created_at);
create index messages_parent_id_idx on messages(parent_id);
```

## Group Agent Tables

```sql
create table chat_groups (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  name text not null,
  description text,
  avatar text,
  config jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table chat_group_agents (
  chat_group_id text not null references chat_groups(id) on delete cascade,
  agent_id text not null references agents(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  role text,
  sort_order integer,
  config jsonb,
  created_at timestamptz not null default now(),
  primary key (chat_group_id, agent_id)
);

create index chat_group_agents_agent_idx on chat_group_agents(agent_id);
```

## Tool, MCP, Skill, And Document Tables

```sql
create table user_installed_plugins (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  identifier text not null,
  type text not null,
  manifest jsonb,
  settings jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, identifier, type)
);

create table mcp_servers (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  name text not null,
  type text not null,
  url text,
  command text,
  args jsonb,
  auth jsonb,
  headers jsonb,
  enabled boolean not null default true,
  manifest jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table agent_skills (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  identifier text not null,
  name text not null,
  source text,
  manifest jsonb,
  resources jsonb,
  zip_file_hash text,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);
```

Agent documents and skill resources:

```sql
create table agent_documents (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  agent_id text references agents(id) on delete cascade,
  skill_id text references agent_skills(id) on delete set null,
  title text,
  content text,
  content_type text,
  access_self integer,
  access_shared integer,
  access_public integer,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## File, Knowledge, And RAG Tables

```sql
create table files (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  name text not null,
  mime_type text,
  size bigint,
  url text,
  storage_key text,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table documents (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  file_id text references files(id) on delete set null,
  title text,
  content text,
  parser text,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table knowledge_bases (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  name text not null,
  description text,
  settings jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table knowledge_base_files (
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  file_id text not null references files(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (knowledge_base_id, file_id)
);

create table chunks (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  document_id text references documents(id) on delete cascade,
  file_id text references files(id) on delete set null,
  text text not null,
  chunk_index integer,
  metadata jsonb,
  created_at timestamptz not null default now()
);

create table embeddings (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  chunk_id text references chunks(id) on delete cascade,
  provider text,
  model text,
  dimensions integer,
  embedding vector,
  metadata jsonb,
  created_at timestamptz not null default now()
);
```

If the database does not support vectors, replace `embedding vector` with `{ vector_store_id, vector_ref }`.

## Memory Tables

The current implementation has layered memory tables. A portable schema may preserve separate layer tables or use one common `user_memories` table with layer-specific detail tables.

```sql
create table user_memories (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  layer text not null,
  title text,
  content text not null,
  summary text,
  tags jsonb,
  categories jsonb,
  status text,
  source jsonb,
  captured_at timestamptz,
  confidence numeric,
  importance numeric,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index user_memories_user_layer_idx on user_memories(user_id, layer);
create index user_memories_user_captured_at_idx on user_memories(user_id, captured_at desc);

create table user_memory_embeddings (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  memory_id text not null references user_memories(id) on delete cascade,
  provider text,
  model text,
  dimensions integer,
  embedding vector,
  created_at timestamptz not null default now()
);
```

Optional detail tables:

```sql
create table user_memory_contexts (
  memory_id text primary key references user_memories(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  context_type text,
  metadata jsonb
);

create table user_memory_preferences (
  memory_id text primary key references user_memories(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  preference_type text,
  value jsonb,
  metadata jsonb
);

create table user_memory_activities (
  memory_id text primary key references user_memories(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  activity_type text,
  starts_at timestamptz,
  ends_at timestamptz,
  metadata jsonb
);

create table user_memory_identities (
  memory_id text primary key references user_memories(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  identity_type text,
  relationship text,
  metadata jsonb
);

create table user_memory_experiences (
  memory_id text primary key references user_memories(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  experience_type text,
  score_confidence numeric,
  score_impact numeric,
  score_priority numeric,
  score_urgency numeric,
  metadata jsonb
);
```

Persona documents:

```sql
create table user_persona_documents (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  title text,
  content text,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table user_persona_document_histories (
  id text primary key,
  persona_document_id text not null references user_persona_documents(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  content text,
  diff jsonb,
  created_at timestamptz not null default now()
);
```

## Runtime Operation Tables

```sql
create table agent_operations (
  operation_id text primary key,
  user_id text not null references users(id) on delete cascade,
  agent_id text references agents(id) on delete set null,
  group_id text references chat_groups(id) on delete set null,
  session_id text references sessions(id) on delete set null,
  topic_id text references topics(id) on delete set null,
  thread_id text references threads(id) on delete set null,
  user_message_id text references messages(id) on delete set null,
  assistant_message_id text references messages(id) on delete set null,
  provider text not null,
  model text not null,
  status text not null,
  step_count integer not null default 0,
  initial_context jsonb not null,
  state jsonb not null,
  usage jsonb,
  cost jsonb,
  error jsonb,
  locked_by text,
  lock_expires_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index agent_operations_user_status_idx on agent_operations(user_id, status);
create index agent_operations_topic_idx on agent_operations(topic_id);
create index agent_operations_thread_idx on agent_operations(thread_id);

create table agent_operation_events (
  id text primary key,
  operation_id text not null references agent_operations(operation_id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  sequence integer not null,
  type text not null,
  phase text,
  step_index integer,
  payload jsonb not null,
  metadata jsonb,
  created_at timestamptz not null default now(),
  unique (operation_id, sequence)
);

create index agent_operation_events_operation_sequence_idx
  on agent_operation_events(operation_id, sequence);

create table agent_operation_steps (
  id text primary key,
  operation_id text not null references agent_operations(operation_id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  step_index integer not null,
  instruction_type text,
  step_label text,
  status text not null,
  input jsonb,
  output jsonb,
  error jsonb,
  usage jsonb,
  cost jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  unique (operation_id, step_index)
);
```

## Operation Tool Snapshot Tables

```sql
create table agent_operation_tools (
  id text primary key,
  operation_id text not null references agent_operations(operation_id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  original_identifier text not null,
  model_tool_name text not null,
  source text not null,
  manifest jsonb not null,
  executor_ref jsonb,
  created_at timestamptz not null default now(),
  unique (operation_id, model_tool_name)
);
```

Rules:

- This table is immutable after operation creation.
- It preserves tool name mapping even if installed tools change later.

## Human Intervention Tables

```sql
create table agent_operation_interventions (
  id text primary key,
  operation_id text not null references agent_operations(operation_id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  kind text not null,
  status text not null,
  prompt text,
  options jsonb,
  pending_tool_calls jsonb,
  response jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index agent_operation_interventions_operation_idx
  on agent_operation_interventions(operation_id);
```

## Tracing Tables

```sql
create table agent_trace_snapshots (
  id text primary key,
  operation_id text references agent_operations(operation_id) on delete set null,
  user_id text not null references users(id) on delete cascade,
  session_id text references sessions(id) on delete set null,
  topic_id text references topics(id) on delete set null,
  title text,
  summary text,
  snapshot jsonb not null,
  redaction_level text,
  created_at timestamptz not null default now()
);

create index agent_trace_snapshots_operation_idx on agent_trace_snapshots(operation_id);
```

## Task Tables

```sql
create table tasks (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  title text not null,
  description text,
  status text not null,
  priority text,
  due_at timestamptz,
  assignee_agent_id text references agents(id) on delete set null,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table task_dependencies (
  task_id text not null references tasks(id) on delete cascade,
  depends_on_task_id text not null references tasks(id) on delete cascade,
  user_id text not null references users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (task_id, depends_on_task_id)
);

create table async_tasks (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  task_id text references tasks(id) on delete set null,
  operation_id text references agent_operations(operation_id) on delete set null,
  status text not null,
  type text,
  input jsonb,
  output jsonb,
  error jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## Scheduled Agent Job Tables

```sql
create table agent_cron_jobs (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  agent_id text references agents(id) on delete cascade,
  title text,
  prompt text,
  schedule text not null,
  timezone text,
  enabled boolean not null default true,
  last_run_at timestamptz,
  next_run_at timestamptz,
  metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## Hooks, Audit, And Usage Tables

```sql
create table agent_runtime_hooks (
  id text primary key,
  user_id text references users(id) on delete cascade,
  scope text not null,
  event_type text not null,
  target text not null,
  config jsonb,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table agent_audit_events (
  id text primary key,
  user_id text references users(id) on delete cascade,
  operation_id text references agent_operations(operation_id) on delete set null,
  event_type text not null,
  actor_type text,
  actor_id text,
  payload jsonb,
  created_at timestamptz not null default now()
);

create table usage_records (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  operation_id text references agent_operations(operation_id) on delete set null,
  provider text,
  model text,
  input_tokens integer,
  output_tokens integer,
  total_tokens integer,
  cost_amount numeric,
  cost_currency text,
  metadata jsonb,
  created_at timestamptz not null default now()
);
```

## Agent Signal Tables

```sql
create table agent_signal_definitions (
  id text primary key,
  user_id text references users(id) on delete cascade,
  name text not null,
  source text not null,
  matcher jsonb not null,
  action jsonb not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table agent_signal_events (
  id text primary key,
  user_id text references users(id) on delete cascade,
  source text not null,
  type text not null,
  operation_id text references agent_operations(operation_id) on delete set null,
  agent_id text references agents(id) on delete set null,
  session_id text references sessions(id) on delete set null,
  topic_id text references topics(id) on delete set null,
  payload jsonb not null,
  occurred_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table agent_signal_runs (
  id text primary key,
  signal_definition_id text references agent_signal_definitions(id) on delete set null,
  source_event_id text references agent_signal_events(id) on delete cascade,
  user_id text references users(id) on delete cascade,
  status text not null,
  result jsonb,
  error jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);
```

## Bot Provider Tables

```sql
create table agent_bot_providers (
  id text primary key,
  user_id text not null references users(id) on delete cascade,
  agent_id text references agents(id) on delete cascade,
  platform text not null,
  application_id text,
  config jsonb,
  credentials_ref text,
  enabled boolean not null default true,
  runtime_status jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (platform, application_id)
);
```

## Required Constraints And Invariants

- `agent_operation_events.sequence` must be unique and contiguous per operation.
- `agent_operations.status` must be one of the runtime statuses.
- Terminal operations must not be resumed unless an explicit recovery mode is implemented.
- Message parent chains must remain within the same user.
- Group chats must not assume one `agent_id` per topic/thread.
- Operation tool snapshots must not change after operation start.
- Memory embeddings must record provider/model/dimensions.
- Provider credentials must never be stored in plain JSON config.

## Retention And Compaction

Recommended retention:

| Data                     | Retention                                                       |
| ------------------------ | --------------------------------------------------------------- |
| Messages, agents, memory | Until user deletes.                                             |
| Operation state          | 30 to 90 days or while message exists.                          |
| Runtime event deltas     | Compact after terminal event if final state is reconstructable. |
| Trace snapshots          | Configurable, often shorter than messages.                      |
| Audit/usage              | Product/compliance-defined.                                     |
| Provider raw responses   | Avoid storing by default; store redacted traces only.           |
