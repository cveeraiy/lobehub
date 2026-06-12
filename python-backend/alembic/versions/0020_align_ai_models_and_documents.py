"""Align AI model and document parity drift.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.ai_models') IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'ai_models' AND column_name = 'organization'
                ) THEN
                    ALTER TABLE ai_models ADD COLUMN organization varchar(100);
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'ai_models' AND column_name = 'enabled'
                ) THEN
                    ALTER TABLE ai_models ALTER COLUMN enabled DROP NOT NULL;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'ai_models' AND column_name = 'type'
                ) THEN
                    UPDATE ai_models SET type = 'chat' WHERE type IS NULL;
                    ALTER TABLE ai_models
                        ALTER COLUMN type TYPE varchar(20) USING type::varchar(20),
                        ALTER COLUMN type SET DEFAULT 'chat',
                        ALTER COLUMN type SET NOT NULL;
                END IF;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS documents_slug_user_id_unique
            ON documents (slug, user_id)
            WHERE slug IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS documents_slug_user_id_unique")
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.ai_models') IS NOT NULL THEN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'ai_models' AND column_name = 'type'
                ) THEN
                    ALTER TABLE ai_models
                        ALTER COLUMN type DROP NOT NULL,
                        ALTER COLUMN type TYPE varchar(255) USING type::varchar(255);
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'ai_models' AND column_name = 'enabled'
                ) THEN
                    UPDATE ai_models SET enabled = true WHERE enabled IS NULL;
                    ALTER TABLE ai_models ALTER COLUMN enabled SET NOT NULL;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'ai_models' AND column_name = 'organization'
                ) THEN
                    ALTER TABLE ai_models DROP COLUMN organization;
                END IF;
            END IF;
        END $$;
        """
    )
