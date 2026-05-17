# Python Backend — DB Schema Mismatches

The PostgreSQL database is created and migrated by the **TypeScript Drizzle ORM**, not by the Python backend. The Python SQLModel models must match the actual DB schema exactly.

## How to Verify Schema

```bash
# List all tables
docker exec lobe-postgres psql -U postgres -d lobehub -c "\dt"

# Describe a specific table
docker exec lobe-postgres psql -U postgres -d lobehub -c "\d tablename"

# Check if a column exists
docker exec lobe-postgres psql -U postgres -d lobehub -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'thread_id'"
```

## Resolved Mismatches (previously known issues)

All of these have been fixed. Listed here for historical reference.

### 1. `messages.thread_id` — RESOLVED

Added `thread_id` column to `messages` table via `ALTER TABLE` and re-added the field to `app/models/message.py`.

### 2. `user_memory_identities` / `user_memory_preferences` — RESOLVED

These tables exist in the DB (created by Alembic initial migration). The router (`user_memory.py`) was referencing non-existent `.title` field — fixed to use actual model fields:

- **Identity**: `type`, `description`, `role`, `relationship`
- **Preference**: `type`, `conclusion_directives`, `suggestions`, `tags`

### 3. `agent_documents` — VFS Columns — RESOLVED

Added 11 missing columns via **Alembic migration `0002_add_missing_columns.py`** + direct ALTER TABLE:

- `access_self`, `access_shared`, `access_public` (access control bitmasks)
- `template_id`, `policy` (JSON), `policy_load_position`, `policy_load_format`, `policy_load_rule`
- `deleted_by_user_id`, `deleted_by_agent_id`, `delete_reason` (soft delete)

All VFS endpoints now work correctly.

## Datetime Handling

All timestamp columns use `TIMESTAMP WITHOUT TIME ZONE`. Python datetimes must be **timezone-naive**:

```python
# In app/models/_helpers.py
def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

If you pass a timezone-aware datetime, asyncpg raises:

```
asyncpg.exceptions.DBAPIError: cannot pass a timezone-aware datetime
```

## Foreign Key Constraints

Be aware of FK cascading issues:

- Deleting a `task` fails if it has `task_comments` (FK: `task_comments_task_id_fkey`)
- Deleting an `agent` fails if it has `agent_eval_benchmarks` (FK: `agent_eval_benchmarks_agent_id_fkey`)
- Creating a `agent_cron_job` fails if `user_id` doesn't exist in `users` (FK: `agent_cron_jobs_user_id_fkey`)

## Adding New Models

When adding a Python model for a table that already exists in the TS DB:

1. Run `\d tablename` to get the exact column names, types, and constraints
2. Match column types exactly (e.g., `VARCHAR(255)` vs `VARCHAR` vs `TEXT`)
3. If the model needs columns the DB doesn't have, create an Alembic migration (`alembic/versions/`)
4. Use `sa_column=json_column("field_name")` for JSON columns
5. Use `metadata_` (with underscore) for any field named `metadata` — it's reserved by SQLAlchemy
6. Run migration: `DATABASE_URL=postgresql+asyncpg://postgres:lobechat@localhost:5433/lobehub .venv/bin/alembic upgrade head`
7. For asyncpg, each `op.execute()` must contain a **single** SQL statement (no multi-statement strings)
