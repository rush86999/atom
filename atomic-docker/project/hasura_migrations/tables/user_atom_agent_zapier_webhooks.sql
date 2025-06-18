-- Migration for creating the user_atom_agent_zapier_webhooks table

CREATE TABLE "public"."user_atom_agent_zapier_webhooks" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "user_id" uuid NOT NULL,
    "zap_name" text NOT NULL,
    "webhook_url" text NOT NULL, -- Should be encrypted at the application layer before storage
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("id"),
    FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON UPDATE restrict ON DELETE cascade,
    UNIQUE ("user_id", "zap_name")
);

-- Assuming the set_current_timestamp_updated_at function already exists globally from previous migrations
-- (e.g., from user_atom_agent_google_calendar_tokens.sql or a shared utility migration).
-- If it does not exist or this is the first table needing it in this specific migration set,
-- the function definition should be included here:
-- CREATE OR REPLACE FUNCTION "public"."set_current_timestamp_updated_at"()
-- RETURNS TRIGGER AS $$
-- DECLARE
--   _new record;
-- BEGIN
--   _new := NEW;
--   _new."updated_at" = NOW();
--   RETURN _new;
-- END;
-- $$ LANGUAGE plpgsql;

CREATE TRIGGER "set_public_user_atom_agent_zapier_webhooks_updated_at"
BEFORE UPDATE ON "public"."user_atom_agent_zapier_webhooks"
FOR EACH ROW
EXECUTE PROCEDURE "public"."set_current_timestamp_updated_at"();

COMMENT ON TRIGGER "set_public_user_atom_agent_zapier_webhooks_updated_at" ON "public"."user_atom_agent_zapier_webhooks"
IS 'trigger to set value of column "updated_at" to current timestamp on row update';

COMMENT ON TABLE "public"."user_atom_agent_zapier_webhooks"
IS 'Stores user-configured Zapier webhooks for the Atom Agent to trigger.';

COMMENT ON COLUMN "public"."user_atom_agent_zapier_webhooks"."user_id"
IS 'Foreign key referencing the user who owns this webhook configuration.';

COMMENT ON COLUMN "public"."user_atom_agent_zapier_webhooks"."zap_name"
IS 'User-defined alias for the Zap, e.g., "Log to Sheet", "Send Slack Message". Must be unique per user.';

COMMENT ON COLUMN "public"."user_atom_agent_zapier_webhooks"."webhook_url"
IS 'Stores the encrypted Zapier webhook URL provided by the user.';
