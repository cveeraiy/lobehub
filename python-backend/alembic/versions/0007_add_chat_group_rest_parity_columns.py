"""Add chat group REST parity columns.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-22
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS title TEXT')
    op.execute('UPDATE chat_groups SET title = name WHERE title IS NULL AND name IS NOT NULL')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS background_color TEXT')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS market_identifier TEXT')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS content TEXT')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS editor_data JSONB')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS config JSONB')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS client_id TEXT')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS group_id TEXT')
    op.execute('ALTER TABLE chat_groups ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE')
    op.execute('UPDATE chat_groups SET pinned = FALSE WHERE pinned IS NULL')
    op.execute('CREATE INDEX IF NOT EXISTS chat_groups_group_id_idx ON chat_groups USING btree (group_id)')
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'chat_groups_client_id_user_id_unique'
            ) THEN
                CREATE UNIQUE INDEX chat_groups_client_id_user_id_unique
                ON chat_groups USING btree (client_id, user_id);
            END IF;
        END $$;
        """
    )

    op.execute('ALTER TABLE chat_groups_agents ADD COLUMN IF NOT EXISTS chat_group_id TEXT')
    op.execute('UPDATE chat_groups_agents SET chat_group_id = group_id WHERE chat_group_id IS NULL')
    op.execute('ALTER TABLE chat_groups_agents ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE')
    op.execute('UPDATE chat_groups_agents SET enabled = TRUE WHERE enabled IS NULL')
    op.execute('ALTER TABLE chat_groups_agents ADD COLUMN IF NOT EXISTS "order" INTEGER DEFAULT 0')
    op.execute('UPDATE chat_groups_agents SET "order" = 0 WHERE "order" IS NULL')
    op.execute('ALTER TABLE chat_groups_agents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()')
    op.execute('UPDATE chat_groups_agents SET updated_at = created_at WHERE updated_at IS NULL')
    op.execute(
        'CREATE INDEX IF NOT EXISTS chat_groups_agents_chat_group_id_idx ON chat_groups_agents USING btree (chat_group_id)'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS chat_groups_agents_chat_group_id_idx')
    op.execute('ALTER TABLE chat_groups_agents DROP COLUMN IF EXISTS updated_at')
    op.execute('ALTER TABLE chat_groups_agents DROP COLUMN IF EXISTS "order"')
    op.execute('ALTER TABLE chat_groups_agents DROP COLUMN IF EXISTS enabled')
    op.execute('ALTER TABLE chat_groups_agents DROP COLUMN IF EXISTS chat_group_id')
    op.execute('DROP INDEX IF EXISTS chat_groups_client_id_user_id_unique')
    op.execute('DROP INDEX IF EXISTS chat_groups_group_id_idx')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS pinned')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS group_id')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS client_id')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS config')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS editor_data')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS content')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS market_identifier')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS background_color')
    op.execute('ALTER TABLE chat_groups DROP COLUMN IF EXISTS title')
