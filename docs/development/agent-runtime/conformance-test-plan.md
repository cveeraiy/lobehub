# Agent Runtime Conformance Test Plan

## Purpose

This document defines the test suite needed to prove that a reimplementation is compatible with the portable agent runtime specs.

The conformance suite should run against any language implementation through public APIs and normalized runtime events. It should not import repository internals.

## Test Harness Requirements

The test harness needs:

- A clean test tenant/user.
- A fake deterministic provider adapter.
- A fake streaming provider adapter.
- A fake embedding provider.
- A fake builtin tool registry.
- A fake MCP HTTP server.
- A fake skill package.
- A test database or isolated schema.
- Runtime event replay access.
- Ability to force provider/tool errors.

## Compatibility Levels

### Level 0 Required Tests

- Send single-agent chat message.
- Select provider/model.
- Stream assistant text.
- Execute one builtin tool.
- Execute one MCP tool.
- Activate one skill.
- Request and submit tool approval.
- Persist final assistant message.

### Level 1 Required Tests

- Persist operation state.
- Replay events after reconnect.
- Resume operation after human intervention.
- Normalize provider tool arguments.
- Handle provider errors.
- Track usage/cost.
- Compress context when instructed.
- Store operation tool snapshot.
- Pass all API schema validation tests.

### Level 2 Required Tests

- Graph agent execution.
- Group orchestration.
- Async/client task dispatch.
- Memory search and injection.
- Memory extraction.
- Knowledge/RAG retrieval.
- Agent Signal ingestion/run.
- Trace snapshot creation.
- Bot/platform bridge execution where implemented.

## Fixture: Deterministic Provider

Fake provider behavior:

| Input marker          | Provider output                              |
| --------------------- | -------------------------------------------- |
| `TEXT_ONLY`           | Streams `Hello`, ` world`, `.`               |
| `CALL_TOOL:name,args` | Emits one tool call with supplied name/args. |
| `CALL_TWO_TOOLS`      | Emits two parallel tool calls.               |
| `REASONING`           | Streams reasoning deltas and final text.     |
| `INVALID_TOOL_JSON`   | Emits malformed final tool arguments.        |
| `CONTEXT_TOO_LONG`    | Fails with context window error.             |
| `RATE_LIMIT`          | Fails with retryable rate limit.             |
| `STRUCTURED_OBJECT`   | Returns JSON object matching schema.         |

The fake provider must produce stable token usage so assertions can verify usage/cost aggregation.

## Fixture: Fake Tools

Required tools:

```ts
weather.get_current({ city: string }) -> { city, temperature, condition }
todo.create({ title: string, items: string[] }) -> { todoId, title, count }
danger.delete_file({ path: string }) -> approval required
error.always_fail({ message: string }) -> throws TOOL_EXECUTION_ERROR
```

Assertions:

- Tool manifests convert to valid model tool schema.
- Model-facing names map back to original identifiers.
- Tool arguments are parsed into objects.
- Tool results are appended as tool messages.
- Approval-required tools pause the operation.
- Rejected tools emit cancelled tool events.

## Fixture: Fake MCP Server

The MCP server must support:

- `listTools`
- `listResources`
- `listPrompts`
- `callTool`

Tools:

```ts
mcp.echo({ text: string }) -> { text }
mcp.file({ name: string, content: string }) -> content block with file artifact
mcp.fail({}) -> error
```

Assertions:

- HTTP MCP tools are discoverable.
- Stdio MCP is rejected in web-only environment.
- Tool results with artifacts are normalized into file/artifact references.
- MCP failures use `MCP_CONNECTION_ERROR` or `TOOL_EXECUTION_ERROR`.

## Fixture: Fake Skill

Skill manifest:

- identifier: `test.trip_planner`
- prompt/reference: trip planning instructions
- tool: `todo.create`
- resource: `packing-list.md`

Assertions:

- Skill appears in skill listing.
- Skill activation injects prompt/reference into context.
- Skill tools become available in operation tool set.
- Skill activation event is emitted.

## API Contract Tests

### Chat

1. Create an agent.
2. Create or resolve chat context.
3. Send `TEXT_ONLY`.
4. Assert user and assistant messages are persisted.
5. Assert operation reaches `done`.
6. Assert final assistant message content is `Hello world.`.

### New Topic And Thread

1. Send a message with `newTopic`.
2. Assert new topic exists and is returned.
3. Send a message with `newThread`.
4. Assert thread exists and message query can fetch thread messages.

### Group Client Task Thread

1. Create group with supervisor and worker agents.
2. Create client group task thread for worker.
3. Assert thread agent is worker agent.
4. Assert query returns group context without incorrectly filtering by supervisor agent.

## Runtime Event Tests

### Text Streaming Order

Expected event sequence:

```text
operation.created
operation.started
step.started
llm.started
llm.text_delta
llm.text_delta
llm.text_delta
llm.completed
step.completed
operation.completed
```

Assertions:

- Sequence numbers are contiguous.
- Terminal event is last.
- Replay after sequence `0` returns the same persisted events.
- UI can reconstruct final message from events.

### Tool Call Flow

Expected event sequence:

```text
llm.tool_call_delta*
llm.completed
tool.call_started
tool.call_completed
step.completed
step.started
llm.started
llm.text_delta*
operation.completed
```

Assertions:

- Tool call has stable `toolCallId`.
- Tool start/completion reference the original identifier.
- Tool result is visible in runtime state.

### Human Approval Flow

