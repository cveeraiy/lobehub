"""Align message_queries with canonical schema.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-23
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('message_queries') IS NOT NULL THEN
                ALTER TABLE message_queries
                    ADD COLUMN IF NOT EXISTS client_id text;
                ALTER TABLE message_queries
                    DROP COLUMN IF EXISTS created_at,
                    DROP COLUMN IF EXISTS rag_type;

                CREATE UNIQUE INDEX IF NOT EXISTS message_queries_client_id_user_id_unique
                    ON message_queries (client_id, user_id);
                CREATE INDEX IF NOT EXISTS message_queries_embeddings_id_idx
                    ON message_queries (embeddings_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('message_queries') IS NOT NULL THEN
                DROP INDEX IF EXISTS message_queries_client_id_user_id_unique;
                DROP INDEX IF EXISTS message_queries_embeddings_id_idx;
                ALTER TABLE message_queries
                    DROP COLUMN IF EXISTS client_id,
                    ADD COLUMN IF NOT EXISTS rag_type varchar,
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now();
            END IF;
        END $$;
        """
    )
