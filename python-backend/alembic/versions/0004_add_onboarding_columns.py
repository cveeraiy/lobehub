"""Add agent_onboarding, onboarding, interests columns to users table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("agent_onboarding", JSONB, nullable=True))
    op.add_column("users", sa.Column("onboarding", JSONB, nullable=True))
    op.add_column("users", sa.Column("interests", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "interests")
    op.drop_column("users", "onboarding")
    op.drop_column("users", "agent_onboarding")
