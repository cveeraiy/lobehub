"""Align UUID runtime columns with Python canonical schema.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-23
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            item record;
            invalid_count bigint;
            uuid_pattern constant text := '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
        BEGIN
            ALTER TABLE IF EXISTS embeddings DROP CONSTRAINT IF EXISTS embeddings_chunk_id_fkey;
            ALTER TABLE IF EXISTS document_chunks DROP CONSTRAINT IF EXISTS document_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS file_chunks DROP CONSTRAINT IF EXISTS file_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS message_chunks DROP CONSTRAINT IF EXISTS message_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS message_query_chunks DROP CONSTRAINT IF EXISTS message_query_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS message_query_chunks DROP CONSTRAINT IF EXISTS message_query_chunks_query_id_fkey;
            ALTER TABLE IF EXISTS unstructured_chunks DROP CONSTRAINT IF EXISTS unstructured_chunks_composite_id_fkey;
            ALTER TABLE IF EXISTS message_queries DROP CONSTRAINT IF EXISTS message_queries_embeddings_id_fkey;
            ALTER TABLE IF EXISTS rag_eval_evaluation_records
                DROP CONSTRAINT IF EXISTS rag_eval_evaluation_records_question_embedding_id_fkey;
            ALTER TABLE IF EXISTS files DROP CONSTRAINT IF EXISTS files_chunk_task_id_fkey;
            ALTER TABLE IF EXISTS files DROP CONSTRAINT IF EXISTS files_embedding_task_id_fkey;
            ALTER TABLE IF EXISTS generation_batches DROP CONSTRAINT IF EXISTS generation_batches_async_task_id_fkey;
            ALTER TABLE IF EXISTS async_tasks DROP CONSTRAINT IF EXISTS async_tasks_parent_id_fkey;

            IF to_regclass('async_tasks') IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'async_tasks'
                      AND column_name = 'parent_id'
                )
            THEN
                ALTER TABLE async_tasks ADD COLUMN parent_id uuid;
            END IF;

            FOR item IN
                SELECT * FROM (VALUES
                    ('chunks', 'id'),
                    ('embeddings', 'id'),
                    ('embeddings', 'chunk_id'),
                    ('document_chunks', 'chunk_id'),
                    ('file_chunks', 'chunk_id'),
                    ('message_chunks', 'chunk_id'),
                    ('message_queries', 'id'),
                    ('message_queries', 'embeddings_id'),
                    ('message_query_chunks', 'query_id'),
                    ('message_query_chunks', 'chunk_id'),
                    ('unstructured_chunks', 'id'),
                    ('unstructured_chunks', 'composite_id'),
                    ('rag_eval_evaluation_records', 'question_embedding_id'),
                    ('async_tasks', 'id'),
                    ('async_tasks', 'parent_id'),
                    ('files', 'chunk_task_id'),
                    ('files', 'embedding_task_id'),
                    ('generation_batches', 'async_task_id')
                ) AS columns(table_name, column_name)
            LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = item.table_name
                      AND column_name = item.column_name
                      AND udt_name <> 'uuid'
                )
                THEN
                    EXECUTE format(
                        'SELECT count(*) FROM %I WHERE %I IS NOT NULL AND %I::text !~* %L',
                        item.table_name,
                        item.column_name,
                        item.column_name,
                        uuid_pattern
                    )
                    INTO invalid_count;

                    IF invalid_count > 0 THEN
                        RAISE EXCEPTION
                            'Cannot convert %.% to uuid: % non-UUID values found',
                            item.table_name,
                            item.column_name,
                            invalid_count;
                    END IF;

                    EXECUTE format(
                        'ALTER TABLE %I ALTER COLUMN %I TYPE uuid USING NULLIF(%I::text, '''')::uuid',
                        item.table_name,
                        item.column_name,
                        item.column_name
                    );
                END IF;
            END LOOP;

            ALTER TABLE IF EXISTS chunks ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE IF EXISTS embeddings ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE IF EXISTS message_queries ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE IF EXISTS unstructured_chunks ALTER COLUMN id SET DEFAULT gen_random_uuid();
            ALTER TABLE IF EXISTS async_tasks ALTER COLUMN id SET DEFAULT gen_random_uuid();

            ALTER TABLE IF EXISTS embeddings
                ADD CONSTRAINT embeddings_chunk_id_fkey
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
            ALTER TABLE IF EXISTS document_chunks
                ADD CONSTRAINT document_chunks_chunk_id_fkey
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
            ALTER TABLE IF EXISTS file_chunks
                ADD CONSTRAINT file_chunks_chunk_id_fkey
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
            ALTER TABLE IF EXISTS message_chunks
                ADD CONSTRAINT message_chunks_chunk_id_fkey
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
            ALTER TABLE IF EXISTS message_query_chunks
                ADD CONSTRAINT message_query_chunks_chunk_id_fkey
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE;
            ALTER TABLE IF EXISTS message_query_chunks
                ADD CONSTRAINT message_query_chunks_query_id_fkey
                FOREIGN KEY (query_id) REFERENCES message_queries(id) ON DELETE CASCADE;
            ALTER TABLE IF EXISTS unstructured_chunks
                ADD CONSTRAINT unstructured_chunks_composite_id_fkey
                FOREIGN KEY (composite_id) REFERENCES chunks(id) ON DELETE CASCADE;
            ALTER TABLE IF EXISTS message_queries
                ADD CONSTRAINT message_queries_embeddings_id_fkey
                FOREIGN KEY (embeddings_id) REFERENCES embeddings(id) ON DELETE SET NULL;
            ALTER TABLE IF EXISTS rag_eval_evaluation_records
                ADD CONSTRAINT rag_eval_evaluation_records_question_embedding_id_fkey
                FOREIGN KEY (question_embedding_id) REFERENCES embeddings(id);
            ALTER TABLE IF EXISTS files
                ADD CONSTRAINT files_chunk_task_id_fkey
                FOREIGN KEY (chunk_task_id) REFERENCES async_tasks(id) ON DELETE SET NULL;
            ALTER TABLE IF EXISTS files
                ADD CONSTRAINT files_embedding_task_id_fkey
                FOREIGN KEY (embedding_task_id) REFERENCES async_tasks(id) ON DELETE SET NULL;
            ALTER TABLE IF EXISTS generation_batches
                ADD CONSTRAINT generation_batches_async_task_id_fkey
                FOREIGN KEY (async_task_id) REFERENCES async_tasks(id);
            ALTER TABLE IF EXISTS async_tasks
                ADD CONSTRAINT async_tasks_parent_id_fkey
                FOREIGN KEY (parent_id) REFERENCES async_tasks(id);
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            item record;
        BEGIN
            ALTER TABLE IF EXISTS embeddings DROP CONSTRAINT IF EXISTS embeddings_chunk_id_fkey;
            ALTER TABLE IF EXISTS document_chunks DROP CONSTRAINT IF EXISTS document_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS file_chunks DROP CONSTRAINT IF EXISTS file_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS message_chunks DROP CONSTRAINT IF EXISTS message_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS message_query_chunks DROP CONSTRAINT IF EXISTS message_query_chunks_chunk_id_fkey;
            ALTER TABLE IF EXISTS message_query_chunks DROP CONSTRAINT IF EXISTS message_query_chunks_query_id_fkey;
            ALTER TABLE IF EXISTS unstructured_chunks DROP CONSTRAINT IF EXISTS unstructured_chunks_composite_id_fkey;
            ALTER TABLE IF EXISTS message_queries DROP CONSTRAINT IF EXISTS message_queries_embeddings_id_fkey;
            ALTER TABLE IF EXISTS rag_eval_evaluation_records
                DROP CONSTRAINT IF EXISTS rag_eval_evaluation_records_question_embedding_id_fkey;
            ALTER TABLE IF EXISTS files DROP CONSTRAINT IF EXISTS files_chunk_task_id_fkey;
            ALTER TABLE IF EXISTS files DROP CONSTRAINT IF EXISTS files_embedding_task_id_fkey;
            ALTER TABLE IF EXISTS generation_batches DROP CONSTRAINT IF EXISTS generation_batches_async_task_id_fkey;
            ALTER TABLE IF EXISTS async_tasks DROP CONSTRAINT IF EXISTS async_tasks_parent_id_fkey;

            FOR item IN
                SELECT * FROM (VALUES
                    ('chunks', 'id'),
                    ('embeddings', 'id'),
                    ('embeddings', 'chunk_id'),
                    ('document_chunks', 'chunk_id'),
                    ('file_chunks', 'chunk_id'),
                    ('message_chunks', 'chunk_id'),
                    ('message_queries', 'id'),
                    ('message_queries', 'embeddings_id'),
                    ('message_query_chunks', 'query_id'),
                    ('message_query_chunks', 'chunk_id'),
                    ('unstructured_chunks', 'id'),
                    ('unstructured_chunks', 'composite_id'),
                    ('rag_eval_evaluation_records', 'question_embedding_id'),
                    ('async_tasks', 'id'),
                    ('async_tasks', 'parent_id'),
                    ('files', 'chunk_task_id'),
                    ('files', 'embedding_task_id'),
                    ('generation_batches', 'async_task_id')
                ) AS columns(table_name, column_name)
            LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = item.table_name
                      AND column_name = item.column_name
                      AND udt_name = 'uuid'
                )
                THEN
                    EXECUTE format(
                        'ALTER TABLE %I ALTER COLUMN %I DROP DEFAULT',
                        item.table_name,
                        item.column_name
                    );
                    EXECUTE format(
                        'ALTER TABLE %I ALTER COLUMN %I TYPE varchar USING %I::text',
                        item.table_name,
                        item.column_name,
                        item.column_name
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