1. Provider emits `danger.delete_file`.
2. Runtime emits `human.approval_requested`.
3. Operation status becomes `waiting_for_human`.
4. Submit approval.
5. Runtime emits `human.response_received`.
6. Tool executes.
7. Operation completes.

Reject path:

- Submit rejection.
- Tool emits `tool.call_cancelled`.
- Operation continues or finishes with clear reason.

### Reconnect Replay

1. Start streaming operation.
2. Disconnect after first text delta.
3. Replay from last received sequence.
4. Attach to live stream.
5. Assert no duplicate final text when client applies event IDs/sequences.

## Provider Adapter Tests

### Tool Schema Normalization

Inputs:

- missing schema
- string schema containing JSON
- invalid string schema
- root array schema
- schema with unsupported provider keyword

Assertions:

- Provider receives object schema.
- Invalid schema does not crash chat startup.
- Unsupported keywords are dropped or produce structured validation error.

### Bedrock/Anthropic-Style Tool Arguments

Assertions:

- Tool input schema is object, not string.
- Tool arguments are object at executor boundary.
- Top-level string arguments fail with `TOOL_ARGUMENT_PARSE_ERROR`, not an unhandled schema exception.

### Error Mapping

Force:

- missing API key
- model not found
- rate limit
- context window exceeded
- content filter

Assertions:

- Error codes match [Provider Adapter Specification](./provider-adapter-spec.md).
- Retryable is true only for retryable failures.
- Operation terminal event includes normalized error.

## Memory Tests

### Memory Search And Injection

1. Insert identity memory: `User likes window seats`.
2. Insert preference memory: `User prefers vegetarian food`.
3. Ask prompt requiring travel planning.
4. Assert memory search event includes relevant records.
5. Assert context assembled event marks `memoryIncluded`.
6. Assert provider receives injected memory text.

### Memory Extraction

1. Send message: `I live in Austin and prefer morning flights`.
2. Run memory extraction.
3. Assert identity/preference records created or updated.
4. Assert embeddings are created with provider/model/dimensions.
5. Assert query APIs return records by layer and tags.

### Memory Re-Embedding

1. Change embedding model.
2. Run re-embed.
3. Assert embedding metadata updated.
4. Assert semantic search still returns expected records.

## Knowledge/RAG Tests

1. Upload test document.
2. Parse and chunk document.
3. Embed chunks.
4. Attach knowledge base to agent.
5. Ask a question answered only by the document.
6. Assert retrieved chunks are injected into context.
7. Assert response contains citation/source metadata where product supports it.

## Graph Agent Tests

Fixture graph:

```text
start -> classify -> tool_or_answer
tool_or_answer -> call_tool -> answer
tool_or_answer -> answer
answer -> finish
```

Assertions:

- Node transitions are deterministic.
- Graph state is persisted in operation state.
- Tool branch executes when classifier selects tool path.
- Finish node emits operation terminal event.

## Group Orchestration Tests

Scenario:

- Supervisor receives user request.
- Supervisor delegates research to worker A.
- Supervisor delegates todo creation to worker B.
- Workers return results.
- Supervisor synthesizes final answer.

Assertions:

- Group events identify speaker/delegate agent.
- Worker task threads are created.
- Parent/child relationships are persisted.
- Final group message references outputs from workers.

## Task Tests

### Async Task

1. Create task.
2. Start async task run.
3. Assert status transitions pending -> running -> succeeded.
4. Assert operation/task link exists.

### Client Task

1. Request client-side task.
2. Assert server creates thread but does not execute local action.
3. Client reports result.
4. Runtime continues.

## Trace Tests

1. Run operation with tracing enabled.
2. Assert snapshot exists.
3. Assert snapshot contains operation state, steps, events, context summary, provider/model, tool set, usage.
4. Assert secrets and provider keys are redacted.

## Database Invariant Tests

Required checks:

- Deleting user cascades user-owned rows.
- Operation events have unique `(operation_id, sequence)`.
- Operation tool snapshots are immutable after operation start.
- Message parent references do not cross users.
- Group thread queries include multi-agent messages.
- Memory embeddings record dimensions.
- Provider secrets are not present in plain provider config.

## UI Acceptance Tests

The React-portable UI must pass:

- Agent list loads and empty state renders.
- Chat loads existing messages.
- Sending message shows optimistic user message and streaming assistant message.
- Tool call block transitions loading -> success/error.
- Approval panel appears for approval-required tool.
- MCP server list handles loading/error/empty.
- Skill list handles missing/empty builtin arrays without crashing.
- Memory page can filter by layer/tag/search.
- Provider/model selector disables unsupported models.
- Runtime reconnect replays missed events without duplicating text.

## Performance And Reliability Tests

Minimum scenarios:

- 100-message conversation context assembly.
- 10 parallel tool calls.
- 1,000 persisted runtime events replayed in pages.
- Provider stream disconnect and retry.
- MCP timeout.
- Memory search over at least 10,000 records if memory is enabled.
- RAG search over at least 100,000 chunks if knowledge is enabled.

## Test Output

Each conformance run should produce:

```ts
interface ConformanceReport {
  implementation: string;
  version: string;
  compatibilityLevel: 0 | 1 | 2;
  passed: number;
  failed: number;
  skipped: number;
  failures: Array<{
    testId: string;
    message: string;
    details?: unknown;
  }>;
  createdAt: string;
}
```

The report should be saved as JSON and optionally rendered as Markdown for review.
