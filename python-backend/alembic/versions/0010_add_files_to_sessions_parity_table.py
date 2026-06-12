"""Add files_to_sessions parity table.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-23
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS files_to_sessions (
            file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT files_to_sessions_file_id_session_id_pk PRIMARY KEY (file_id, session_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS files_to_sessions_user_id_idx ON files_to_sessions (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS files_to_sessions_file_id_idx ON files_to_sessions (file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS files_to_sessions_session_id_idx ON files_to_sessions (session_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS files_to_sessions")
