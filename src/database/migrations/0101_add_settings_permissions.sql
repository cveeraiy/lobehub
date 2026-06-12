ALTER TABLE "user_settings" ADD COLUMN IF NOT EXISTS "settings_permissions" jsonb DEFAULT '{"agentSettings": false, "systemSettings": false}';
