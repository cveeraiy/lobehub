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


def _add_column_if_not_exists(table, column):
    """Add a column only if it doesn't already exist (idempotent)."""
    op.execute(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
        f"{column.compile(dialect=op.get_bind().dialect)}"
    )


def upgrade() -> None:
    # ── agent_documents: add VFS columns (idempotent) ─────────────────
    conn = op.get_bind()
    for col_name, col_ddl in [
        ("access_self", "INTEGER DEFAULT 31"),
        ("access_shared", "INTEGER DEFAULT 0"),
        ("access_public", "INTEGER DEFAULT 0"),
        ("template_id", "VARCHAR(100)"),
        ("policy", "JSON"),
        ("policy_load_position", "VARCHAR(50) DEFAULT 'before-first-user'"),
        ("policy_load_format", "VARCHAR(20) DEFAULT 'raw'"),
        ("policy_load_rule", "VARCHAR(50) DEFAULT 'always'"),
        ("deleted_by_user_id", "VARCHAR"),
    ]:
        conn.execute(sa.text(
            f"ALTER TABLE agent_documents ADD COLUMN IF NOT EXISTS {col_name} {col_ddl}"
        ))

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

    # FK for deleted_by_user_id (idempotent via DO block)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'agent_documents_deleted_by_user_id_fkey'
            ) THEN
                ALTER TABLE agent_documents
                    ADD CONSTRAINT agent_documents_deleted_by_user_id_fkey
                    FOREIGN KEY (deleted_by_user_id) REFERENCES users(id);
            END IF;
        END $$;
    """)


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
