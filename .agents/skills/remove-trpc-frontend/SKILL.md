---
name: remove-trpc-frontend
description: Safely remove frontend TRPC service/resolver code after equivalent REST API coverage exists. Use when deleting lambdaClient-based frontend code, retiring .resolved service fallbacks, promoting REST services to canonical imports, or migrating one feature/domain fully off TRPC with targeted regression tests.
---

# Remove Frontend TRPC Code

Use this skill after REST support already exists and the task is to retire frontend TRPC paths. This is a removal workflow, not the initial TRPC-to-REST migration. If REST service files or Python endpoints are missing, use `trpc-to-rest` or `hono-python-rest-parity` first.

## References

Before choosing a feature to clean up, read [references/feature-migration-status.md](references/feature-migration-status.md). It maps feature IDs to routers, services, stores, known direct TRPC usage, and removal readiness.

If the status reference looks stale, cross-check `.agents/skills/rest-migration-plan/SKILL.md` and regenerate the local inventory with the commands in Preflight. Update the reference after completing a feature removal so the next cleanup starts from the current state.

## Principles

- Work feature by feature. Do not remove TRPC for multiple domains in one edit unless the user explicitly asks.
- Prove REST parity before deleting fallback code.
- Prefer deleting whole, unused TRPC service modules and resolvers only after all call sites for that feature/domain use REST.
- Do not remove a resolver if the domain is still partially TRPC. Either keep the resolver or narrow the cleanup to proven operation call sites.
- Keep response shapes stable for stores/components. Any REST shape normalization belongs in the service layer.
- Run targeted existing tests after each feature cleanup. Stop after two failed fix attempts and ask for help.

## Preflight

1. Identify the feature/domain and operation list from the user request.
2. Check current worktree state:

```bash
git status --short
```

3. Inventory frontend TRPC usage for the domain:

```bash
rg -n "lambdaClient|\\.resolved|shouldUseRest|NEXT_PUBLIC_REST_DOMAINS|NEXT_PUBLIC_USE_REST_API" src/services src/store src/features src/routes --glob '*.{ts,tsx}'
rg -n "from '@/services/.+\\.resolved|from '@/services/.+\\.rest|from '@/services/" src/store src/features src/routes --glob '*.{ts,tsx}'
```

4. Confirm REST implementation exists:

```bash
rg -n "restClient\\.(get|post|put|patch|delete)" src/services --glob '*.{ts,tsx}'
rg -n "@router\\.(get|post|put|patch|delete)\\(" python-backend/app/routers --glob '*.py'
```

If Python REST parity is unclear, use `hono-python-rest-parity` before deleting frontend fallback code.

## Removal Decision

Classify the cleanup before editing:

| Situation                                                                                  | Action                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Every operation used by the feature has matching REST service methods and Python endpoints | Promote REST to the canonical frontend path and remove unused TRPC/resolver code for that feature/domain.                                                                               |
| Only some operations have REST parity                                                      | Do not delete the shared domain resolver. Migrate only the proven operation call sites if the codebase has an operation-level pattern, or stop and add the missing REST coverage first. |
| REST service exists but shape/date/casing compatibility is untested                        | Add or run targeted frontend tests before removal. Fix the REST adapter first.                                                                                                          |
| Backend endpoint exists but no Python API/E2E coverage exists                              | Prefer adding/running backend tests before removing frontend fallback.                                                                                                                  |

## Safe Edit Sequence

### 1. Establish Canonical REST Import

For a fully migrated flat service:

```diff
-import { agentService } from '@/services/agent.resolved';
+import { agentService } from '@/services/agent.rest';
```

For a directory service:

```diff
-import { userService } from '@/services/user/resolved';
+import { userService } from '@/services/user';
```

Only use the directory service import when `src/services/user/index.ts` has been promoted to REST. If `index.ts` is still TRPC, first move or copy the REST implementation into the canonical module, then delete the old fallback files after tests pass.

### 2. Promote REST Carefully

When promoting REST to canonical:

- Preserve exported names and public method signatures.
- Preserve return shapes expected by stores/components.
- Preserve SuperJSON behavior manually where needed, especially `Date` conversion.
- Remove `shouldUseRest` usage only after there are no remaining fallback imports for that domain.
- Delete env-domain entries from docs/config only when no other domain depends on them.

Common file transitions:

```text
src/services/<domain>.rest.ts      -> src/services/<domain>.ts
src/services/<domain>.resolved.ts  -> delete
src/services/<domain>.ts.old/trpc  -> delete, only if unused

src/services/<domain>/index.rest.ts -> src/services/<domain>/index.ts
src/services/<domain>/resolved.ts   -> delete
```

Use `git mv` for whole-file promotion when it preserves history and does not overwrite user edits. If both source and destination have meaningful changes, merge with `apply_patch`.

### 3. Remove Dead TRPC Code

After imports are updated, verify dead code before deleting:

```bash
rg -n "<serviceName>|<domain>\\.resolved|from '@/services/<domain>'|lambdaClient\\.<namespace>" src test packages apps --glob '*.{ts,tsx}'
```

Delete only files/methods that are unreachable. If a TRPC service file contains operations outside the selected feature, do not delete the whole file.

### 4. Clean Resolver/Flag References

For the completed domain:

- remove `.resolved.ts` files
- remove `shouldUseRest('<domain>')` references
- remove domain-specific REST flag tests or snapshots only if they test deleted resolver behavior
- update any service barrel exports that pointed at the resolver

Keep the global REST flag system if any other domain still uses it.

## Validation

Run the smallest useful test set first:

```bash
bunx vitest run --silent='passed-only' '<affected-test-file>'
```

Then run broader checks when the cleanup touches shared services or store contracts:

```bash
bun run type-check
```

If Python endpoints or adapters were changed:

```bash
cd python-backend
.venv/bin/pytest tests/e2e/test_XX_domain.py -v --tb=short
```

Prefer existing tests. Add focused tests only when there is no coverage for a risky response-shape, date, casing, or error-path change.

## Final Report

Report:

- feature/domain cleaned up
- TRPC service/resolver files or methods removed
- imports promoted to REST/canonical service
- tests run and results
- any domains intentionally left on resolver fallback
- reference status updated, or why it was not updated

If cleanup could not proceed, state the concrete blocker: missing Python endpoint, missing REST service method, incompatible response shape, missing tests, or remaining call sites.
