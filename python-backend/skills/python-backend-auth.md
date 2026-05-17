# Python Backend — Authentication Guide

## Auth Flow Overview

The Python backend supports two authentication mechanisms, both handled in `app/dependencies.py:get_current_user_id`.

## 1. Keycloak JWT (Primary — User-Facing)

Users authenticate via Keycloak OIDC. The frontend obtains a JWT access token and sends it as `Authorization: Bearer <token>`.

### Keycloak Dev Config

| Setting       | Value                   |
| ------------- | ----------------------- |
| URL           | `http://localhost:8080` |
| Realm         | `lobehub`               |
| Client ID     | `lobehub-app`           |
| Client Secret | `lobehub-dev-secret`    |
| Test user     | `chandra` / `test123`   |

### Token Acquisition (for testing)

```bash
curl -s -X POST 'http://localhost:8080/realms/lobehub/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password&client_id=lobehub-app&client_secret=lobehub-dev-secret&username=chandra&password=test123'
```

Returns `{ "access_token": "eyJ...", "token_type": "bearer", ... }`.

### JWKS Validation

JWT is validated against the Keycloak JWKS endpoint:

```
http://localhost:8080/realms/lobehub/protocol/openid-connect/certs
```

The `get_current_user` function extracts the user from the JWT and calls `get_or_create_user` to ensure the user exists in the `users` table.

## 2. Service Token (Internal — TS→Python Proxy)

For the TypeScript backend to call the Python backend on behalf of a user:

| Header               | Value                              |
| -------------------- | ---------------------------------- |
| `X-Service-Token`    | Must match `SERVICE_TOKEN` env var |
| `X-Internal-User-Id` | The user ID to act as              |

The service token path calls `_ensure_user_exists` to verify the user ID exists in the DB.

## 3. Dev Mock Auth

Set `ENABLE_MOCK_DEV_USER=1` + `MOCK_DEV_USER_ID=<user-id>` to bypass all auth. Used for local TRPC development against the frontend.

## Common Auth Issues

### `_TEMP_USER_ID` placeholder

Several routers were initially written with hardcoded `_TEMP_USER_ID = "user_default"`. This causes `IntegrityError` (FK violation) because `user_default` doesn't exist in the `users` table.

**Always use:**

```python
from app.dependencies import get_current_user_id

@router.post("/endpoint")
async def handler(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    ...
```

**Routers that were fixed** (replaced `_TEMP_USER_ID` → `get_current_user_id`):

- `app/routers/briefs.py`
- `app/routers/agent_cron_jobs.py`

**Check these routers** if you see FK violations — they may still use placeholders.

### Token Expiry

Keycloak tokens expire after a short TTL. In tests, the `client` fixture is function-scoped and gets a fresh token per test function. If you see 401 errors, the token may have expired between test runs.

### User Auto-Creation

`get_or_create_user` in `app/dependencies.py` automatically creates a row in the `users` table if the Keycloak user doesn't exist yet. The user ID is derived from the JWT `sub` claim.
