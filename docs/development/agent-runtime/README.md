# Agent Runtime Portability Specification Set

## Purpose

This folder contains the language-neutral specification set for rebuilding the core agent platform in another backend language and another React-compatible frontend.

The specs are based on the current repository behavior, but avoid TypeScript, Next.js, TRPC, Zustand, Drizzle, and component-library lock-in wherever possible.

## Reading Order

Read the documents in this order:

| Order | Document                                                       | Purpose                                                                                             |
| ----- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1     | [System Functional Specification](./sfs.md)                    | Product and runtime behavior.                                                                       |
| 2     | [Portable Design](./design.md)                                 | Architecture, boundaries, and module responsibilities.                                              |
| 3     | [Implementation Contract](./implementation-contract.md)        | Runtime object shapes, instruction contracts, tool contracts, graph/group/memory/tracing contracts. |
| 4     | [API Contract](./api-contract.md)                              | HTTP/service boundary needed by UI, bots, clients, and workers.                                     |
| 5     | [Runtime Event Protocol](./runtime-event-protocol.md)          | Stream, persisted runtime events, ordering, replay, and reconnect semantics.                        |
| 6     | [Provider Adapter Specification](./provider-adapter-spec.md)   | LLM provider normalization, tool calling, streaming, embeddings, errors, and fallbacks.             |
| 7     | [Persistence And DDL Specification](./persistence-ddl-spec.md) | Portable relational schema guidance for all core agent features.                                    |
| 8     | [UI Functional Specification](./ui-functional-spec.md)         | React-portable UI behavior for all core agent features.                                             |
| 9     | [Conformance Test Plan](./conformance-test-plan.md)            | Test matrix and fixtures required to prove compatibility.                                           |

## What Is Required To Port

A compatible implementation needs all of the following:

- A backend runtime that implements the agent, instruction, operation, tool, MCP, skill, memory, graph, group, tracing, and persistence contracts.
- A model runtime/provider adapter layer that presents one normalized chat, tool-call, streaming, embedding, and error contract.
- A durable database model that can store chat entities, agent definitions, provider config, knowledge/RAG, memory, operations, events, tools, skills, tasks, hooks, signals, and audit/usage records.
- A UI that talks only to the generic API and event contracts, not to repository-specific stores or TRPC-specific details.
- A conformance suite that validates behavior using deterministic fake providers, fake tools, fake MCP servers, and replayable runtime events.

## Compatibility Levels

Use the levels from [Implementation Contract](./implementation-contract.md#compatibility-levels):

- **Level 0**: demo single-agent runtime with model selection, builtin skills, MCP, in-memory operations, streaming, and approval.
- **Level 1**: production portable runtime with durable operations, resumable events, context engine, cost/usage, errors, and conformance fixtures.
- **Level 2**: full feature parity with graph agents, group orchestration, task dispatch, memory, agent documents, Agent Signal, tracing, and cloud/local environments.

## Source Code Reference Map

| Capability               | Current repo reference                                                                                                                                    |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent runtime contracts  | `packages/agent-runtime/src`                                                                                                                              |
| Model provider adapters  | `packages/model-runtime/src`                                                                                                                              |
| Context assembly         | `packages/context-engine/src`, `src/services/chat/mecha`, `src/server/modules/Mecha`                                                                      |
| Tool engineering         | `src/helpers/toolEngineering`, `src/server/services/toolExecution`                                                                                        |
| MCP server router        | `src/server/routers/tools/mcp.ts`, `src/services/mcp.ts`                                                                                                  |
| Server operation runtime | `src/server/services/agentRuntime`, `src/server/modules/AgentRuntime`                                                                                     |
| Chat server router       | `src/server/routers/lambda/aiChat.ts`                                                                                                                     |
| Agent task router        | `src/server/routers/lambda/aiAgent.ts`                                                                                                                    |
| Memory router/service    | `src/server/routers/lambda/userMemories.ts`, `src/server/services/memory/userMemory`                                                                      |
| Database schemas         | `packages/database/src/schemas`                                                                                                                           |
| UI agent surfaces        | `src/features/AgentSetting`, `src/features/AgentBuilder`, `src/features/Conversation`, `src/features/MCP`, `src/features/SkillStore`, `src/routes/(main)` |
