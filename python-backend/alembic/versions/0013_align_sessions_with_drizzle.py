"""Align sessions with Drizzle schema.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-23
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title TEXT")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS avatar TEXT")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS background_color TEXT")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS slug VARCHAR(100)")
    op.execute(
        """
        UPDATE sessions
        SET slug = LEFT('session-' || regexp_replace(id, '[^a-zA-Z0-9]+', '-', 'g'), 100)
        WHERE slug IS NULL
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (PARTITION BY user_id, slug ORDER BY id) AS rn
            FROM sessions
            WHERE slug IS NOT NULL
        )
        UPDATE sessions AS s
        SET slug = LEFT(s.slug, 83) || '-' || RIGHT(regexp_replace(s.id, '[^a-zA-Z0-9]+', '', 'g'), 16)
        FROM ranked
        WHERE s.id = ranked.id AND ranked.rn > 1
        """
    )
    op.execute("ALTER TABLE sessions ALTER COLUMN slug TYPE VARCHAR(100) USING LEFT(slug, 100)")
    op.execute("ALTER TABLE sessions ALTER COLUMN slug SET NOT NULL")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE")
    op.execute("UPDATE sessions SET pinned = FALSE WHERE pinned IS NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS slug_user_id_unique ON sessions (slug, user_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS sessions_client_id_user_id_unique ON sessions (client_id, user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS sessions_id_user_id_idx ON sessions (id, user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS sessions_user_id_updated_at_idx ON sessions (user_id, updated_at)")
    op.execute("CREATE INDEX IF NOT EXISTS sessions_group_id_idx ON sessions (group_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS sessions_user_id_updated_at_idx")
    op.execute("DROP INDEX IF EXISTS sessions_id_user_id_idx")
    op.execute("DROP INDEX IF EXISTS slug_user_id_unique")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS background_color")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS avatar")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS description")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS title")
