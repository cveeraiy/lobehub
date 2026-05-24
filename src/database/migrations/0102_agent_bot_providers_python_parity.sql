-- Align legacy local agent_bot_providers tables with the Python REST bot runtime.
-- Older development databases may have webhook_url/webhook_secret columns,
-- credentials stored as json, no application_id column, and a unique
-- (agent_id, platform) constraint. The Python runtime expects application_id
-- routing plus text credentials.

ALTER TABLE "agent_bot_providers" ADD COLUMN IF NOT EXISTS "application_id" varchar(255);
--> statement-breakpoint

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'agent_bot_providers'
      AND column_name = 'webhook_url'
  ) THEN
    UPDATE "agent_bot_providers"
    SET "application_id" = COALESCE(
      NULLIF("application_id", ''),
      NULLIF("webhook_url", ''),
      "id"::text
    )
    WHERE "application_id" IS NULL OR "application_id" = '';
  ELSE
    UPDATE "agent_bot_providers"
    SET "application_id" = COALESCE(NULLIF("application_id", ''), "id"::text)
    WHERE "application_id" IS NULL OR "application_id" = '';
  END IF;
END $$;
--> statement-breakpoint

ALTER TABLE "agent_bot_providers" ALTER COLUMN "application_id" SET NOT NULL;
--> statement-breakpoint

ALTER TABLE "agent_bot_providers" ALTER COLUMN "platform" TYPE varchar(50);
--> statement-breakpoint

ALTER TABLE "agent_bot_providers"
  ALTER COLUMN "credentials" TYPE text
  USING CASE
    WHEN "credentials" IS NULL THEN NULL
    ELSE "credentials"::text
  END;
--> statement-breakpoint

ALTER TABLE "agent_bot_providers" ALTER COLUMN "settings" TYPE jsonb USING COALESCE("settings"::jsonb, '{}'::jsonb);
--> statement-breakpoint

ALTER TABLE "agent_bot_providers" DROP CONSTRAINT IF EXISTS "agent_bot_providers_agent_id_platform_unique";
--> statement-breakpoint

DROP INDEX IF EXISTS "agent_bot_providers_agent_id_platform_unique";
--> statement-breakpoint

DROP INDEX IF EXISTS "agent_bot_providers_platform_app_id_unique";
--> statement-breakpoint

CREATE UNIQUE INDEX IF NOT EXISTS "agent_bot_providers_platform_app_id_unique"
ON "agent_bot_providers" USING btree ("platform", "application_id");
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "agent_bot_providers_platform_idx"
ON "agent_bot_providers" USING btree ("platform");
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "agent_bot_providers_agent_id_idx"
ON "agent_bot_providers" USING btree ("agent_id");
--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "agent_bot_providers_user_id_idx"
ON "agent_bot_providers" USING btree ("user_id");
