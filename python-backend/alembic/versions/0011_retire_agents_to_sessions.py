"""Retire agents_to_sessions in favor of sessions.agent_id.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-23
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS agent_id TEXT")
    op.execute("CREATE INDEX IF NOT EXISTS sessions_agent_id_idx ON sessions USING btree (agent_id)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'sessions_agent_id_agents_id_fk'
            ) THEN
                ALTER TABLE sessions
                ADD CONSTRAINT sessions_agent_id_agents_id_fk
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.agents_to_sessions') IS NOT NULL THEN
                UPDATE sessions AS s
                SET agent_id = linked.agent_id
                FROM (
                    SELECT DISTINCT ON (session_id)
                        session_id,
                        agent_id
                    FROM agents_to_sessions
                    WHERE agent_id IS NOT NULL AND session_id IS NOT NULL
                    ORDER BY session_id, agent_id
                ) AS linked
                WHERE s.id = linked.session_id
                  AND s.agent_id IS NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_agent_id_agents_id_fk")
    op.execute("DROP INDEX IF EXISTS sessions_agent_id_idx")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS agent_id")
