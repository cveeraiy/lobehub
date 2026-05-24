"""Align user tables with Drizzle schema.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-23
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS normalized_email TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS organization TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_expires TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number_verified BOOLEAN")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP WITH TIME ZONE DEFAULT now()")
    op.execute("UPDATE users SET banned = is_banned WHERE is_banned IS NOT NULL")
    op.execute("UPDATE users SET ban_expires = ban_expires_at WHERE ban_expires IS NULL AND ban_expires_at IS NOT NULL")
    op.execute("UPDATE users SET organization = org_id WHERE organization IS NULL AND org_id IS NOT NULL")
    op.execute("UPDATE users SET last_active_at = accessed_at WHERE last_active_at IS NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_unique ON users (username)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users (email)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_normalized_email_unique ON users (normalized_email)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_phone_unique ON users (phone)")
    op.execute("CREATE INDEX IF NOT EXISTS users_email_idx ON users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS users_username_idx ON users (username)")
    op.execute("CREATE INDEX IF NOT EXISTS users_banned_true_created_at_idx ON users (created_at) WHERE banned = true")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_banned")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS ban_expires_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS org_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS org_role")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS org_slug")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS key")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS terminal_color")

    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS settings_permissions JSONB")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'user_settings' AND column_name = 'user_id'
            ) THEN
                UPDATE user_settings SET id = user_id WHERE user_id IS NOT NULL;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE user_settings DROP CONSTRAINT IF EXISTS user_settings_user_id_unique")
    op.execute("DROP INDEX IF EXISTS ix_user_settings_user_id")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS user_id")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'user_settings_id_users_id_fk'
            ) THEN
                ALTER TABLE user_settings
                ADD CONSTRAINT user_settings_id_users_id_fk
                FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE user_settings DROP COLUMN IF EXISTS accessed_at")

    op.execute("ALTER TABLE user_installed_plugins ADD COLUMN IF NOT EXISTS source VARCHAR(255)")
    op.execute("UPDATE user_installed_plugins SET type = 'plugin' WHERE type IS NULL")
    op.execute("ALTER TABLE user_installed_plugins ALTER COLUMN type SET NOT NULL")
    op.execute("ALTER TABLE user_installed_plugins DROP CONSTRAINT IF EXISTS user_installed_plugins_pkey")
    op.execute(
        "ALTER TABLE user_installed_plugins DROP CONSTRAINT IF EXISTS user_installed_plugins_user_id_identifier_unique"
    )
    op.execute("ALTER TABLE user_installed_plugins DROP COLUMN IF EXISTS id")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'user_installed_plugins_user_id_identifier_pk'
            ) THEN
                ALTER TABLE user_installed_plugins
                ADD CONSTRAINT user_installed_plugins_user_id_identifier_pk
                PRIMARY KEY (user_id, identifier);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE user_installed_plugins DROP CONSTRAINT IF EXISTS user_installed_plugins_user_id_identifier_pk"
    )
    op.execute("ALTER TABLE user_installed_plugins ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS user_installed_plugins_user_id_identifier_unique "
        "ON user_installed_plugins (user_id, identifier)"
    )

    op.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS user_id TEXT")
    op.execute("UPDATE user_settings SET user_id = id WHERE user_id IS NULL")
    op.execute("ALTER TABLE user_settings DROP CONSTRAINT IF EXISTS user_settings_id_users_id_fk")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS user_settings_user_id_unique ON user_settings (user_id)")

    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_expires_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS org_id TEXT")
    op.execute("UPDATE users SET is_banned = banned WHERE banned IS NOT NULL")
    op.execute("UPDATE users SET ban_expires_at = ban_expires WHERE ban_expires_at IS NULL AND ban_expires IS NOT NULL")
    op.execute("UPDATE users SET org_id = organization WHERE org_id IS NULL AND organization IS NOT NULL")
