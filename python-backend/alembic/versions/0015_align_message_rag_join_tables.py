"""Align message RAG join tables with canonical schema.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-23
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            orphan_count bigint;
        BEGIN
            IF to_regclass('message_chunks') IS NOT NULL THEN
                ALTER TABLE message_chunks DROP COLUMN IF EXISTS created_at;
            END IF;

            IF to_regclass('message_query_chunks') IS NOT NULL THEN
                SELECT count(*)
                INTO orphan_count
                FROM message_query_chunks mqc
                LEFT JOIN messages m ON m.id = mqc.id
                WHERE m.id IS NULL;

                IF orphan_count > 0 THEN
                    RAISE EXCEPTION
                        'Cannot align message_query_chunks.id with messages.id: % orphan rows found',
                        orphan_count;
                END IF;

                ALTER TABLE message_query_chunks DROP CONSTRAINT IF EXISTS message_query_chunks_pkey;
                ALTER TABLE message_query_chunks
                    DROP CONSTRAINT IF EXISTS message_query_chunks_chunk_id_id_query_id_pk;
                ALTER TABLE message_query_chunks DROP CONSTRAINT IF EXISTS message_query_chunks_id_fkey;
                ALTER TABLE message_query_chunks DROP COLUMN IF EXISTS created_at;
                ALTER TABLE message_query_chunks
                    ALTER COLUMN id DROP DEFAULT,
                    ALTER COLUMN id SET NOT NULL,
                    ALTER COLUMN query_id SET NOT NULL,
                    ALTER COLUMN chunk_id SET NOT NULL,
                    ALTER COLUMN similarity TYPE numeric(6, 5) USING similarity::numeric(6, 5);

                ALTER TABLE message_query_chunks
                    ADD CONSTRAINT message_query_chunks_id_fkey
                    FOREIGN KEY (id) REFERENCES messages(id) ON DELETE CASCADE;
                ALTER TABLE message_query_chunks
                    ADD CONSTRAINT message_query_chunks_chunk_id_id_query_id_pk
                    PRIMARY KEY (chunk_id, id, query_id);

                CREATE INDEX IF NOT EXISTS message_query_chunks_message_id_idx
                    ON message_query_chunks (id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('message_chunks') IS NOT NULL THEN
                ALTER TABLE message_chunks
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now();
            END IF;

            IF to_regclass('message_query_chunks') IS NOT NULL THEN
                ALTER TABLE message_query_chunks
                    DROP CONSTRAINT IF EXISTS message_query_chunks_chunk_id_id_query_id_pk;
                ALTER TABLE message_query_chunks DROP CONSTRAINT IF EXISTS message_query_chunks_id_fkey;
                ALTER TABLE message_query_chunks
                    ADD CONSTRAINT message_query_chunks_pkey PRIMARY KEY (id);
                ALTER TABLE message_query_chunks
                    ALTER COLUMN similarity TYPE double precision USING similarity::double precision;
                ALTER TABLE message_query_chunks
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now();
            END IF;
        END $$;
        """
    )
