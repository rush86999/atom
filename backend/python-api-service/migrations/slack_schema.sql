-- Slack OAuth Integration Database Schema
-- Complete schema for Slack workspace authentication and data caching

-- Create encryption extension if not exists
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Slack OAuth tokens table
CREATE TABLE IF NOT EXISTS slack_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    bot_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT DEFAULT '',
    team_id VARCHAR(255),
    team_name VARCHAR(255),
    bot_user_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    encrypted_tokens TEXT NOT NULL,
    UNIQUE(user_id)
);

-- Slack users cache
CREATE TABLE IF NOT EXISTS slack_users_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    slack_user_id VARCHAR(255) NOT NULL,
    user_data JSONB,
    name TEXT,
    real_name TEXT,
    display_name TEXT,
    email TEXT,
    phone TEXT,
    title TEXT,
    status TEXT,
    status_emoji TEXT,
    is_bot BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_owner BOOLEAN DEFAULT FALSE,
    is_restricted BOOLEAN DEFAULT FALSE,
    is_ultra_restricted BOOLEAN DEFAULT FALSE,
    presence TEXT DEFAULT 'offline',
    tz TEXT,
    tz_label TEXT,
    updated_at TIMESTAMP WITH TIME ZONE,
    deleted BOOLEAN DEFAULT FALSE,
    image TEXT,
    has_image BOOLEAN DEFAULT FALSE,
    has_status BOOLEAN DEFAULT FALSE,
    has_phone BOOLEAN DEFAULT FALSE,
    has_title BOOLEAN DEFAULT FALSE,
    has_email BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, slack_user_id)
);

-- Slack channels cache
CREATE TABLE IF NOT EXISTS slack_channels_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    channel_data JSONB,
    name TEXT,
    name_normalized TEXT,
    topic TEXT,
    purpose TEXT,
    is_archived BOOLEAN DEFAULT FALSE,
    is_general BOOLEAN DEFAULT FALSE,
    is_private BOOLEAN DEFAULT TRUE,
    is_im BOOLEAN DEFAULT FALSE,
    is_mpim BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE,
    creator TEXT,
    last_read TEXT,
    unread_count INTEGER DEFAULT 0,
    unread_count_display INTEGER DEFAULT 0,
    num_members INTEGER DEFAULT 0,
    member_count INTEGER DEFAULT 0,
    is_member BOOLEAN DEFAULT TRUE,
    user_name TEXT,
    user_image TEXT,
    updated_at TIMESTAMP WITH TIME ZONE,
    has_topic BOOLEAN DEFAULT FALSE,
    has_purpose BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, channel_id)
);

-- Slack messages cache
CREATE TABLE IF NOT EXISTS slack_messages_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    message_id VARCHAR(255) NOT NULL,
    message_data JSONB,
    ts TEXT,
    message_type TEXT DEFAULT 'message',
    text TEXT,
    user TEXT,
    team TEXT,
    bot_id TEXT,
    is_bot BOOLEAN DEFAULT FALSE,
    thread_ts TEXT,
    is_thread BOOLEAN DEFAULT FALSE,
    reply_count INTEGER DEFAULT 0,
    reactions JSONB DEFAULT '[]'::jsonb,
    files JSONB DEFAULT '[]'::jsonb,
    has_files BOOLEAN DEFAULT FALSE,
    has_reactions BOOLEAN DEFAULT FALSE,
    has_thread BOOLEAN DEFAULT FALSE,
    edited BOOLEAN DEFAULT FALSE,
    pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date DATE,
    user_name TEXT,
    user_image TEXT,
    UNIQUE(user_id, channel_id, message_id)
);

-- Slack files cache
CREATE TABLE IF NOT EXISTS slack_files_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    file_id VARCHAR(255) NOT NULL,
    file_data JSONB,
    name TEXT,
    title TEXT,
    mimetype TEXT,
    filetype TEXT,
    pretty_type TEXT,
    user TEXT,
    timestamp INTEGER DEFAULT 0,
    size INTEGER DEFAULT 0,
    url_private TEXT,
    url_private_download TEXT,
    permalink TEXT,
    permalink_public TEXT,
    editable BOOLEAN DEFAULT FALSE,
    is_public BOOLEAN DEFAULT FALSE,
    is_external BOOLEAN DEFAULT FALSE,
    has_preview BOOLEAN DEFAULT FALSE,
    num_starred INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date DATE,
    size_mb NUMERIC(10,2),
    has_image BOOLEAN DEFAULT FALSE,
    has_video BOOLEAN DEFAULT FALSE,
    has_audio BOOLEAN DEFAULT FALSE,
    is_document BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, file_id)
);

