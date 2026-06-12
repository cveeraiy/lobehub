"""Align agent relation table parity drift.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            pk_name text;
        BEGIN
            IF to_regclass('public.agents_knowledge_bases') IS NOT NULL THEN
                ALTER TABLE agents_knowledge_bases ALTER COLUMN enabled DROP NOT NULL;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_knowledge_bases' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE agents_knowledge_bases ADD COLUMN updated_at timestamp without time zone DEFAULT now() NOT NULL;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_knowledge_bases' AND column_name = 'accessed_at'
                ) THEN
                    ALTER TABLE agents_knowledge_bases ADD COLUMN accessed_at timestamp without time zone DEFAULT now() NOT NULL;
                END IF;
            END IF;

            IF to_regclass('public.agents_files') IS NOT NULL THEN
                ALTER TABLE agents_files ALTER COLUMN enabled DROP NOT NULL;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_files' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE agents_files ADD COLUMN updated_at timestamp without time zone DEFAULT now() NOT NULL;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_files' AND column_name = 'accessed_at'
                ) THEN
                    ALTER TABLE agents_files ADD COLUMN accessed_at timestamp without time zone DEFAULT now() NOT NULL;
                END IF;

                SELECT conname INTO pk_name
                FROM pg_constraint
                WHERE conrelid = 'public.agents_files'::regclass AND contype = 'p'
                LIMIT 1;

                IF pk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE agents_files DROP CONSTRAINT %I', pk_name);
                END IF;

                ALTER TABLE agents_files ADD CONSTRAINT agents_files_file_id_agent_id_user_id_pk
                    PRIMARY KEY (file_id, agent_id, user_id);
            END IF;

            IF to_regclass('public.chat_groups_agents') IS NOT NULL THEN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chat_groups_agents' AND column_name = 'group_id'
                ) THEN
                    ALTER TABLE chat_groups_agents DROP COLUMN group_id;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chat_groups_agents' AND column_name = 'chat_group_id'
                ) THEN
                    ALTER TABLE chat_groups_agents ALTER COLUMN chat_group_id SET NOT NULL;
                END IF;

                ALTER TABLE chat_groups_agents
                    ALTER COLUMN enabled DROP NOT NULL,
                    ALTER COLUMN "order" DROP NOT NULL;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chat_groups_agents' AND column_name = 'accessed_at'
                ) THEN
                    ALTER TABLE chat_groups_agents ADD COLUMN accessed_at timestamp without time zone DEFAULT now() NOT NULL;
                END IF;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            pk_name text;
        BEGIN
            IF to_regclass('public.chat_groups_agents') IS NOT NULL THEN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chat_groups_agents' AND column_name = 'accessed_at'
                ) THEN
                    ALTER TABLE chat_groups_agents DROP COLUMN accessed_at;
                END IF;

                UPDATE chat_groups_agents SET enabled = true WHERE enabled IS NULL;
                UPDATE chat_groups_agents SET "order" = 0 WHERE "order" IS NULL;
                ALTER TABLE chat_groups_agents
                    ALTER COLUMN enabled SET NOT NULL,
                    ALTER COLUMN "order" SET NOT NULL;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chat_groups_agents' AND column_name = 'group_id'
                ) THEN
                    ALTER TABLE chat_groups_agents ADD COLUMN group_id varchar;
                    UPDATE chat_groups_agents SET group_id = chat_group_id;
                    ALTER TABLE chat_groups_agents ALTER COLUMN group_id SET NOT NULL;
                END IF;
            END IF;

            IF to_regclass('public.agents_files') IS NOT NULL THEN
                SELECT conname INTO pk_name
                FROM pg_constraint
                WHERE conrelid = 'public.agents_files'::regclass AND contype = 'p'
                LIMIT 1;

                IF pk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE agents_files DROP CONSTRAINT %I', pk_name);
                END IF;
                ALTER TABLE agents_files ADD CONSTRAINT agents_files_agent_id_file_id_pk PRIMARY KEY (agent_id, file_id);

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_files' AND column_name = 'accessed_at'
                ) THEN
                    ALTER TABLE agents_files DROP COLUMN accessed_at;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_files' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE agents_files DROP COLUMN updated_at;
                END IF;

                UPDATE agents_files SET enabled = true WHERE enabled IS NULL;
                ALTER TABLE agents_files ALTER COLUMN enabled SET NOT NULL;
            END IF;

            IF to_regclass('public.agents_knowledge_bases') IS NOT NULL THEN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_knowledge_bases' AND column_name = 'accessed_at'
                ) THEN
                    ALTER TABLE agents_knowledge_bases DROP COLUMN accessed_at;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'agents_knowledge_bases' AND column_name = 'updated_at'
                ) THEN
                    ALTER TABLE agents_knowledge_bases DROP COLUMN updated_at;
                END IF;

                UPDATE agents_knowledge_bases SET enabled = true WHERE enabled IS NULL;
                ALTER TABLE agents_knowledge_bases ALTER COLUMN enabled SET NOT NULL;
            END IF;
        END $$;
        """
    )
