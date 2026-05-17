# TRPC → REST Migration (Python Backend Side)

When migrating a frontend service from TRPC to REST, the Python REST router is the backend target. This doc covers conventions for the Python side.

## Response Envelope

All Python REST routers MUST return responses in the standard envelope:

```python
# Success (list)
{"success": True, "data": [...], "total": 42}

# Success (single item)
{"success": True, "data": {...}}

# Success (no content)
{"success": True}

# Error (via HTTPException)
{"detail": "Not found"}  # FastAPI default
```

## Field Casing Convention

Python REST routers use **snake_case** for field names (Pydantic models). The frontend REST client expects **camelCase**.

**Preferred approach:** Add a Pydantic `model_config` with `alias_generator` to output camelCase:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class BriefResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: str
    user_id: str
    task_id: str | None = None
    created_at: str | None = None
    # Output: {"id": "...", "userId": "...", "taskId": "...", "createdAt": "..."}
```

**Alternative:** The frontend service can transform snake_case → camelCase, but it's cleaner to handle at the Python layer.

## Endpoint Design Rules

1. **Prefix:** All routers use `/api/<resource>` prefix
2. **HTTP methods:** GET for reads, POST for creates/actions, PUT/PATCH for updates, DELETE for deletes
3. **Status codes:** 200 for success, 201 for creates, 204 for no-content, 404 for not found
4. **Auth:** Use `user_id: str = Depends(get_current_user_id)` on every endpoint
5. **Pagination:** Use `limit` + `offset` query params, return `total` in response

## Matching TRPC Procedures to REST Endpoints

When a frontend service calls `lambdaClient.brief.listUnresolved.query()`, the matching REST endpoint is:

```
TRPC: brief.listUnresolved (query)  →  GET /api/briefs/unresolved
TRPC: brief.delete (mutate)         →  DELETE /api/briefs/{id}
TRPC: brief.markRead (mutate)       →  POST /api/briefs/{id}/read
TRPC: brief.resolve (mutate)        →  POST /api/briefs/{id}/resolve
```

General pattern:

- TRPC `query` → REST `GET`
- TRPC `mutate` (create) → REST `POST`
- TRPC `mutate` (update) → REST `PUT` or `PATCH`
- TRPC `mutate` (delete) → REST `DELETE`
- TRPC `mutate` (action) → REST `POST /resource/{id}/action`

## Checklist for Adding a New REST Router

1. Create `python-backend/app/routers/<domain>.py`
2. Define Pydantic request/response models with camelCase aliases
3. Add `router = APIRouter(prefix="/api/<resource>", tags=["<Resource>"])`
4. Implement CRUD endpoints matching the TRPC procedures
5. The router will be auto-discovered by `main.py` (importlib loop)
6. Test with: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/<resource>`
7. Verify OpenAPI docs at: `http://localhost:8000/docs`

## Existing Routers

See `python-backend/app/routers/*.py` — 40+ routers already exist covering all major domains. Most TRPC procedures already have matching REST endpoints.
