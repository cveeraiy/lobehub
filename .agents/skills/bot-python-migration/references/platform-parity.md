# Platform Parity Checklist

Use this checklist during each platform migration review.

## Provider Data

- `application_id` is persisted and serialized.
- Credentials are stored in the agreed Python-compatible format.
- Settings are merged with schema defaults before runtime use.
- Platform writes reject disabled or unknown platform IDs.
- Duplicate provider conflicts match the intended uniqueness rule.

## Runtime

- Inbound route authenticates or verifies signatures when the platform supports it.
- Webhook/gateway payloads map to a common thread/message shape.
- Mention, subscribed message, DM, and group-channel behavior match TS or have documented intentional differences.
- Queue/debounce behavior is preserved for supported modes.
- Active-thread guards prevent duplicate runs.
- `/new` clears topic state.
- `/stop` interrupts active execution or reports unsupported behavior clearly.

## Messaging

- Markdown is preserved, transformed, or stripped according to platform capability.
- Message edits are used only when supported.
- Long replies split by configured `charLimit`.
- Usage stats and tool-call display settings are honored.
- Reactions/typing indicators are no-ops when unsupported, not failures.

## Attachments

- Prefer buffered data when available.
- Use authenticated platform fetch helpers before public URLs.
- Infer missing MIME/name data for common image payloads.
- Include quoted/referenced message attachments if the platform exposes them.

## Frontend REST

- `agentBotProvider.rest.ts` matches the TRPC service return shape.
- Snake_case Python responses are transformed to camelCase before stores receive them.
- `listPlatforms` returns full serialized definitions, including schema.
- Channel forms work without importing TS platform registry data.

## Validation

- Add targeted Python tests for provider CRUD and platform parsing.
- Add or update frontend REST service tests when response shape changes.
- Run only targeted tests; do not run the full repo test suite unless explicitly requested.
