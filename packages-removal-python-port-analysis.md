# Packages Removal vs Python Port Analysis

Generated: 2026-05-22

This document starts the package-by-package removal analysis for TypeScript packages under `packages/`.
It focuses on whether each package has been ported to `python-backend/` and whether it is currently removable from the TS workspace.

Related source material:

- `.agents/skills/ethos-repo-migration/SKILL.md`
- `.agents/skills/python-backend/SKILL.md`
- `.agents/skills/hono-python-rest-parity/SKILL.md`
- `.agents/skills/bot-python-migration/SKILL.md`
- Existing package-level overlap report: `package-python-backend-analysis.md`

## Decision Model

Python parity and TS removal are separate decisions.

| Status                         | Meaning                                                                                                                         |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `removed`                      | The Python-equivalent package was removed from the TS workspace.                                                                |
| `ported-blocked-by-ts-imports` | Python has equivalent backend behavior, but current TS code still imports the package directly.                                 |
| `partial-port`                 | Python has some equivalent service/router/tool behavior, but coverage or contract parity needs a focused audit before deletion. |
| `not-python-owned`             | Package is frontend, Electron, browser/client, shared UI, or build-time TS surface that Python should not replace.              |
| `keep-shared-contract`         | Package contains TS types, constants, schema ownership, prompts, or utilities still required by the SPA or TS tooling.          |

Removal rule: do not delete a package only because Python has an overlap. Delete only after all direct imports, workspace dependencies, runtime entrypoints, tests, and docs that require that package are removed or replaced.

## Highest Priority Removal Candidates

These packages have been removed from the TS workspace.

| Order | Package                         | Former TS blockers                                                                           | Python evidence                                                                                                                                  | Status                                                                                                  |
| ----- | ------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| 1     | `@lobechat/eval-dataset-parser` | Imported by `src/server/routers/lambda/agentEval.ts`.                                        | `python-backend/tests/test_agent_eval_dataset_parser.py` covers CSV, JSON, and JSONL parsing through `python-backend/app/routers/agent_eval.py`. | Removed; TS route now has local CSV/JSON/JSONL fallback and rejects XLSX with a Python-backend message. |
| 2     | `@lobechat/chat-adapter-line`   | Imported by `src/server/routers/lambda/agentBotProvider.ts` and TS bot platform client code. | `python-backend/app/services/bot/platforms/line/*` plus `python-backend/tests/test_line_client.py` and bot platform tests.                       | Removed; TS bot platform registry no longer registers LINE.                                             |
| 3     | `@lobechat/chat-adapter-feishu` | Imported by TS bot message router/runtime and Feishu platform client code.                   | `python-backend/app/services/bot/platforms/feishu/*` plus `python-backend/tests/test_feishu_client.py`.                                          | Removed; TS bot platform registry no longer registers Feishu/Lark.                                      |
| 4     | `@lobechat/chat-adapter-qq`     | Imported by TS bot message router/runtime and QQ platform client code.                       | `python-backend/app/services/bot/platforms/qq/*` plus `python-backend/tests/test_qq_client.py`.                                                  | Removed; TS bot platform registry no longer registers QQ.                                               |
| 5     | `@lobechat/chat-adapter-wechat` | Imported by TS bot message router/runtime and `agentBotProvider` QR helpers.                 | `python-backend/app/services/bot/platforms/wechat/*` plus `python-backend/tests/test_wechat_client.py`.                                          | Removed; TS bot platform registry no longer registers WeChat.                                           |
| 6     | `@lobechat/openapi`             | Mounted from `src/hono-server/routes/api.ts`.                                                | Python has OpenAPI-related routers and `hono-python-rest-parity-report.md`; `python-backend/tests/test_openapi_workflow_parity.py` exists.       | Removed; Hono no longer mounts `@lobechat/openapi` for `/api/v1/*`.                                     |

## Package Matrix

