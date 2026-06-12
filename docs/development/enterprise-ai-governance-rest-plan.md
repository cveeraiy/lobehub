# Enterprise AI Governance REST Implementation Plan

## Goal

Turn provider, model, and skill configuration into organization-managed enterprise policy.
Normal users should not manage AI providers, service models, or skill settings. Admins should
manage those settings for:

- one user;
- one or more user groups;
- every user in an organization.

The implementation must use the Python FastAPI backend and REST frontend services only. Do not
add new TRPC procedures for this work.

## Non-Negotiable Constraint

Do not modify the existing database schema until the new implementation is tested.

The first implementation phase must therefore use a schema-free policy repository:

- static config loaded by Python backend settings;
- test fixtures injected into the Python service layer;
- optional local JSON/dev-only repository if manual UI testing needs persisted state.

Only after the REST API, frontend, policy resolver, write blocking, and runtime enforcement are
tested should database schema changes and migrations be introduced.

## Existing Code Touchpoints

- Python REST backend: `python-backend/app/routers`, `python-backend/app/services`
- REST frontend service layer: `src/services/*.rest.ts`, `src/services/*.resolved.ts`
- Existing admin REST service: `src/services/admin.rest.ts`
- Existing admin UI: `src/features/Admin`
- User settings store: `src/store/user`
- User settings pages:
  - `src/routes/(main)/settings/provider`
  - `src/routes/(main)/settings/service-model`
  - `src/routes/(main)/settings/skill`
- Current Python user state endpoint: `python-backend/app/routers/user.py`
- Current Python admin endpoint: `python-backend/app/routers/admin.py`

## Target Architecture

```text
Admin UI
  -> src/services/enterpriseAiPolicy.rest.ts
  -> /api/admin/enterprise-ai-policies
  -> Python EnterpriseAiPolicyService
  -> PolicyRepository abstraction
      -> Phase 1: Static/Test/Dev JSON repository, no schema change
      -> Phase 2: Database repository, after tests pass

User SPA
  -> /api/user/state
  -> EnterpriseAiPolicyResolver
  -> effective enterprise AI settings
  -> read-only managed provider/model/skill UX

Runtime
  -> chat/model/tool execution
  -> EnterpriseAiPolicyResolver
  -> enforced provider/model/skill allowlists
```

## Policy Model

Use this domain model in Python service code first. It should not imply a database table yet.

```text
EnterpriseAiPolicy
- id
- name
- description
- organization_id
- priority
- enabled
- provider_config
- model_config
- skill_config
- targets
- created_by
- updated_by
- created_at
- updated_at

EnterpriseAiPolicyTarget
- target_type: organization | group | user
- target_id

EffectiveEnterpriseAiPolicy
- managed_settings
- providers
- models
- default_agent
- skills
- restrictions
```

Policy precedence:

1. user-targeted policy
2. group-targeted policy, highest priority first
3. organization-targeted policy
4. global fallback policy

When multiple policies apply at the same level, the higher `priority` wins. If priority ties,
the newest update wins.

## Phase 0: REST-Only Foundation Audit

1. Confirm `NEXT_PUBLIC_USE_REST_API=1` or `NEXT_PUBLIC_REST_DOMAINS` can route the affected
   domains through REST.
2. Identify any provider/model/skill settings writes that still import TRPC services directly.
3. Confirm Python has REST coverage for:
   - user state;
   - admin user listing/settings;
   - AI provider/model discovery;
   - skills/tool availability.
4. Create a list of direct `lambdaClient` usage that would bypass REST for this feature.

Exit criteria:

- A short inventory of REST gaps exists.
- No implementation depends on adding a new TS TRPC router.

## Phase 1: Schema-Free Python Policy Service

Add Python-only domain logic without database migrations.

Files to add:

- `python-backend/app/services/enterprise_ai_policy/types.py`
- `python-backend/app/services/enterprise_ai_policy/repository.py`
- `python-backend/app/services/enterprise_ai_policy/static_repository.py`
- `python-backend/app/services/enterprise_ai_policy/resolver.py`
- `python-backend/app/services/enterprise_ai_policy/service.py`

Repository interface:

