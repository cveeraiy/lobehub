"""Add canonical message columns and constraints.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-23
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('messages') IS NOT NULL THEN
                ALTER TABLE messages
                    ADD COLUMN IF NOT EXISTS editor_data json,
                    ADD COLUMN IF NOT EXISTS favorite boolean DEFAULT false,
                    ADD COLUMN IF NOT EXISTS group_id text,
                    ADD COLUMN IF NOT EXISTS observation_id text,
                    ADD COLUMN IF NOT EXISTS quota_id text,
                    ADD COLUMN IF NOT EXISTS reasoning json,
                    ADD COLUMN IF NOT EXISTS search json,
                    ADD COLUMN IF NOT EXISTS summary text,
                    ADD COLUMN IF NOT EXISTS target_id text,
                    ADD COLUMN IF NOT EXISTS trace_id text;

                ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_group_id_fkey;
                ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_message_group_id_fkey;
                ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_quota_id_fkey;

                ALTER TABLE messages
                    ADD CONSTRAINT messages_group_id_fkey
                    FOREIGN KEY (group_id) REFERENCES chat_groups(id) ON DELETE SET NULL;
                ALTER TABLE messages
                    ADD CONSTRAINT messages_message_group_id_fkey
                    FOREIGN KEY (message_group_id) REFERENCES message_groups(id) ON DELETE CASCADE;
                ALTER TABLE messages
                    ADD CONSTRAINT messages_quota_id_fkey
                    FOREIGN KEY (quota_id) REFERENCES messages(id) ON DELETE SET NULL;

                CREATE INDEX IF NOT EXISTS messages_created_at_idx ON messages (created_at);
                CREATE INDEX IF NOT EXISTS messages_group_id_idx ON messages (group_id);
                CREATE INDEX IF NOT EXISTS messages_message_group_id_idx ON messages (message_group_id);
                CREATE INDEX IF NOT EXISTS messages_quota_id_idx ON messages (quota_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('messages') IS NOT NULL THEN
                ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_group_id_fkey;
                ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_message_group_id_fkey;
                ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_quota_id_fkey;

                DROP INDEX IF EXISTS messages_group_id_idx;
                DROP INDEX IF EXISTS messages_message_group_id_idx;
                DROP INDEX IF EXISTS messages_quota_id_idx;

                ALTER TABLE messages
                    DROP COLUMN IF EXISTS editor_data,
                    DROP COLUMN IF EXISTS favorite,
                    DROP COLUMN IF EXISTS group_id,
                    DROP COLUMN IF EXISTS observation_id,
                    DROP COLUMN IF EXISTS quota_id,
                    DROP COLUMN IF EXISTS reasoning,
                    DROP COLUMN IF EXISTS search,
                    DROP COLUMN IF EXISTS summary,
                    DROP COLUMN IF EXISTS target_id,
                    DROP COLUMN IF EXISTS trace_id;
            END IF;
        END $$;
        """
    )
