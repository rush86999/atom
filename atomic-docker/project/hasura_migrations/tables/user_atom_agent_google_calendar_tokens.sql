-- Migration for creating the user_atom_agent_google_calendar_tokens table
-- and setting up an updated_at trigger.

CREATE TABLE "public"."user_atom_agent_google_calendar_tokens" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "user_id" uuid NOT NULL,
    "access_token" text NOT NULL, -- Should be encrypted at the application layer before storage
    "refresh_token" text, -- Should be encrypted at the application layer before storage
    "expiry_date" timestamptz NOT NULL,
    "scope" text,
    "token_type" text, -- Added based on typical OAuth responses
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("id"),
    FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON UPDATE restrict ON DELETE cascade,
    UNIQUE ("user_id") -- Assuming one set of calendar tokens per user for Atom
);

-- Function and Trigger for auto-updating updated_at timestamp
-- (Assuming this function doesn't already exist globally for the project)
-- If it does exist, this part can be omitted from this specific migration.
CREATE OR REPLACE FUNCTION "public"."set_current_timestamp_updated_at"()
RETURNS TRIGGER AS $$
DECLARE
  _new record;
BEGIN
  _new := NEW;
  _new."updated_at" = NOW();
  RETURN _new;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER "set_public_user_atom_agent_google_calendar_tokens_updated_at"
BEFORE UPDATE ON "public"."user_atom_agent_google_calendar_tokens"
FOR EACH ROW
EXECUTE PROCEDURE "public"."set_current_timestamp_updated_at"();

COMMENT ON TRIGGER "set_public_user_atom_agent_google_calendar_tokens_updated_at" ON "public"."user_atom_agent_google_calendar_tokens"
IS 'trigger to set value of column "updated_at" to current timestamp on row update';

-- Comments on columns regarding encryption
COMMENT ON COLUMN "public"."user_atom_agent_google_calendar_tokens"."access_token" IS 'Should be encrypted at the application layer before storage';
COMMENT ON COLUMN "public"."user_atom_agent_google_calendar_tokens"."refresh_token" IS 'Should be encrypted at the application layer before storage';