-- Slack workspace metrics
CREATE TABLE IF NOT EXISTS slack_workspace_metrics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    team_id VARCHAR(255),
    metric_type VARCHAR(50) NOT NULL,
    metric_value NUMERIC,
    metric_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Slack activity logs
CREATE TABLE IF NOT EXISTS slack_activity_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    action_details JSONB,
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    channel_id VARCHAR(255),
    message_id VARCHAR(255),
    file_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Slack sync schedules
CREATE TABLE IF NOT EXISTS slack_sync_schedules (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    sync_type VARCHAR(50) NOT NULL,
    schedule_name TEXT NOT NULL,
    frequency VARCHAR(50),
    last_sync TIMESTAMP WITH TIME ZONE,
    next_sync TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_slack_oauth_user_id ON slack_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_oauth_team_id ON slack_oauth_tokens(team_id);
CREATE INDEX IF NOT EXISTS idx_slack_oauth_updated_at ON slack_oauth_tokens(updated_at);

CREATE INDEX IF NOT EXISTS idx_slack_users_user_id ON slack_users_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_users_slack_user_id ON slack_users_cache(slack_user_id);
CREATE INDEX IF NOT EXISTS idx_slack_users_name ON slack_users_cache(name);
CREATE INDEX IF NOT EXISTS idx_slack_users_email ON slack_users_cache(email);
CREATE INDEX IF NOT EXISTS idx_slack_users_is_admin ON slack_users_cache(is_admin);
CREATE INDEX IF NOT EXISTS idx_slack_users_is_bot ON slack_users_cache(is_bot);
CREATE INDEX IF NOT EXISTS idx_slack_users_presence ON slack_users_cache(presence);
CREATE INDEX IF NOT EXISTS idx_slack_users_updated_at ON slack_users_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_slack_channels_user_id ON slack_channels_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_channels_channel_id ON slack_channels_cache(channel_id);
CREATE INDEX IF NOT EXISTS idx_slack_channels_name ON slack_channels_cache(name);
CREATE INDEX IF NOT EXISTS idx_slack_channels_is_private ON slack_channels_cache(is_private);
CREATE INDEX IF NOT EXISTS idx_slack_channels_is_im ON slack_channels_cache(is_im);
CREATE INDEX IF NOT EXISTS idx_slack_channels_is_archived ON slack_channels_cache(is_archived);
CREATE INDEX IF NOT EXISTS idx_slack_channels_num_members ON slack_channels_cache(num_members);
CREATE INDEX IF NOT EXISTS idx_slack_channels_updated_at ON slack_channels_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_slack_messages_user_id ON slack_messages_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_channel_id ON slack_messages_cache(channel_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_message_id ON slack_messages_cache(message_id);
CREATE INDEX IF NOT EXISTS idx_slack_messages_ts ON slack_messages_cache(ts);
CREATE INDEX IF NOT EXISTS idx_slack_messages_user ON slack_messages_cache(user);
CREATE INDEX IF NOT EXISTS idx_slack_messages_is_bot ON slack_messages_cache(is_bot);
CREATE INDEX IF NOT EXISTS idx_slack_messages_thread_ts ON slack_messages_cache(thread_ts);
CREATE INDEX IF NOT EXISTS idx_slack_messages_has_reactions ON slack_messages_cache(has_reactions);
CREATE INDEX IF NOT EXISTS idx_slack_messages_has_files ON slack_messages_cache(has_files);
CREATE INDEX IF NOT EXISTS idx_slack_messages_created_at ON slack_messages_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_slack_messages_date ON slack_messages_cache(date);

CREATE INDEX IF NOT EXISTS idx_slack_files_user_id ON slack_files_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_files_file_id ON slack_files_cache(file_id);
CREATE INDEX IF NOT EXISTS idx_slack_files_name ON slack_files_cache(name);
CREATE INDEX IF NOT EXISTS idx_slack_files_mimetype ON slack_files_cache(mimetype);
CREATE INDEX IF NOT EXISTS idx_slack_files_filetype ON slack_files_cache(filetype);
CREATE INDEX IF NOT EXISTS idx_slack_files_user ON slack_files_cache(user);
CREATE INDEX IF NOT EXISTS idx_slack_files_timestamp ON slack_files_cache(timestamp);
CREATE INDEX IF NOT EXISTS idx_slack_files_size ON slack_files_cache(size);
CREATE INDEX IF NOT EXISTS idx_slack_files_has_image ON slack_files_cache(has_image);
CREATE INDEX IF NOT EXISTS idx_slack_files_has_video ON slack_files_cache(has_video);
CREATE INDEX IF NOT EXISTS idx_slack_files_has_audio ON slack_files_cache(has_audio);
CREATE INDEX IF NOT EXISTS idx_slack_files_created_at ON slack_files_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_slack_files_date ON slack_files_cache(date);

CREATE INDEX IF NOT EXISTS idx_slack_workspace_user_id ON slack_workspace_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_workspace_metric_type_date ON slack_workspace_metrics(metric_type, metric_date);

CREATE INDEX IF NOT EXISTS idx_slack_activity_user_id ON slack_activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_activity_action ON slack_activity_logs(action);
CREATE INDEX IF NOT EXISTS idx_slack_activity_channel_id ON slack_activity_logs(channel_id);
CREATE INDEX IF NOT EXISTS idx_slack_activity_created_at ON slack_activity_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_slack_sync_user_id ON slack_sync_schedules(user_id);
CREATE INDEX IF NOT EXISTS idx_slack_sync_type ON slack_sync_schedules(sync_type);
CREATE INDEX IF NOT EXISTS idx_slack_sync_next_sync ON slack_sync_schedules(next_sync);

-- Functions for token management
CREATE OR REPLACE FUNCTION refresh_slack_tokens(
    p_user_id VARCHAR(255),
    p_new_access_token TEXT,
    p_new_refresh_token TEXT,
    p_new_bot_token TEXT,
    p_expires_at TIMESTAMP WITH TIME ZONE
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE slack_oauth_tokens
    SET 
        access_token = p_new_access_token,
        refresh_token = COALESCE(p_new_refresh_token, refresh_token),
        bot_token = COALESCE(p_new_bot_token, bot_token),
        expires_at = p_expires_at,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION is_slack_token_expired(
    p_user_id VARCHAR(255)
) RETURNS BOOLEAN AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT expires_at INTO v_expires_at
    FROM slack_oauth_tokens
    WHERE user_id = p_user_id AND is_active = TRUE;
    
    RETURN v_expires_at IS NULL OR v_expires_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes';
END;
$$ LANGUAGE plpgsql;

-- Functions for analytics
CREATE OR REPLACE FUNCTION get_slack_stats(
    p_user_id VARCHAR(255)
) RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
    v_total_users INTEGER;
    v_active_users INTEGER;
    v_total_bots INTEGER;
    v_total_channels INTEGER;
    v_public_channels INTEGER;
    v_private_channels INTEGER;
    v_direct_messages INTEGER;
    v_total_messages INTEGER;
    v_messages_today INTEGER;
    v_messages_this_week INTEGER;
    v_total_files INTEGER;
    v_files_this_week INTEGER;
BEGIN
    -- Get user counts
    SELECT COUNT(*) INTO v_total_users
    FROM slack_users_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_active_users
    FROM slack_users_cache
    WHERE user_id = p_user_id AND presence = 'active';
    
    SELECT COUNT(*) INTO v_total_bots
    FROM slack_users_cache
    WHERE user_id = p_user_id AND is_bot = TRUE;
    
    -- Get channel counts
    SELECT COUNT(*) INTO v_total_channels
    FROM slack_channels_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_public_channels
    FROM slack_channels_cache
    WHERE user_id = p_user_id AND is_private = FALSE AND is_im = FALSE AND is_mpim = FALSE;
    
    SELECT COUNT(*) INTO v_private_channels
    FROM slack_channels_cache
    WHERE user_id = p_user_id AND is_private = TRUE AND is_im = FALSE AND is_mpim = FALSE;
    
    SELECT COUNT(*) INTO v_direct_messages
    FROM slack_channels_cache
    WHERE user_id = p_user_id AND is_im = TRUE;
    
    -- Get message counts
    SELECT COUNT(*) INTO v_total_messages
    FROM slack_messages_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_messages_today
    FROM slack_messages_cache
    WHERE user_id = p_user_id AND date = CURRENT_DATE;
    
    SELECT COUNT(*) INTO v_messages_this_week
    FROM slack_messages_cache
    WHERE user_id = p_user_id AND date >= CURRENT_DATE - INTERVAL '7 days';
    
    -- Get file counts
    SELECT COUNT(*) INTO v_total_files
    FROM slack_files_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_files_this_week
    FROM slack_files_cache
    WHERE user_id = p_user_id AND date >= CURRENT_DATE - INTERVAL '7 days';
    
    -- Build result
    v_result := jsonb_build_object(
        'users', jsonb_build_object(
            'total', v_total_users,
            'active', v_active_users,
            'bots', v_total_bots,
            'humans', v_total_users - v_total_bots
        ),
        'channels', jsonb_build_object(
            'total', v_total_channels,
            'public', v_public_channels,
            'private', v_private_channels,
            'direct_messages', v_direct_messages
        ),
        'messages', jsonb_build_object(
            'total', v_total_messages,
            'today', v_messages_today,
            'this_week', v_messages_this_week
        ),
        'files', jsonb_build_object(
            'total', v_total_files,
            'this_week', v_files_this_week
        ),
        'engagement', jsonb_build_object(
            'active_rate', v_total_users > 0 AND (v_active_users::NUMERIC / v_total_users::NUMERIC) OR 0,
            'bot_ratio', v_total_users > 0 AND (v_total_bots::NUMERIC / v_total_users::NUMERIC) or 0,
            'messages_per_day', v_messages_today,
            'activity_trend', CASE 
                WHEN v_messages_this_week > 0 AND v_total_messages > 0 
                THEN (v_messages_this_week::NUMERIC / 7) / (v_total_messages::NUMERIC / 365)
                ELSE 1 
            END
        )
    );
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- Functions for cache management
CREATE OR REPLACE FUNCTION cleanup_slack_cache(
    p_user_id VARCHAR(255),
    p_days_old INTEGER DEFAULT 30
) RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- Clean up old activity logs
    DELETE FROM slack_activity_logs
    WHERE user_id = p_user_id
    AND created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    -- Clean up old metrics
    DELETE FROM slack_workspace_metrics
    WHERE user_id = p_user_id
    AND metric_date < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    -- Clean up old messages (keep last 90 days)
    DELETE FROM slack_messages_cache
    WHERE user_id = p_user_id
    AND created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_slack_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
CREATE TRIGGER tr_slack_oauth_tokens_updated
    BEFORE UPDATE ON slack_oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_slack_updated_at();

CREATE TRIGGER tr_slack_users_updated
    BEFORE UPDATE ON slack_users_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_slack_updated_at();

CREATE TRIGGER tr_slack_channels_updated
    BEFORE UPDATE ON slack_channels_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_slack_updated_at();

CREATE TRIGGER tr_slack_files_updated
    BEFORE UPDATE ON slack_files_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_slack_updated_at();

CREATE TRIGGER tr_slack_sync_updated
    BEFORE UPDATE ON slack_sync_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_slack_updated_at();

-- Row Level Security (RLS)
ALTER TABLE slack_oauth_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_users_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_channels_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_messages_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_files_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_workspace_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_sync_schedules ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY slack_oauth_tokens_user_policy ON slack_oauth_tokens
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY slack_users_user_policy ON slack_users_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY slack_channels_user_policy ON slack_channels_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY slack_messages_user_policy ON slack_messages_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY slack_files_user_policy ON slack_files_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY slack_workspace_user_policy ON slack_workspace_metrics
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY slack_activity_user_policy ON slack_activity_logs
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY slack_sync_user_policy ON slack_sync_schedules
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

COMMIT;