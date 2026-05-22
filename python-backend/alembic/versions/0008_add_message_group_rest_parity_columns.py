"""Add message group REST parity columns.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-22
"""

from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS parent_group_id VARCHAR(255)")
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS title VARCHAR(255)")
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS type TEXT")
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS content TEXT")
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS editor_data JSONB")
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS metadata JSONB")
    op.execute("ALTER TABLE message_groups ADD COLUMN IF NOT EXISTS client_id VARCHAR(255)")

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS message_groups_client_id_user_id_unique "
        "ON message_groups (client_id, user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS message_groups_type_idx ON message_groups (type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS message_groups_parent_group_id_idx "
        "ON message_groups (parent_group_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS message_groups_parent_message_id_idx "
        "ON message_groups (parent_message_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS message_groups_parent_message_id_idx")
    op.execute("DROP INDEX IF EXISTS message_groups_parent_group_id_idx")
    op.execute("DROP INDEX IF EXISTS message_groups_type_idx")
    op.execute("DROP INDEX IF EXISTS message_groups_client_id_user_id_unique")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS client_id")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS metadata")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS editor_data")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS content")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS type")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS description")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS title")
    op.execute("ALTER TABLE message_groups DROP COLUMN IF EXISTS parent_group_id")
