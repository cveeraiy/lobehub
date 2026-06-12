"""Add thread REST parity columns.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-22
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE threads ADD COLUMN IF NOT EXISTS agent_id TEXT')
    op.execute('ALTER TABLE threads ADD COLUMN IF NOT EXISTS group_id TEXT')
    op.execute('ALTER TABLE threads ADD COLUMN IF NOT EXISTS metadata JSONB')
    op.execute('ALTER TABLE threads ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP WITH TIME ZONE DEFAULT now()')
    op.execute('UPDATE threads SET last_active_at = updated_at WHERE last_active_at IS NULL')
    op.execute('CREATE INDEX IF NOT EXISTS threads_agent_id_idx ON threads USING btree (agent_id)')
    op.execute('CREATE INDEX IF NOT EXISTS threads_group_id_idx ON threads USING btree (group_id)')
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'threads_agent_id_agents_id_fk'
            ) THEN
                ALTER TABLE threads
                ADD CONSTRAINT threads_agent_id_agents_id_fk
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'threads_group_id_chat_groups_id_fk'
            ) THEN
                ALTER TABLE threads
                ADD CONSTRAINT threads_group_id_chat_groups_id_fk
                FOREIGN KEY (group_id) REFERENCES chat_groups(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute('ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_group_id_chat_groups_id_fk')
    op.execute('ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_agent_id_agents_id_fk')
    op.execute('DROP INDEX IF EXISTS threads_group_id_idx')
    op.execute('DROP INDEX IF EXISTS threads_agent_id_idx')
    op.execute('ALTER TABLE threads DROP COLUMN IF EXISTS last_active_at')
    op.execute('ALTER TABLE threads DROP COLUMN IF EXISTS metadata')
    op.execute('ALTER TABLE threads DROP COLUMN IF EXISTS group_id')
    op.execute('ALTER TABLE threads DROP COLUMN IF EXISTS agent_id')
