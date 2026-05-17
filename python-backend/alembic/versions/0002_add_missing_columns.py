"""Add missing columns for agent_documents VFS and messages.thread_id.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_documents: add VFS columns ──────────────────────────────
    # The Python model expects access_self/access_shared/access_public
    # but the DB only has access_mask. Add the new columns.
    op.add_column(
        "agent_documents",
        sa.Column("access_self", sa.Integer(), nullable=True, server_default="31"),
    )
    op.add_column(
        "agent_documents",
        sa.Column("access_shared", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "agent_documents",
        sa.Column("access_public", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "agent_documents",
        sa.Column("template_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "agent_documents",
        sa.Column("policy", sa.JSON(), nullable=True),
    )
    op.add_column(
        "agent_documents",
        sa.Column("policy_load_position", sa.String(50), nullable=True, server_default="before-first-user"),
    )
    op.add_column(
        "agent_documents",
        sa.Column("policy_load_format", sa.String(20), nullable=True, server_default="raw"),
    )
    op.add_column(
        "agent_documents",
        sa.Column("policy_load_rule", sa.String(50), nullable=True, server_default="always"),
    )
    op.add_column(
        "agent_documents",
        sa.Column("deleted_by_user_id", sa.String(), nullable=True),
    )

    # Create indexes that the model declares (only if they don't already exist)
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS agent_documents_access_self_idx ON agent_documents (access_self)",
        "CREATE INDEX IF NOT EXISTS agent_documents_access_shared_idx ON agent_documents (access_shared)",
        "CREATE INDEX IF NOT EXISTS agent_documents_access_public_idx ON agent_documents (access_public)",
        "CREATE INDEX IF NOT EXISTS agent_documents_template_id_idx ON agent_documents (template_id)",
        "CREATE INDEX IF NOT EXISTS agent_documents_policy_load_position_idx ON agent_documents (policy_load_position)",
        "CREATE INDEX IF NOT EXISTS agent_documents_policy_load_format_idx ON agent_documents (policy_load_format)",
        "CREATE INDEX IF NOT EXISTS agent_documents_policy_load_rule_idx ON agent_documents (policy_load_rule)",
        "CREATE INDEX IF NOT EXISTS agent_documents_deleted_at_idx ON agent_documents (deleted_at)",
    ]:
        op.execute(idx_sql)

    # FK for deleted_by_user_id
    op.execute(
        "ALTER TABLE agent_documents "
        "ADD CONSTRAINT agent_documents_deleted_by_user_id_fkey "
        "FOREIGN KEY (deleted_by_user_id) REFERENCES users(id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agent_documents DROP CONSTRAINT IF EXISTS agent_documents_deleted_by_user_id_fkey")
    op.execute("DROP INDEX IF EXISTS agent_documents_access_self_idx")
    op.execute("DROP INDEX IF EXISTS agent_documents_access_shared_idx")
    op.execute("DROP INDEX IF EXISTS agent_documents_access_public_idx")
    op.execute("DROP INDEX IF EXISTS agent_documents_template_id_idx")
    op.execute("DROP INDEX IF EXISTS agent_documents_policy_load_position_idx")
    op.execute("DROP INDEX IF EXISTS agent_documents_policy_load_format_idx")
    op.execute("DROP INDEX IF EXISTS agent_documents_policy_load_rule_idx")
    op.execute("DROP INDEX IF EXISTS agent_documents_deleted_at_idx")
    op.drop_column("agent_documents", "deleted_by_user_id")
    op.drop_column("agent_documents", "policy_load_rule")
    op.drop_column("agent_documents", "policy_load_format")
    op.drop_column("agent_documents", "policy_load_position")
    op.drop_column("agent_documents", "policy")
    op.drop_column("agent_documents", "template_id")
    op.drop_column("agent_documents", "access_public")
    op.drop_column("agent_documents", "access_shared")
    op.drop_column("agent_documents", "access_self")