| Package                                      | Python port status | Removal readiness              | Notes                                                                                                                                                                                                 |
| -------------------------------------------- | ------------------ | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `@lobechat/agent-gateway-client`             | `partial-port`     | `not-python-owned`             | Browser-compatible WebSocket client. Python has agent stream/runtime endpoints, but this package is a client/protocol helper still used by SPA/server gateway code.                                   |
| `@lobechat/agent-manager-runtime`            | `partial-port`     | `ported-blocked-by-ts-imports` | Python has agent/AI-agent services, but TS built-in agent builder and management tools import this package directly. Remove only after those TS executors are retired.                                |
| `@lobechat/agent-runtime`                    | `partial-port`     | `ported-blocked-by-ts-imports` | Python has `app/services/agent_runtime`, `agent_runtime_hooks`, and `ai_agent`, but TS agent runtime remains widely imported across SPA/server/tests. Requires a dedicated agent-runtime parity plan. |
| `@lobechat/agent-signal`                     | `partial-port`     | `ported-blocked-by-ts-imports` | Python has `app/services/agent_signal` and router/test coverage, but shared TS contracts and producer helpers are still imported by TS Agent Signal services and observability code.                  |
| `@lobechat/agent-templates`                  | `partial-port`     | `keep-shared-contract`         | Python may mirror defaults, but TS package is template data consumed by database/onboarding/tool paths. Not a standalone backend implementation to delete first.                                      |
| `@lobechat/agent-tracing`                    | `partial-port`     | `ported-blocked-by-ts-imports` | Python has runtime/Langfuse tracing hooks, but TS tracing store/workflow code still imports this package. Defer until tracing ownership is clarified.                                                 |
| `@lobechat/builtin-agents`                   | `partial-port`     | `keep-shared-contract`         | Built-in agent definitions and default bindings remain TS data used by SPA and database setup. Python system-agent parity does not make this immediately removable.                                   |
| `@lobechat/builtin-skills`                   | `partial-port`     | `keep-shared-contract`         | Python has skill services, but TS skill manifests/default resources remain referenced by SPA/server code.                                                                                             |
| `@lobechat/builtin-tool-activator`           | `partial-port`     | `ported-blocked-by-ts-imports` | Python has `app/tools/activator.py`; TS package still supplies manifests, render/inspection contracts, and executor registration.                                                                     |
| `@lobechat/builtin-tool-agent-builder`       | `partial-port`     | `ported-blocked-by-ts-imports` | Python agent services overlap, but TS tool package is still imported by `builtin-tools`, `builtin-agents`, and executor code.                                                                         |
| `@lobechat/builtin-tool-agent-documents`     | `partial-port`     | `ported-blocked-by-ts-imports` | Python has agent document routers, VFS service, and `app/tools/agent_documents_tool.py`. TS UI/runtime package still feeds SPA tool rendering and server runtimes.                                    |
| `@lobechat/builtin-tool-agent-management`    | `partial-port`     | `ported-blocked-by-ts-imports` | Python agents and AI-agent routers overlap. TS built-in tool registry still imports the package.                                                                                                      |
| `@lobechat/builtin-tool-agent-marketplace`   | `partial-port`     | `ported-blocked-by-ts-imports` | Python market routers exist, but TS package still provides tool UI/runtime registration.                                                                                                              |
| `@lobechat/builtin-tool-brief`               | `removed`          | `removed`                      | Python has `briefs` router/service and `brief_tool.py`. The remaining TS legacy identifier/manifest contract now lives in `@lobechat/builtin-tools`.                                                  |
| `@lobechat/builtin-tool-calculator`          | `removed`          | `removed`                      | Python `app/tools/calculator.py` owns calculator execution via SymPy/Pint. The remaining TS manifest and REST-backed executor contract now lives in `@lobechat/builtin-tools`.                        |
| `@lobechat/builtin-tool-claude-code`         | `partial-port`     | `not-python-owned`             | Primarily heterogeneous-agent/client UI. Python does not own Claude Code/Electron execution in the same way.                                                                                          |
| `@lobechat/builtin-tool-cloud-sandbox`       | `partial-port`     | `ported-blocked-by-ts-imports` | Python has `cloud_sandbox` router/service. TS package still owns client inspectors/renders and executor wiring.                                                                                       |
| `@lobechat/builtin-tool-creds`               | `partial-port`     | `ported-blocked-by-ts-imports` | Python key vault/API routes overlap, but TS package still contributes tool definitions and executor paths.                                                                                            |
| `@lobechat/builtin-tool-cron`                | `removed`          | `removed`                      | Python has agent cron job router and task scheduler services. The remaining TS manifest/runtime/executor contract now lives in `@lobechat/builtin-tools`.                                             |
| `@lobechat/builtin-tool-group-agent-builder` | `partial-port`     | `ported-blocked-by-ts-imports` | Python chat group/AI-agent services overlap. TS group-agent builder still imports agent-manager runtime and UI pieces.                                                                                |
| `@lobechat/builtin-tool-group-management`    | `partial-port`     | `ported-blocked-by-ts-imports` | Python chat groups/tasks overlap, but TS tool UI/runtime still active.                                                                                                                                |
| `@lobechat/builtin-tool-gtd`                 | `partial-port`     | `ported-blocked-by-ts-imports` | Python has tasks service and `gtd_tool.py`; TS package remains in built-in tools and agents.                                                                                                          |
| `@lobechat/builtin-tool-knowledge-base`      | `partial-port`     | `ported-blocked-by-ts-imports` | Python has knowledge/files/chunks services. TS package still owns tool UI/runtime registration.                                                                                                       |
| `@lobechat/builtin-tool-lobe-agent`          | `removed`          | `removed`                      | Python has `lobe_agent_tool.py` and AI-agent service. The remaining TS visual-media manifest/runtime/executor contract now lives in `@lobechat/builtin-tools`.                                        |
| `@lobechat/builtin-tool-local-system`        | `not-python-owned` | `not-python-owned`             | Desktop/local file and Electron IPC execution. Python backend should not own most of this package.                                                                                                    |
| `@lobechat/builtin-tool-memory`              | `partial-port`     | `ported-blocked-by-ts-imports` | Python has user memory router/service and `memory_tool.py`; TS package still owns tool UI/runtime and prompt wiring.                                                                                  |
| `@lobechat/builtin-tool-message`             | `partial-port`     | `ported-blocked-by-ts-imports` | Python has messages/chat/bot services. TS package still drives message tool runtime and bot adapter imports.                                                                                          |
| `@lobechat/builtin-tool-notebook`            | `partial-port`     | `ported-blocked-by-ts-imports` | Python has notebook router and `notebook_tool.py`; TS notebook tool UI/runtime remains in active use.                                                                                                 |
| `@lobechat/builtin-tool-page-agent`          | `partial-port`     | `not-python-owned`             | Mostly page/editor runtime integration and UI. Python parity needs separate page/document execution decision.                                                                                         |
| `@lobechat/builtin-tool-remote-device`       | `partial-port`     | `ported-blocked-by-ts-imports` | Device proxy/runtime still exists in TS. Python device router does not make the client/device package removable yet.                                                                                  |
| `@lobechat/builtin-tool-skill-maintainer`    | `removed`          | `removed`                      | Python has `skill_maintainer` router/service and parity test. TS hidden manifest registration was removed from the built-in tool aggregator.                                                          |
| `@lobechat/builtin-tool-skill-store`         | `partial-port`     | `ported-blocked-by-ts-imports` | Python has skill/market services and `skill_store.py`; TS UI/runtime still imported.                                                                                                                  |
| `@lobechat/builtin-tool-skills`              | `partial-port`     | `ported-blocked-by-ts-imports` | Python has skill engine and `skills.py`; TS package remains in tool registry and client renders.                                                                                                      |
| `@lobechat/builtin-tool-task`                | `removed`          | `removed`                      | Python has tasks router/service and `task_tool.py`. The remaining TS task manifest/list/executor contract now lives in `@lobechat/builtin-tools`.                                                     |
| `@lobechat/builtin-tool-topic-reference`     | `removed`          | `removed`                      | Python has topics router and `topic_reference.py`. The remaining TS manifest/identifier/executor wrapper now lives in `@lobechat/builtin-tools`.                                                      |
| `@lobechat/builtin-tool-user-interaction`    | `partial-port`     | `ported-blocked-by-ts-imports` | Python AI-agent human intervention overlaps. TS UI/intervention handlers remain active.                                                                                                               |
| `@lobechat/builtin-tool-web-browsing`        | `partial-port`     | `ported-blocked-by-ts-imports` | Python has web search router/tools and URL crawler. TS package still owns client render/portal/runtime behavior.                                                                                      |
| `@lobechat/builtin-tool-web-onboarding`      | `removed`          | `removed`                      | Python onboarding REST/service owns document patch semantics. The remaining TS manifest/runtime utility/intervention contract now lives in `@lobechat/builtin-tools`.                                 |
| `@lobechat/builtin-tools`                    | `partial-port`     | `not-python-owned`             | TS aggregator for renders, inspectors, identifiers, and interventions. Python has separate server-side registry only.                                                                                 |
| `@lobechat/chat-adapter-feishu`              | `removed`          | `removed`                      | Python Feishu platform client and tests exist. TS package and TS platform implementation removed.                                                                                                     |
| `@lobechat/chat-adapter-line`                | `removed`          | `removed`                      | Python LINE platform client and tests exist. TS package and TS platform implementation removed.                                                                                                       |
| `@lobechat/chat-adapter-qq`                  | `removed`          | `removed`                      | Python QQ platform client and tests exist. TS package and TS platform implementation removed.                                                                                                         |
| `@lobechat/chat-adapter-wechat`              | `removed`          | `removed`                      | Python WeChat platform client and tests exist. TS package and TS platform implementation removed.                                                                                                     |
| `@lobechat/config`                           | `partial-port`     | `keep-shared-contract`         | Python has `app/config.py`, but TS config package remains frontend/build/runtime configuration.                                                                                                       |
| `@lobechat/const`                            | `partial-port`     | `keep-shared-contract`         | Shared constants are imported widely by SPA/packages. Python may mirror boundary enums, but this remains a TS contract package.                                                                       |
| `@lobechat/context-engine`                   | `partial-port`     | `ported-blocked-by-ts-imports` | Python has context compression and agent runtime message handling, but TS context engine remains heavily imported by memory, chat, and runtime code.                                                  |
| `@lobechat/conversation-flow`                | `not-python-owned` | `keep-shared-contract`         | Conversation rendering/transformation is still TS/frontend/domain logic. Python only needs persisted shape parity.                                                                                    |
| `@lobechat/database`                         | `partial-port`     | `keep-shared-contract`         | Do not remove first. Skill guidance says TypeScript Drizzle in `packages/database` owns schema definition and Python SQLModel must match it.                                                          |
| `@lobechat/device-gateway-client`            | `not-python-owned` | `not-python-owned`             | Client package for device gateway. Python backend does not own this protocol/client package.                                                                                                          |
| `@lobechat/edge-config`                      | `removed`          | `removed`                      | Package removed. The thin Vercel Edge Config wrapper now lives in `src/server/modules/EdgeConfig` for remaining TS config callers.                                                                    |
| `@lobechat/editor-runtime`                   | `partial-port`     | `not-python-owned`             | Mostly page/editor runtime used by TS page-agent UI and execution. Python replacement is not clearly complete.                                                                                        |
| `@lobechat/eval-dataset-parser`              | `removed`          | `removed`                      | Python agent eval parser tests cover CSV/JSON/JSONL. TS package removed; TS lambda retains local CSV/JSON/JSONL fallback only.                                                                        |
| `@lobechat/eval-rubric`                      | `removed`          | `removed`                      | Package removed. The evaluator now lives in `src/server/modules/EvalRubric` for remaining TS eval callers while Python task review parity continues to own backend migration.                         |
| `@lobechat/fetch-sse`                        | `partial-port`     | `keep-shared-contract`         | Python must emit compatible SSE, but SPA still needs TS SSE client utilities. Not a backend package deletion target.                                                                                  |
| `@lobechat/file-loaders`                     | `partial-port`     | `ported-blocked-by-ts-imports` | Python has RAG/file parsing services. TS document and local-file-shell code still import this package.                                                                                                |
| `@lobechat/heterogeneous-agents`             | `not-python-owned` | `not-python-owned`             | External agent adapter/client labels and UI integration. Python agent runtime overlap is not enough for deletion.                                                                                     |
| `@lobechat/local-file-shell`                 | `not-python-owned` | `not-python-owned`             | Local desktop file/shell helpers. Only root package dependency is visible, but this is not Python-owned backend behavior. Check if dependency is stale separately.                                    |
| `@lobechat/markdown-patch`                   | `partial-port`     | `ported-blocked-by-ts-imports` | Python may patch onboarding/skill content, but TS onboarding/user routes and built-in web onboarding still import it.                                                                                 |
| `@lobechat/memory-user-memory`               | `partial-port`     | `ported-blocked-by-ts-imports` | Python memory service and tests overlap. TS memory tool, extraction services, observability, and database model code still import it.                                                                 |
| `model-bank`                                 | `partial-port`     | `keep-shared-contract`         | Python `model_catalog` intentionally mirrors a minimal subset. TS package remains heavily used by frontend, model runtime, database, utils, and docs.                                                 |
| `@lobechat/model-runtime`                    | `partial-port`     | `ported-blocked-by-ts-imports` | Python has `llm_service`, `provider_runtime.py`, model fallback, image/video/webapi routes. TS model runtime remains heavily imported by SPA/server/tests.                                            |
| `@lobechat/observability-otel`               | `partial-port`     | `ported-blocked-by-ts-imports` | Python has tracing hooks, but TS instrumentation and Agent Signal observability still import this package.                                                                                            |
| `@lobechat/openapi`                          | `removed`          | `removed`                      | Python routers cover much of the REST/OpenAPI surface. TS package removed and Hono mount deleted.                                                                                                     |
| `@lobechat/prompts`                          | `partial-port`     | `keep-shared-contract`         | Python services may mirror prompts, but TS prompts are still shared by many tool/runtime packages.                                                                                                    |
| `@lobechat/python-interpreter`               | `not-python-owned` | `not-python-owned`             | Pyodide/client interpreter package, distinct from the FastAPI backend.                                                                                                                                |
| `@lobechat/shared-tool-ui`                   | `not-python-owned` | `not-python-owned`             | React tool UI package. Python should not replace it.                                                                                                                                                  |
| `@lobechat/ssrf-safe-fetch`                  | `partial-port`     | `keep-shared-contract`         | Python crawler/search must enforce equivalent safety, but TS utils, web crawler, Hono, and model runtime still import the TS package.                                                                 |
| `@lobechat/tool-runtime`                     | `partial-port`     | `ported-blocked-by-ts-imports` | Python has `app/services/tool_execution` and `app/tools/*`; TS shared tool UI and built-in tools still import runtime contracts.                                                                      |
| `@lobechat/types`                            | `partial-port`     | `keep-shared-contract`         | Python Pydantic models map to these API/domain contracts, but SPA/packages import this widely. Do not delete while TS frontend exists.                                                                |
| `@lobechat/utils`                            | `partial-port`     | `keep-shared-contract`         | Python may mirror selected helpers. TS utilities remain heavily used across SPA/packages.                                                                                                             |
| `@lobechat/web-crawler`                      | `partial-port`     | `ported-blocked-by-ts-imports` | Python has URL crawler/web search tools. TS search services and built-in web browsing package still import web crawler contracts/UI payloads.                                                         |

