---
name: bot-python-migration
description: Migrate Ethos chat bot platform implementations from the TypeScript bot runtime to the Python FastAPI REST backend one platform at a time. Use when porting Discord, Slack, Telegram, Feishu, Lark, QQ, WeChat, Line, Microsoft Teams, bot webhooks, BotMessageRouter behavior, PlatformClient implementations, gateway lifecycle, bot provider REST parity, or channel runtime status from TS to Python.
---

# Bot Python Migration

## Core Rule

Migrate one platform end-to-end before starting the next. Do not add Microsoft Teams until the Python platform substrate and at least one existing platform have passed parity checks.

Use these skills together when relevant:

- `bot` for current TS platform behavior and runtime architecture.
- `python-backend` for FastAPI, auth, SQLModel, and router conventions.
- `rest-frontend-architecture` for frontend REST service/resolver expectations.
- `testing` when adding Vitest or Python API tests.

## Scope Per Platform

Each platform migration must include:

1. Python platform definition and schema metadata.
2. Python REST provider CRUD parity with the TS service contract.
3. Inbound webhook or gateway entrypoint.
4. Message normalization into the common bot runtime shape.
5. Outbound messenger methods required by the bridge.
6. Credential validation.
7. Runtime status behavior or an explicit unsupported-mode guard.
8. Focused tests and a short parity note in the PR/summary.

## Migration Order

Prefer this order unless the user names a specific platform:

1. Fix shared `agent_bot_providers` Python parity first.
2. Migrate a simple webhook platform first: `telegram` or `line`.
3. Migrate `slack` in webhook mode.
4. Add persistent gateway support, then port websocket/polling platforms.
5. Migrate `discord`, `feishu`, `lark`, `qq`, and `wechat`.
6. Implement `teams` after existing Python runtime patterns are stable.

When the user asks to disable other channels, expose only migrated Python-supported platforms from Python `listPlatforms` and the frontend REST service. Do not merely hide unsupported platforms in UI while accepting them in API writes.

## Required First Pass

Before editing, inspect the current platform and REST surfaces:

```bash
rg -n "agentBotProvider|BotMessageRouter|PlatformDefinition|platformRegistry" src packages python-backend -g '*.{ts,tsx,py}'
rg -n "<platform-id>|application_id|agent_bot_providers" src packages python-backend -g '*.{ts,tsx,py}'
```

Read only the files needed for the chosen platform:

- TS registry: `src/server/services/bot/platforms/index.ts`
- TS platform folder: `src/server/services/bot/platforms/<platform>/`
- TS router: `src/server/routers/lambda/agentBotProvider.ts`
- Frontend REST service: `src/services/agentBotProvider.rest.ts`
- Python router: `python-backend/app/routers/agent_bot_providers.py`
- Python model: `python-backend/app/models/agent_ops.py`
- Drizzle schema: `packages/database/src/schemas/agentBotProvider.ts`

## Shared Substrate Checklist

Complete or verify this before porting individual platforms:

- Python `AgentBotProvider` matches Drizzle: `id`, `agent_id`, `user_id`, `platform`, `application_id`, encrypted/plain credential storage strategy, `settings`, `enabled`, timestamps, indexes, and unique constraints.
- Python serializers return snake_case fields, and `agentBotProvider.rest.ts` converts them to the camelCase shape expected by stores.
- Python `listPlatforms` returns serialized platform definitions with schema, descriptions, documentation, connection mode, markdown/edit capabilities, not only string IDs.
- REST create/update validates platform IDs against the Python registry.
- REST delete/update invalidates or stops Python runtime state once gateway support exists.
- Existing TRPC files remain untouched unless the user explicitly asks to remove TS backend support.

## Platform Porting Steps

For each platform:

1. Create `python-backend/app/services/bot/platforms/<platform>/` with definition, schema, client, formatting helpers, and tests where useful.
2. Register the platform in the Python platform registry only after basic tests pass.
3. Port schema defaults before runtime behavior. Defaults must merge into stored settings the same way TS `mergeWithDefaults` does.
4. Implement `validate_credentials` using the platform API when possible. If validation is incomplete, return field-level errors for known missing values and document the gap.
5. Implement inbound parsing from the platform webhook/gateway payload into the common message/thread shape.
6. Implement outbound messenger capabilities:
   - `create_message`
   - `edit_message` only when supported
   - `remove_reaction` only when supported
   - `trigger_typing` when supported
   - `update_thread_name` when supported
7. Port platform-specific formatting and markdown stripping behavior.
8. Add platform access settings: DM policy, group policy, allowlist, server/user IDs, history limit, debounce/queue settings, char limit, display tool calls, usage stats.
9. Run the platform through the common bot bridge and Python agent runtime, not a standalone one-off path.

## Parity Gates

Do not mark a platform migrated until these are true:

- The frontend channel list and detail form work through REST mode only.
- Creating, updating, disabling, deleting, and listing providers use Python endpoints.
- Unsupported connection modes fail clearly instead of silently queuing forever.
- A sample inbound event reaches the Python bridge and produces the expected outbound action in tests or a local manual test.
- `/new` and `/stop` behavior is either ported or explicitly disabled with user-visible behavior.
- Attachments are handled with the same priority as TS where the platform supports them: buffered data, authenticated lazy fetch, public URL fallback.
- Runtime status is accurate for supported modes or explicitly `unknown` with no connect CTA for unsupported modes.

See `references/platform-parity.md` for the detailed review checklist.

## Tests

Prefer focused tests over broad suites:

```bash
bunx vitest run --silent='passed-only' src/services/agentBotProvider.test.ts
cd python-backend && .venv/bin/pytest tests/ < targeted-test > .py
```

If Python tests are not available for the touched area, add small FastAPI/router/service tests or document the manual verification gap.

## Teams Rule

When implementing Microsoft Teams after the migration:

- Add it as another Python platform, not as a special-case route.
- Keep non-Teams channels disabled by Python registry/API policy if the product requirement is Teams-only.
- Only add `@chat-adapter/teams` if the user explicitly accepts keeping Teams runtime in TypeScript. For Python-only runtime, use Microsoft Bot Framework/Graph-compatible Python handling instead.
