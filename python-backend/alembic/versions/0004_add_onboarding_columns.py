"""Add agent_onboarding, onboarding, interests columns to users table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-16
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS agent_onboarding JSONB")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding JSONB")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS interests JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS interests")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS onboarding")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS agent_onboarding")