## Suggested One-by-One Workflow

For each candidate package:

1. Confirm Python endpoint/service/tool parity with a focused static audit and targeted tests.
2. Run `rg "<package-name>" . --glob '!pnpm-lock.yaml'` and classify every import as active, test-only, docs-only, or package metadata.
3. Remove or redirect active TS imports to the Python REST path or delete obsolete TS lambda/server code.
4. Remove the root `package.json` workspace dependency and the package folder.
5. Run targeted tests only:
   - Python parity tests for the affected domain.
   - TS tests that covered the retired import path.
   - `bun run type-check` only when TS import graph changes are broad enough to require it.

## Removed In This Pass

- `@lobechat/eval-dataset-parser`
- `@lobechat/chat-adapter-line`
- `@lobechat/chat-adapter-feishu`
- `@lobechat/chat-adapter-qq`
- `@lobechat/chat-adapter-wechat`
- `@lobechat/openapi`
- `@lobechat/edge-config`
- `@lobechat/eval-rubric`
- `@lobechat/builtin-tool-skill-maintainer`
- `@lobechat/builtin-tool-brief`
- `@lobechat/builtin-tool-topic-reference`
- `@lobechat/builtin-tool-cron`
- `@lobechat/builtin-tool-lobe-agent`
- `@lobechat/builtin-tool-task`