```python
class EnterpriseAiPolicyRepository(Protocol):
    async def list_policies_for_user(self, user_id: str) -> list[EnterpriseAiPolicy]: ...
    async def list_policies_for_admin(self, admin_user_id: str) -> list[EnterpriseAiPolicy]: ...
    async def upsert_policy(self, policy: EnterpriseAiPolicy) -> EnterpriseAiPolicy: ...
    async def delete_policy(self, policy_id: str) -> None: ...
```

Phase 1 repository implementations:

- `StaticEnterpriseAiPolicyRepository`: loads one org policy from backend config/env.
- `InMemoryEnterpriseAiPolicyRepository`: used by tests.
- Optional `DevJsonEnterpriseAiPolicyRepository`: local manual testing only, explicitly marked
  not for production.

Exit criteria:

- Policy precedence is unit tested.
- Effective policy shape is stable.
- No database schema file or migration file has changed.

## Phase 2: Python REST Endpoints

Add REST endpoints only.

Router:

- `python-backend/app/routers/enterprise_ai_policies.py`

Endpoints:

```text
GET    /api/enterprise-ai-policy/effective
GET    /api/admin/enterprise-ai-policies
POST   /api/admin/enterprise-ai-policies
PUT    /api/admin/enterprise-ai-policies/{policy_id}
DELETE /api/admin/enterprise-ai-policies/{policy_id}
POST   /api/admin/enterprise-ai-policies/{policy_id}/targets
DELETE /api/admin/enterprise-ai-policies/{policy_id}/targets/{target_type}/{target_id}
```

Rules:

- Use `Depends(get_current_user_id)` for every endpoint.
- Use Python admin authorization, not frontend checks.
- REST request/response fields should use `snake_case`; transform to camelCase in TS service.
- Do not add TRPC compatibility endpoints for this feature.

Exit criteria:

- Python API tests pass for admin CRUD, target assignment, and effective policy resolution.
- Non-admin users cannot mutate policies.
- No database schema file or migration file has changed.

## Phase 3: Frontend REST Service Layer

Add a REST-only frontend service.

Files:

- `src/services/enterpriseAiPolicy.rest.ts`
- `src/services/enterpriseAiPolicy.resolved.ts`

The resolved file may exist for consistency, but it must resolve to REST for this feature and
must not import a TRPC implementation.

Service methods:

```ts
getEffectivePolicy();
listPolicies();
createPolicy();
updatePolicy();
deletePolicy();
assignTarget();
removeTarget();
```

Rules:

- Use `restClient`.
- Convert `snake_case` API fields to frontend `camelCase`.
- Do not import `lambdaClient`.
- Do not create `src/services/enterpriseAiPolicy.ts` as a TRPC service.

Exit criteria:

- Unit tests verify field transformation and REST URL usage.
- Static search shows no `lambdaClient` usage in the enterprise policy service.

## Phase 4: User State Integration

Extend Python `/api/user/state` to include effective enterprise AI policy.

Add response field:

```json
{
  "enterprise_ai_policy": {
    "managed_settings": {
      "provider": true,
      "model": true,
      "skills": true
    },
    "providers": {},
    "models": {},
    "default_agent": {},
    "skills": {},
    "restrictions": {}
  }
}
```

Frontend changes:

- Extend user state types.
- Store the effective policy in `useUserStore`.
- Selectors for provider/model/skill settings should read policy-managed effective settings when
  present.

Exit criteria:

- User state initialization works in REST mode.
- Existing personal settings continue to load.
- Provider/model/skill settings become policy-managed when policy says so.

## Phase 5: Block User Writes to Managed Settings

Server-side enforcement is required.

In Python user settings update endpoints, reject or strip writes to managed fields:

- provider credentials / key vaults;
- language model provider config;
- default agent model/provider;
- skill/tool enablement;
- MCP/tool marketplace settings if governed by policy.

Preferred behavior:

- return `403` with a clear machine-readable error code, for example
  `ENTERPRISE_SETTING_MANAGED`;
- include blocked paths in the response.

Frontend behavior:

- disable managed controls;
- show read-only state: `Managed by your organization`;
- avoid sending blocked writes.

Exit criteria:

