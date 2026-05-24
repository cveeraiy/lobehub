"""Align topics, threads, and async task drift.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.async_tasks') IS NOT NULL THEN
                ALTER TABLE async_tasks DROP CONSTRAINT IF EXISTS async_tasks_parent_id_fkey;
                ALTER TABLE async_tasks ALTER COLUMN status DROP NOT NULL;
                ALTER TABLE async_tasks ADD COLUMN IF NOT EXISTS inference_id text;
                ALTER TABLE async_tasks ADD COLUMN IF NOT EXISTS duration integer;
                ALTER TABLE async_tasks ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}';
                ALTER TABLE async_tasks ADD COLUMN IF NOT EXISTS accessed_at timestamp without time zone DEFAULT now() NOT NULL;
                CREATE INDEX IF NOT EXISTS async_tasks_parent_id_idx ON async_tasks (parent_id);
                CREATE INDEX IF NOT EXISTS async_tasks_type_status_idx ON async_tasks (type, status);
                CREATE INDEX IF NOT EXISTS async_tasks_inference_id_idx ON async_tasks (inference_id);
                CREATE INDEX IF NOT EXISTS async_tasks_metadata_idx ON async_tasks USING gin (metadata);
            END IF;

            IF to_regclass('public.topics') IS NOT NULL THEN
                ALTER TABLE topics ADD COLUMN IF NOT EXISTS content text;
                ALTER TABLE topics ADD COLUMN IF NOT EXISTS editor_data jsonb;
                ALTER TABLE topics ADD COLUMN IF NOT EXISTS group_id text;
                ALTER TABLE topics ADD COLUMN IF NOT EXISTS description text;
                ALTER TABLE topics ADD COLUMN IF NOT EXISTS trigger text;
                ALTER TABLE topics ADD COLUMN IF NOT EXISTS mode text;
                ALTER TABLE topics ADD COLUMN IF NOT EXISTS completed_at timestamp with time zone;
                ALTER TABLE topics ALTER COLUMN favorite DROP NOT NULL;
                ALTER TABLE topics
                    ADD CONSTRAINT topics_group_id_chat_groups_id_fk
                    FOREIGN KEY (group_id) REFERENCES chat_groups(id) ON DELETE CASCADE;
                CREATE INDEX IF NOT EXISTS topics_id_user_id_idx ON topics (id, user_id);
                CREATE INDEX IF NOT EXISTS topics_group_id_idx ON topics (group_id);
                CREATE INDEX IF NOT EXISTS topics_trigger_idx ON topics (trigger);
                CREATE INDEX IF NOT EXISTS topics_status_idx ON topics (status);
                CREATE INDEX IF NOT EXISTS topics_user_id_completed_at_idx ON topics (user_id, completed_at);
            END IF;

            IF to_regclass('public.threads') IS NOT NULL THEN
                ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_source_message_id_fkey;
                ALTER TABLE threads ADD COLUMN IF NOT EXISTS content text;
                ALTER TABLE threads ADD COLUMN IF NOT EXISTS editor_data jsonb;
                ALTER TABLE threads ADD COLUMN IF NOT EXISTS client_id text;
                UPDATE threads SET type = 'standalone' WHERE type IS NULL;
                ALTER TABLE threads ALTER COLUMN type SET NOT NULL;
                ALTER TABLE threads ALTER COLUMN last_active_at DROP NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS threads_client_id_user_id_unique ON threads (client_id, user_id);
                CREATE INDEX IF NOT EXISTS threads_type_idx ON threads (type);
                CREATE INDEX IF NOT EXISTS threads_agent_id_idx ON threads (agent_id);
                CREATE INDEX IF NOT EXISTS threads_group_id_idx ON threads (group_id);
                CREATE INDEX IF NOT EXISTS threads_parent_thread_id_idx ON threads (parent_thread_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.threads') IS NOT NULL THEN
                DROP INDEX IF EXISTS threads_parent_thread_id_idx;
                DROP INDEX IF EXISTS threads_group_id_idx;
                DROP INDEX IF EXISTS threads_agent_id_idx;
                DROP INDEX IF EXISTS threads_type_idx;
                DROP INDEX IF EXISTS threads_client_id_user_id_unique;
                UPDATE threads SET last_active_at = now() WHERE last_active_at IS NULL;
                ALTER TABLE threads ALTER COLUMN last_active_at SET NOT NULL;
                ALTER TABLE threads ALTER COLUMN type DROP NOT NULL;
                ALTER TABLE threads DROP COLUMN IF EXISTS client_id;
                ALTER TABLE threads DROP COLUMN IF EXISTS editor_data;
                ALTER TABLE threads DROP COLUMN IF EXISTS content;
                ALTER TABLE threads
                    ADD CONSTRAINT threads_source_message_id_fkey
                    FOREIGN KEY (source_message_id) REFERENCES messages(id);
            END IF;

            IF to_regclass('public.topics') IS NOT NULL THEN
                DROP INDEX IF EXISTS topics_user_id_completed_at_idx;
                DROP INDEX IF EXISTS topics_status_idx;
                DROP INDEX IF EXISTS topics_trigger_idx;
                DROP INDEX IF EXISTS topics_group_id_idx;
                DROP INDEX IF EXISTS topics_id_user_id_idx;
                ALTER TABLE topics DROP CONSTRAINT IF EXISTS topics_group_id_chat_groups_id_fk;
                UPDATE topics SET favorite = false WHERE favorite IS NULL;
                ALTER TABLE topics ALTER COLUMN favorite SET NOT NULL;
                ALTER TABLE topics DROP COLUMN IF EXISTS completed_at;
                ALTER TABLE topics DROP COLUMN IF EXISTS mode;
                ALTER TABLE topics DROP COLUMN IF EXISTS trigger;
                ALTER TABLE topics DROP COLUMN IF EXISTS description;
                ALTER TABLE topics DROP COLUMN IF EXISTS group_id;
                ALTER TABLE topics DROP COLUMN IF EXISTS editor_data;
                ALTER TABLE topics DROP COLUMN IF EXISTS content;
            END IF;

            IF to_regclass('public.async_tasks') IS NOT NULL THEN
                DROP INDEX IF EXISTS async_tasks_metadata_idx;
                DROP INDEX IF EXISTS async_tasks_inference_id_idx;
                DROP INDEX IF EXISTS async_tasks_type_status_idx;
                DROP INDEX IF EXISTS async_tasks_parent_id_idx;
                ALTER TABLE async_tasks DROP COLUMN IF EXISTS accessed_at;
                ALTER TABLE async_tasks DROP COLUMN IF EXISTS metadata;
                ALTER TABLE async_tasks DROP COLUMN IF EXISTS duration;
                ALTER TABLE async_tasks DROP COLUMN IF EXISTS inference_id;
                UPDATE async_tasks SET status = 'pending' WHERE status IS NULL;
                ALTER TABLE async_tasks ALTER COLUMN status SET NOT NULL;
                ALTER TABLE async_tasks
                    ADD CONSTRAINT async_tasks_parent_id_fkey
                    FOREIGN KEY (parent_id) REFERENCES async_tasks(id);
            END IF;
        END $$;
        """
    )
