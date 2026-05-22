"""Add enabled column to api_keys.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-22
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE')
    op.execute('UPDATE api_keys SET enabled = TRUE WHERE enabled IS NULL')


def downgrade() -> None:
    op.execute('ALTER TABLE api_keys DROP COLUMN IF EXISTS enabled')
