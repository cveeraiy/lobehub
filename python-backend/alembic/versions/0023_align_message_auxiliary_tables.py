"""Align message auxiliary tables with Drizzle.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.message_groups') IS NOT NULL THEN
                ALTER TABLE message_groups DROP COLUMN IF EXISTS session_id;
                CREATE UNIQUE INDEX IF NOT EXISTS message_groups_client_id_user_id_unique
                    ON message_groups (client_id, user_id);
                CREATE INDEX IF NOT EXISTS message_groups_type_idx ON message_groups (type);
                CREATE INDEX IF NOT EXISTS message_groups_parent_group_id_idx ON message_groups (parent_group_id);
                CREATE INDEX IF NOT EXISTS message_groups_parent_message_id_idx ON message_groups (parent_message_id);
            END IF;

            IF to_regclass('public.message_plugins') IS NOT NULL THEN
                ALTER TABLE message_plugins DROP COLUMN IF EXISTS message_id;
                ALTER TABLE message_plugins ADD COLUMN IF NOT EXISTS client_id text;
                ALTER TABLE message_plugins ADD COLUMN IF NOT EXISTS intervention jsonb;
                ALTER TABLE message_plugins ADD COLUMN IF NOT EXISTS user_id text;
                ALTER TABLE message_plugins ALTER COLUMN user_id SET NOT NULL;
                ALTER TABLE message_plugins
                    ADD CONSTRAINT message_plugins_id_messages_id_fk
                    FOREIGN KEY (id) REFERENCES messages(id) ON DELETE CASCADE;
                ALTER TABLE message_plugins
                    ADD CONSTRAINT message_plugins_user_id_users_id_fk
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                CREATE UNIQUE INDEX IF NOT EXISTS message_plugins_client_id_user_id_unique
                    ON message_plugins (client_id, user_id);
                CREATE INDEX IF NOT EXISTS message_plugins_user_id_idx ON message_plugins (user_id);
                CREATE INDEX IF NOT EXISTS message_plugins_tool_call_id_idx ON message_plugins (tool_call_id);
            END IF;

            IF to_regclass('public.message_tts') IS NOT NULL THEN
                ALTER TABLE message_tts DROP COLUMN IF EXISTS message_id;
                ALTER TABLE message_tts DROP COLUMN IF EXISTS created_at;
                ALTER TABLE message_tts DROP COLUMN IF EXISTS updated_at;
                ALTER TABLE message_tts ADD COLUMN IF NOT EXISTS client_id text;
                ALTER TABLE message_tts ADD COLUMN IF NOT EXISTS user_id text;
                ALTER TABLE message_tts ALTER COLUMN user_id SET NOT NULL;
                ALTER TABLE message_tts
                    ADD CONSTRAINT message_tts_id_messages_id_fk
                    FOREIGN KEY (id) REFERENCES messages(id) ON DELETE CASCADE;
                ALTER TABLE message_tts
                    ADD CONSTRAINT message_tts_user_id_users_id_fk
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                ALTER TABLE message_tts
                    ADD CONSTRAINT message_tts_file_id_files_id_fk
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE;
                CREATE UNIQUE INDEX IF NOT EXISTS message_tts_client_id_user_id_unique
                    ON message_tts (client_id, user_id);
                CREATE INDEX IF NOT EXISTS message_tts_user_id_idx ON message_tts (user_id);
            END IF;

            IF to_regclass('public.message_translates') IS NOT NULL THEN
                ALTER TABLE message_translates DROP COLUMN IF EXISTS message_id;
                ALTER TABLE message_translates DROP COLUMN IF EXISTS created_at;
                ALTER TABLE message_translates DROP COLUMN IF EXISTS updated_at;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS client_id text;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS user_id text;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS "from" text;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS "to" text;
                ALTER TABLE message_translates DROP COLUMN IF EXISTS from_lang;
                ALTER TABLE message_translates DROP COLUMN IF EXISTS to_lang;
                ALTER TABLE message_translates ALTER COLUMN user_id SET NOT NULL;
                ALTER TABLE message_translates
                    ADD CONSTRAINT message_translates_id_messages_id_fk
                    FOREIGN KEY (id) REFERENCES messages(id) ON DELETE CASCADE;
                ALTER TABLE message_translates
                    ADD CONSTRAINT message_translates_user_id_users_id_fk
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                CREATE UNIQUE INDEX IF NOT EXISTS message_translates_client_id_user_id_unique
                    ON message_translates (client_id, user_id);
                CREATE INDEX IF NOT EXISTS message_translates_user_id_idx ON message_translates (user_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.message_translates') IS NOT NULL THEN
                DROP INDEX IF EXISTS message_translates_user_id_idx;
                DROP INDEX IF EXISTS message_translates_client_id_user_id_unique;
                ALTER TABLE message_translates DROP CONSTRAINT IF EXISTS message_translates_user_id_users_id_fk;
                ALTER TABLE message_translates DROP CONSTRAINT IF EXISTS message_translates_id_messages_id_fk;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS to_lang varchar;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS from_lang varchar;
                ALTER TABLE message_translates DROP COLUMN IF EXISTS "to";
                ALTER TABLE message_translates DROP COLUMN IF EXISTS "from";
                ALTER TABLE message_translates DROP COLUMN IF EXISTS user_id;
                ALTER TABLE message_translates DROP COLUMN IF EXISTS client_id;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS updated_at timestamp without time zone DEFAULT now() NOT NULL;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS created_at timestamp without time zone DEFAULT now() NOT NULL;
                ALTER TABLE message_translates ADD COLUMN IF NOT EXISTS message_id varchar;
                UPDATE message_translates SET message_id = id WHERE message_id IS NULL;
                ALTER TABLE message_translates ALTER COLUMN message_id SET NOT NULL;
            END IF;

            IF to_regclass('public.message_tts') IS NOT NULL THEN
                DROP INDEX IF EXISTS message_tts_user_id_idx;
                DROP INDEX IF EXISTS message_tts_client_id_user_id_unique;
                ALTER TABLE message_tts DROP CONSTRAINT IF EXISTS message_tts_file_id_files_id_fk;
                ALTER TABLE message_tts DROP CONSTRAINT IF EXISTS message_tts_user_id_users_id_fk;
                ALTER TABLE message_tts DROP CONSTRAINT IF EXISTS message_tts_id_messages_id_fk;
                ALTER TABLE message_tts DROP COLUMN IF EXISTS user_id;
                ALTER TABLE message_tts DROP COLUMN IF EXISTS client_id;
                ALTER TABLE message_tts ADD COLUMN IF NOT EXISTS updated_at timestamp without time zone DEFAULT now() NOT NULL;
                ALTER TABLE message_tts ADD COLUMN IF NOT EXISTS created_at timestamp without time zone DEFAULT now() NOT NULL;
                ALTER TABLE message_tts ADD COLUMN IF NOT EXISTS message_id varchar;
                UPDATE message_tts SET message_id = id WHERE message_id IS NULL;
                ALTER TABLE message_tts ALTER COLUMN message_id SET NOT NULL;
            END IF;

            IF to_regclass('public.message_plugins') IS NOT NULL THEN
                DROP INDEX IF EXISTS message_plugins_tool_call_id_idx;
                DROP INDEX IF EXISTS message_plugins_user_id_idx;
                DROP INDEX IF EXISTS message_plugins_client_id_user_id_unique;
                ALTER TABLE message_plugins DROP CONSTRAINT IF EXISTS message_plugins_user_id_users_id_fk;
                ALTER TABLE message_plugins DROP CONSTRAINT IF EXISTS message_plugins_id_messages_id_fk;
                ALTER TABLE message_plugins DROP COLUMN IF EXISTS user_id;
                ALTER TABLE message_plugins DROP COLUMN IF EXISTS intervention;
                ALTER TABLE message_plugins DROP COLUMN IF EXISTS client_id;
                ALTER TABLE message_plugins ADD COLUMN IF NOT EXISTS message_id varchar;
                UPDATE message_plugins SET message_id = id WHERE message_id IS NULL;
                ALTER TABLE message_plugins ALTER COLUMN message_id SET NOT NULL;
            END IF;

            IF to_regclass('public.message_groups') IS NOT NULL THEN
                DROP INDEX IF EXISTS message_groups_parent_message_id_idx;
                DROP INDEX IF EXISTS message_groups_parent_group_id_idx;
                DROP INDEX IF EXISTS message_groups_type_idx;
                DROP INDEX IF EXISTS message_groups_client_id_user_id_unique;
                ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS session_id varchar;
            END IF;
        END $$;
        """
    )
