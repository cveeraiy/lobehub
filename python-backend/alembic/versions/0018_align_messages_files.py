"""Align messages_files with canonical join schema.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-23
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE IF EXISTS messages_files
            DROP COLUMN IF EXISTS created_at
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE IF EXISTS messages_files
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
        """
    )
