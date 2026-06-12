"""Align safe scalar drift with Drizzle.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.ai_providers') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'ai_providers' AND column_name = 'enabled'
               ) THEN
                ALTER TABLE ai_providers ALTER COLUMN enabled DROP NOT NULL;
            END IF;

            IF to_regclass('public.knowledge_bases') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'knowledge_bases' AND column_name = 'is_public'
               ) THEN
                ALTER TABLE knowledge_bases ALTER COLUMN is_public DROP NOT NULL;
            END IF;

            IF to_regclass('public.user_memories') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories' AND column_name = 'accessed_count'
               ) THEN
                ALTER TABLE user_memories
                    ALTER COLUMN accessed_count TYPE bigint USING accessed_count::bigint,
                    ALTER COLUMN accessed_count DROP NOT NULL;
            END IF;

            IF to_regclass('public.user_memories_contexts') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories_contexts' AND column_name = 'score_impact'
               ) THEN
                ALTER TABLE user_memories_contexts
                    ALTER COLUMN score_impact TYPE numeric USING score_impact::numeric;
            END IF;

            IF to_regclass('public.user_memories_contexts') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories_contexts' AND column_name = 'score_urgency'
               ) THEN
                ALTER TABLE user_memories_contexts
                    ALTER COLUMN score_urgency TYPE numeric USING score_urgency::numeric;
            END IF;

            IF to_regclass('public.user_memories_preferences') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories_preferences' AND column_name = 'score_priority'
               ) THEN
                ALTER TABLE user_memories_preferences
                    ALTER COLUMN score_priority TYPE numeric USING score_priority::numeric;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.user_memories_preferences') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories_preferences' AND column_name = 'score_priority'
               ) THEN
                ALTER TABLE user_memories_preferences
                    ALTER COLUMN score_priority TYPE double precision USING score_priority::double precision;
            END IF;

            IF to_regclass('public.user_memories_contexts') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories_contexts' AND column_name = 'score_urgency'
               ) THEN
                ALTER TABLE user_memories_contexts
                    ALTER COLUMN score_urgency TYPE double precision USING score_urgency::double precision;
            END IF;

            IF to_regclass('public.user_memories_contexts') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories_contexts' AND column_name = 'score_impact'
               ) THEN
                ALTER TABLE user_memories_contexts
                    ALTER COLUMN score_impact TYPE double precision USING score_impact::double precision;
            END IF;

            IF to_regclass('public.user_memories') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'user_memories' AND column_name = 'accessed_count'
               ) THEN
                UPDATE user_memories SET accessed_count = 0 WHERE accessed_count IS NULL;
                ALTER TABLE user_memories
                    ALTER COLUMN accessed_count TYPE integer USING accessed_count::integer,
                    ALTER COLUMN accessed_count SET NOT NULL;
            END IF;

            IF to_regclass('public.knowledge_bases') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'knowledge_bases' AND column_name = 'is_public'
               ) THEN
                UPDATE knowledge_bases SET is_public = false WHERE is_public IS NULL;
                ALTER TABLE knowledge_bases ALTER COLUMN is_public SET NOT NULL;
            END IF;

            IF to_regclass('public.ai_providers') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'ai_providers' AND column_name = 'enabled'
               ) THEN
                UPDATE ai_providers SET enabled = true WHERE enabled IS NULL;
                ALTER TABLE ai_providers ALTER COLUMN enabled SET NOT NULL;
            END IF;
        END $$;
        """
    )
