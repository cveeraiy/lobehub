"""Add file_chunks parity table.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-23
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            chunk_id_type text;
        BEGIN
            SELECT format_type(a.atttypid, a.atttypmod)
            INTO chunk_id_type
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = current_schema()
              AND c.relname = 'chunks'
              AND a.attname = 'id'
              AND NOT a.attisdropped;

            IF chunk_id_type IS NULL THEN
                RAISE EXCEPTION 'Cannot create file_chunks: chunks.id column was not found';
            END IF;

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS file_chunks (
                    file_id VARCHAR REFERENCES files(id) ON DELETE CASCADE,
                    chunk_id %s REFERENCES chunks(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT file_chunks_file_id_chunk_id_pk PRIMARY KEY (file_id, chunk_id)
                )',
                chunk_id_type
            );
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS file_chunks_user_id_idx ON file_chunks (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS file_chunks_file_id_idx ON file_chunks (file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS file_chunks_chunk_id_idx ON file_chunks (chunk_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS file_chunks")
