"""Align API key storage with TypeScript implementation.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-25 00:00:00.000000
"""

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.api_keys') IS NOT NULL THEN
                ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS key varchar(256);
                CREATE UNIQUE INDEX IF NOT EXISTS api_keys_key_unique ON api_keys (key);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.api_keys') IS NOT NULL THEN
                DROP INDEX IF EXISTS api_keys_key_unique;
                ALTER TABLE api_keys DROP COLUMN IF EXISTS key;
            END IF;
        END $$;
        """
    )
