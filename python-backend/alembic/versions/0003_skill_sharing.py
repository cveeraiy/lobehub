"""Add skill sharing: visibility column + agent_skill_shares junction table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_skills: add visibility column ──────────────────────────
    op.add_column(
        "agent_skills",
        sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS agent_skills_visibility_idx ON agent_skills (visibility)")

    # ── agent_skill_shares: junction table ───────────────────────────
    op.create_table(
        "agent_skill_shares",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("skill_id", sa.String(255), nullable=False),
        sa.Column("shared_with_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("skill_id", "shared_with_user_id", name="agent_skill_shares_unique"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS agent_skill_shares_skill_idx ON agent_skill_shares (skill_id)")
    op.execute("CREATE INDEX IF NOT EXISTS agent_skill_shares_user_idx ON agent_skill_shares (shared_with_user_id)")

    # FK: skill_id → agent_skills.id (CASCADE delete)
    op.execute(
        "ALTER TABLE agent_skill_shares "
        "ADD CONSTRAINT agent_skill_shares_skill_id_fkey "
        "FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE"
    )
    # FK: shared_with_user_id → users.id
    op.execute(
        "ALTER TABLE agent_skill_shares "
        "ADD CONSTRAINT agent_skill_shares_user_id_fkey "
        "FOREIGN KEY (shared_with_user_id) REFERENCES users(id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agent_skill_shares DROP CONSTRAINT IF EXISTS agent_skill_shares_user_id_fkey")
    op.execute("ALTER TABLE agent_skill_shares DROP CONSTRAINT IF EXISTS agent_skill_shares_skill_id_fkey")
    op.drop_table("agent_skill_shares")
    op.execute("DROP INDEX IF EXISTS agent_skills_visibility_idx")
    op.drop_column("agent_skills", "visibility")
