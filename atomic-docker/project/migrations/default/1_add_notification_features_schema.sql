-- File: migrations/default/1_add_notification_features_schema.sql
-- (Timestamp will be replaced by actual migration tool)

-- 0. Ensure a common function for updating 'updated_at' timestamps exists
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS TRIGGER AS $$
DECLARE
  _new RECORD;
BEGIN
  _new := NEW;
  _new."updated_at" = NOW();
  RETURN _new;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.set_current_timestamp_updated_at() IS 'Trigger function to set updated_at timestamp to current time upon row update.';

-- 1. Create table for User Slack Notification Configurations
CREATE TABLE IF NOT EXISTS public.user_slack_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public."User"(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL DEFAULT 'SCHEDULING_RESULTS',
    slack_webhook_url TEXT,
    slack_bot_token_secret_arn TEXT,
    slack_channel_id TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT user_slack_notification_type_unique UNIQUE (user_id, notification_type)
);

CREATE INDEX IF NOT EXISTS idx_user_slack_configurations_user_id ON public.user_slack_configurations(user_id);

CREATE TRIGGER set_public_user_slack_configurations_updated_at
BEFORE UPDATE ON public.user_slack_configurations
FOR EACH ROW
EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.user_slack_configurations IS 'Stores user preferences for Slack notifications related to scheduling results and other features.';
COMMENT ON COLUMN public.user_slack_configurations.slack_webhook_url IS 'Encrypted Slack Incoming Webhook URL or reference to a secret.';
COMMENT ON COLUMN public.user_slack_configurations.slack_bot_token_secret_arn IS 'ARN to AWS Secrets Manager secret for the Slack Bot Token.';
COMMENT ON COLUMN public.user_slack_configurations.slack_channel_id IS 'Slack Channel ID or User ID (for DMs) for bot notifications.';
COMMENT ON COLUMN public.user_slack_configurations.notification_type IS 'Type of notification this configuration applies to (e.g., SCHEDULING_RESULTS).';


-- 2. Create table for User Microsoft Teams Notification Configurations
CREATE TABLE IF NOT EXISTS public.user_msteams_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public."User"(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL DEFAULT 'SCHEDULING_RESULTS',
    msteams_webhook_url TEXT,
    graph_api_tenant_id TEXT,
    graph_api_client_id TEXT,
    graph_api_client_secret_arn TEXT,
    target_type TEXT, -- e.g., 'channel', 'chat', 'user_dm'
    target_id TEXT,   -- Channel ID, Chat ID, or User Principal Name/ID for Graph API messages
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT user_msteams_notification_type_unique UNIQUE (user_id, notification_type)
);

CREATE INDEX IF NOT EXISTS idx_user_msteams_configurations_user_id ON public.user_msteams_configurations(user_id);

CREATE TRIGGER set_public_user_msteams_configurations_updated_at
BEFORE UPDATE ON public.user_msteams_configurations
FOR EACH ROW
EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.user_msteams_configurations IS 'Stores user preferences for Microsoft Teams notifications.';
COMMENT ON COLUMN public.user_msteams_configurations.msteams_webhook_url IS 'Encrypted Microsoft Teams Incoming Webhook URL or reference to a secret.';
COMMENT ON COLUMN public.user_msteams_configurations.graph_api_client_secret_arn IS 'ARN to AWS Secrets Manager secret for the MS Graph API client secret.';
COMMENT ON COLUMN public.user_msteams_configurations.target_id IS 'Target Channel ID, Chat ID, or User ID for Graph API messages.';
COMMENT ON COLUMN public.user_msteams_configurations.notification_type IS 'Type of notification this configuration applies to (e.g., SCHEDULING_RESULTS).';


-- 3. Alter 'pending_scheduling_jobs' table
-- Add scheduler_response_details if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'pending_scheduling_jobs' AND column_name = 'scheduler_response_details') THEN
        ALTER TABLE public.pending_scheduling_jobs ADD COLUMN scheduler_response_details TEXT;
        COMMENT ON COLUMN public.pending_scheduling_jobs.scheduler_response_details IS 'Stores detailed response or error messages from the scheduler callback.';
    END IF;
END $$;

-- Add final_event_id if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'pending_scheduling_jobs' AND column_name = 'final_event_id') THEN
        ALTER TABLE public.pending_scheduling_jobs ADD COLUMN final_event_id TEXT;
        COMMENT ON COLUMN public.pending_scheduling_jobs.final_event_id IS 'If scheduling was successful, stores the ID of the created event in the public.Event table.';
    END IF;
END $$;

-- Add notification_sent_at (for SES) if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'pending_scheduling_jobs' AND column_name = 'notification_sent_at') THEN
        ALTER TABLE public.pending_scheduling_jobs ADD COLUMN notification_sent_at TIMESTAMP WITH TIME ZONE;
        COMMENT ON COLUMN public.pending_scheduling_jobs.notification_sent_at IS 'Timestamp when an email (SES) notification about this job''s status was sent.';
    END IF;
END $$;

-- Add slack_notification_sent_at if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'pending_scheduling_jobs' AND column_name = 'slack_notification_sent_at') THEN
        ALTER TABLE public.pending_scheduling_jobs ADD COLUMN slack_notification_sent_at TIMESTAMP WITH TIME ZONE;
        COMMENT ON COLUMN public.pending_scheduling_jobs.slack_notification_sent_at IS 'Timestamp when a Slack notification about this job''s status was sent.';
    END IF;
END $$;

-- Add msteams_notification_sent_at if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'pending_scheduling_jobs' AND column_name = 'msteams_notification_sent_at') THEN
        ALTER TABLE public.pending_scheduling_jobs ADD COLUMN msteams_notification_sent_at TIMESTAMP WITH TIME ZONE;
        COMMENT ON COLUMN public.pending_scheduling_jobs.msteams_notification_sent_at IS 'Timestamp when a Microsoft Teams notification about this job''s status was sent.';
    END IF;
END $$;


-- 4. Alter 'Event' table (public."Event")
-- Add scheduler_job_id if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'Event' AND column_name = 'scheduler_job_id') THEN
        ALTER TABLE public."Event" ADD COLUMN scheduler_job_id TEXT;
        COMMENT ON COLUMN public."Event".scheduler_job_id IS 'The singleton_id of the scheduling job that created this event.';
    END IF;
END $$;

-- Add notification_sent_at (for SES) if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'Event' AND column_name = 'notification_sent_at') THEN
        ALTER TABLE public."Event" ADD COLUMN notification_sent_at TIMESTAMP WITH TIME ZONE;
        COMMENT ON COLUMN public."Event".notification_sent_at IS 'Timestamp when an email (SES) notification about this event''s creation was sent.';
    END IF;
END $$;

-- Add slack_notification_sent_at if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'Event' AND column_name = 'slack_notification_sent_at') THEN
        ALTER TABLE public."Event" ADD COLUMN slack_notification_sent_at TIMESTAMP WITH TIME ZONE;
        COMMENT ON COLUMN public."Event".slack_notification_sent_at IS 'Timestamp when a Slack notification about this event''s creation was sent.';
    END IF;
END $$;

-- Add msteams_notification_sent_at if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'Event' AND column_name = 'msteams_notification_sent_at') THEN
        ALTER TABLE public."Event" ADD COLUMN msteams_notification_sent_at TIMESTAMP WITH TIME ZONE;
        COMMENT ON COLUMN public."Event".msteams_notification_sent_at IS 'Timestamp when a Microsoft Teams notification about this event''s creation was sent.';
    END IF;
END $$;

RAISE NOTICE 'Notification features schema changes applied successfully.';
