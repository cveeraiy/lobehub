# Python Backend — Agent Guidelines

## Quick Reference

- **Start server**: `.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info`
- **Run E2E tests**: `.venv/bin/pytest tests/e2e/ -v --tb=short`
- **Run single test file**: `.venv/bin/pytest tests/e2e/test_XX_name.py -v --tb=short`
- **Database**: `postgresql+asyncpg://postgres:lobechat@localhost:5433/lobehub`
- **Auth**: Keycloak OIDC at `http://localhost:8080/realms/lobehub`

## Skills

See `skills/` directory for detailed guides:

- `skills/python-backend-api-conventions.md` — REST API field naming, Pydantic schemas, auth patterns
- `skills/python-backend-e2e-testing.md` — E2E test patterns, fixtures, common pitfalls
- `skills/python-backend-add-api-tests.md` — **Adding E2E tests when new API endpoints are created**
- `skills/python-backend-db-schema.md` — DB schema mismatches between Python models and TS Drizzle ORM
- `skills/python-backend-auth.md` — Keycloak JWT auth, service token auth, test authentication
