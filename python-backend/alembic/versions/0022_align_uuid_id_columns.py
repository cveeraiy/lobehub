"""Align UUID id columns with Drizzle.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


UUID_ID_TABLES = (
    "agent_bot_providers",
    "agent_documents",
    "task_dependencies",
    "task_documents",
    "task_topics",
)


def upgrade() -> None:
    for table in UUID_ID_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL
                   AND EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = '{table}' AND column_name = 'id'
                   ) THEN
                    ALTER TABLE {table}
                        ALTER COLUMN id TYPE uuid USING id::uuid;
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    for table in reversed(UUID_ID_TABLES):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL
                   AND EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = '{table}' AND column_name = 'id'
                   ) THEN
                    ALTER TABLE {table}
                        ALTER COLUMN id TYPE varchar(255) USING id::text;
                END IF;
            END $$;
            """
        )