- API tests prove users cannot override managed settings.
- UI tests prove managed pages do not expose editable provider/model/skill controls.
- Runtime tests prove a manually crafted request cannot bypass policy.

## Phase 6: Admin AI Governance UI

Add admin UI under the existing admin area.

Suggested route:

```text
/admin/ai-governance
```

Use SPA route conventions:

- route segment stays thin in `src/routes/(main)/admin`;
- UI and business components live under `src/features/Admin/AiGovernance`;
- update both desktop router configs if a new SPA route is registered.

Views:

- policy list;
- policy detail editor;
- provider configuration;
- model allow/deny/default configuration;
- skill allow/deny configuration;
- target assignment for organization, groups, and users;
- policy preview for a selected user.

Exit criteria:

- Admin can create a policy in schema-free repository mode.
- Admin can assign it to user/group/org targets.
- Preview shows the same effective policy returned by `/api/enterprise-ai-policy/effective`.

## Phase 7: Runtime Enforcement

Apply the effective policy where the application actually uses AI.

Enforcement points:

- model runtime/provider credential resolution;
- chat execution;
- agent execution;
- model listing;
- skill/tool listing;
- skill/tool execution.

Rules:

- Never trust frontend filtering.
- Provider secrets must be resolved server-side.
- If a model is denied, runtime returns a policy error before calling the provider.
- If a skill is denied, it is omitted from available tools and rejected at execution.

Exit criteria:

- Tests prove denied models never reach provider runtime.
- Tests prove denied skills cannot execute even if requested directly.
- Tests prove default/fallback model is applied consistently.

## Phase 8: Test Matrix Before Schema Changes

Complete this test matrix before modifying database schema.

Python unit tests:

- policy precedence: user over group over org over global;
- disabled policy ignored;
- priority ordering;
- target matching;
- effective policy merging;
- blocked user settings writes;
- admin authorization.

Python API/E2E tests:

- `GET /api/enterprise-ai-policy/effective`;
- admin policy CRUD;
- admin target assignment;
- non-admin forbidden;
- user cannot override managed provider/model/skill settings.

Frontend tests:

- REST service URL and transform tests;
- user state enterprise policy hydration;
- managed settings read-only rendering;
- admin governance policy editor behavior.

Runtime tests:

- allowed provider/model succeeds;
- denied model fails before provider call;
- denied skill fails before execution;
- default model comes from policy.

Manual REST-mode validation:

```bash
cd python-backend
.venv/bin/uvicorn main:app --reload --port 8000

PORT=8000 NEXT_PUBLIC_USE_REST_API=1 bun run dev:spa
```

Exit criteria:

- All tests above pass in schema-free mode.
- No feature path uses new TRPC procedures.
- No existing database schema file or migration has changed.

## Phase 9: Database Schema Design Review

Only after Phase 8 passes, prepare schema changes.

Proposed persistent tables:

```text
enterprise_ai_policies
enterprise_ai_policy_targets
enterprise_ai_provider_secrets
organization_groups
organization_group_members
enterprise_ai_policy_audit_logs
```

Before creating migrations:

1. Review table ownership between Drizzle and Python SQLModel.
2. Decide if organization groups should reuse Keycloak group claims or be local app groups.
3. Decide encryption strategy for provider secrets.
4. Decide audit retention.
5. Write migration rollback plan.

Exit criteria:

- Schema design reviewed.
- Migration plan approved.
- Python SQLModel models match the planned database columns.

## Phase 10: Persistence Migration

After approval:

1. Add Drizzle schema changes.
2. Generate database migration.
3. Add matching Python SQLModel models.
4. Replace schema-free repository with database repository behind the same interface.
5. Keep tests from Phase 8 unchanged and make them pass against the database repository.
6. Add migration-specific tests.

Exit criteria:

- Existing schema-free tests still pass.
- Database-backed policy CRUD works.
- Runtime enforcement still works.
- Rollback path is documented.

## Guardrails

- No new TRPC procedures.
- No frontend `lambdaClient` usage in new enterprise policy code.
- No database schema changes before Phase 8 passes.
- No provider secrets in user settings.
- No UI-only enforcement.
- Feature must run with `NEXT_PUBLIC_USE_REST_API=1`.
