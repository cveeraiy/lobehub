# Database Python Parity Audit

- Drizzle snapshot: `src/database/migrations/meta/0101_snapshot.json`
- TS tables: 95
- Python tables: 77
- Matched tables: 76
- Python-missing tables: 19
- Python-extra tables: 1
- Tables with column mismatches: 0
- Tables with constraint mismatches: 0

## Migration Journal Drift

Drift detected.

SQL migrations missing from `_journal.json`:

- `0050_add_user_organization`
- `0065_add_document_fields`
- `0101_add_settings_permissions`

## Python-Missing Tables

- `accounts`
- `agents_to_sessions`
- `auth_sessions`
- `nextauth_authenticators`
- `nextauth_sessions`
- `nextauth_verificationtokens`
- `oauth_handoffs`
- `oidc_access_tokens`
- `oidc_authorization_codes`
- `oidc_clients`
- `oidc_consents`
- `oidc_device_codes`
- `oidc_grants`
- `oidc_interactions`
- `oidc_refresh_tokens`
- `oidc_sessions`
- `passkey`
- `two_factor`
- `verifications`

## Python-Missing Table Decisions

### `retire` (17)

- `accounts`: Better Auth account persistence is retired because Keycloak is the only auth provider.
- `auth_sessions`: Better Auth DB sessions are retired; Python owns Keycloak-backed session handling.
- `nextauth_authenticators`: Legacy NextAuth/WebAuthn persistence is retired.
- `nextauth_sessions`: Legacy NextAuth DB sessions are retired.
- `nextauth_verificationtokens`: Legacy NextAuth verification tokens are retired.
- `oidc_access_tokens`: Legacy internal TS OIDC provider persistence is retired.
- `oidc_authorization_codes`: Legacy internal TS OIDC provider persistence is retired.
- `oidc_clients`: Legacy internal TS OIDC provider clients are retired; market OIDC is separate.
- `oidc_consents`: Legacy internal TS OIDC provider consent persistence is retired.
- `oidc_device_codes`: Legacy internal TS OIDC provider device flow persistence is retired.
- `oidc_grants`: Legacy internal TS OIDC provider persistence is retired.
- `oidc_interactions`: Legacy internal TS OIDC provider interaction persistence is retired.
- `oidc_refresh_tokens`: Legacy internal TS OIDC provider persistence is retired.
- `oidc_sessions`: Legacy internal TS OIDC provider sessions are retired.
- `passkey`: Better Auth passkeys are retired because Keycloak is the only auth provider.
- `two_factor`: Better Auth two-factor persistence is retired because Keycloak owns MFA.
- `verifications`: Better Auth verification persistence is retired because Keycloak owns auth verification flows.

### `retire_candidate` (1)

- `oauth_handoffs`: Internal OAuth credential handoff should be retired with the TS OIDC provider unless a desktop/mobile Keycloak callback flow still requires it.

### `retire_with_migration` (1)

- `agents_to_sessions`: Python canonical schema uses sessions.agent_id for the single active session agent. Existing join rows are backfilled into sessions.agent_id before the TS join table is retired.

## Python-Extra Tables

- `agent_skill_shares`

## Matched Table Mismatch Decisions

None.

## Column Mismatches

None.

## Constraint Mismatches

None.
