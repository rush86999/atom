-- HubSpot OAuth Integration Database Schema
-- Complete schema for HubSpot CRM authentication and data caching

-- Create encryption extension if not exists
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- HubSpot OAuth tokens table
CREATE TABLE IF NOT EXISTS hubspot_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    hub_id VARCHAR(255),
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    encrypted_tokens TEXT NOT NULL,
    UNIQUE(user_id)
);

-- HubSpot contacts cache
CREATE TABLE IF NOT EXISTS hubspot_contacts_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    contact_id VARCHAR(255) NOT NULL,
    contact_data JSONB,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    company TEXT,
    job_title TEXT,
    lifecycle_stage TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    is_customer BOOLEAN DEFAULT FALSE,
    has_email BOOLEAN DEFAULT FALSE,
    has_phone BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, contact_id)
);

-- HubSpot companies cache
CREATE TABLE IF NOT EXISTS hubspot_companies_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    company_data JSONB,
    name TEXT,
    domain TEXT,
    industry TEXT,
    description TEXT,
    size TEXT,
    revenue TEXT,
    phone TEXT,
    website TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    has_website BOOLEAN DEFAULT FALSE,
    has_phone BOOLEAN DEFAULT FALSE,
    employee_count INTEGER DEFAULT 0,
    UNIQUE(user_id, company_id)
);

-- HubSpot deals cache
CREATE TABLE IF NOT EXISTS hubspot_deals_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    deal_id VARCHAR(255) NOT NULL,
    deal_data JSONB,
    deal_name TEXT,
    pipeline TEXT,
    deal_stage TEXT,
    amount NUMERIC DEFAULT 0,
    forecast_amount NUMERIC DEFAULT 0,
    probability DECIMAL(3,2) DEFAULT 0,
    deal_type TEXT,
    close_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    is_closed BOOLEAN DEFAULT FALSE,
    is_won BOOLEAN DEFAULT FALSE,
    has_amount BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, deal_id)
);

-- HubSpot tickets cache
CREATE TABLE IF NOT EXISTS hubspot_tickets_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    ticket_id VARCHAR(255) NOT NULL,
    ticket_data JSONB,
    subject TEXT,
    content TEXT,
    pipeline TEXT,
    pipeline_stage TEXT,
    category TEXT,
    priority TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    closed_date TIMESTAMP WITH TIME ZONE,
    is_closed BOOLEAN DEFAULT FALSE,
    priority_level INTEGER DEFAULT 2,
    UNIQUE(user_id, ticket_id)
);

-- HubSpot pipelines cache
CREATE TABLE IF NOT EXISTS hubspot_pipelines_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    pipeline_id VARCHAR(255) NOT NULL,
    pipeline_data JSONB,
    label TEXT,
    object_type TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    stage_count INTEGER DEFAULT 0,
    won_stages INTEGER DEFAULT 0,
    lost_stages INTEGER DEFAULT 0,
    UNIQUE(user_id, pipeline_id, object_type)
);

-- HubSpot engagement metrics
CREATE TABLE IF NOT EXISTS hubspot_engagement_metrics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    object_type VARCHAR(50) NOT NULL, -- 'contacts', 'companies', 'deals', 'tickets'
    object_id VARCHAR(255),
    metric_type VARCHAR(50) NOT NULL, -- 'created', 'updated', 'deleted', 'engagement'
    metric_value NUMERIC,
    metric_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- HubSpot activity logs
CREATE TABLE IF NOT EXISTS hubspot_activity_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    action_details JSONB,
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    contact_id VARCHAR(255),
    company_id VARCHAR(255),
    deal_id VARCHAR(255),
    ticket_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- HubSpot sync schedules
CREATE TABLE IF NOT EXISTS hubspot_sync_schedules (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    sync_type VARCHAR(50) NOT NULL, -- 'contacts', 'companies', 'deals', 'tickets'
    schedule_name TEXT NOT NULL,
    frequency VARCHAR(50), -- 'hourly', 'daily', 'weekly'
    last_sync TIMESTAMP WITH TIME ZONE,
    next_sync TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_user_id ON hubspot_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_email ON hubspot_oauth_tokens(email);
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_hub_id ON hubspot_oauth_tokens(hub_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_updated_at ON hubspot_oauth_tokens(updated_at);

CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_user_id ON hubspot_contacts_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_contact_id ON hubspot_contacts_cache(contact_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_email ON hubspot_contacts_cache(email);
CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_company ON hubspot_contacts_cache(company);
CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_lifecycle_stage ON hubspot_contacts_cache(lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_hubspot_contacts_updated_at ON hubspot_contacts_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_hubspot_companies_user_id ON hubspot_companies_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_companies_company_id ON hubspot_companies_cache(company_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_companies_name ON hubspot_companies_cache(name);
CREATE INDEX IF NOT EXISTS idx_hubspot_companies_domain ON hubspot_companies_cache(domain);
CREATE INDEX IF NOT EXISTS idx_hubspot_companies_industry ON hubspot_companies_cache(industry);
CREATE INDEX IF NOT EXISTS idx_hubspot_companies_updated_at ON hubspot_companies_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_hubspot_deals_user_id ON hubspot_deals_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_deal_id ON hubspot_deals_cache(deal_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_pipeline ON hubspot_deals_cache(pipeline);
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_stage ON hubspot_deals_cache(deal_stage);
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_amount ON hubspot_deals_cache(amount);
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_close_date ON hubspot_deals_cache(close_date);
CREATE INDEX IF NOT EXISTS idx_hubspot_deals_updated_at ON hubspot_deals_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_user_id ON hubspot_tickets_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_ticket_id ON hubspot_tickets_cache(ticket_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_pipeline ON hubspot_tickets_cache(pipeline);
CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_stage ON hubspot_tickets_cache(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_priority ON hubspot_tickets_cache(priority);
CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_closed_date ON hubspot_tickets_cache(closed_date);
CREATE INDEX IF NOT EXISTS idx_hubspot_tickets_updated_at ON hubspot_tickets_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_hubspot_pipelines_user_id ON hubspot_pipelines_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_pipelines_pipeline_id ON hubspot_pipelines_cache(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_pipelines_object_type ON hubspot_pipelines_cache(object_type);
CREATE INDEX IF NOT EXISTS idx_hubspot_pipelines_updated_at ON hubspot_pipelines_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_hubspot_engagement_user_id ON hubspot_engagement_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_engagement_object_id ON hubspot_engagement_metrics(object_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_engagement_type_date ON hubspot_engagement_metrics(metric_type, metric_date);

CREATE INDEX IF NOT EXISTS idx_hubspot_activity_user_id ON hubspot_activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_activity_action ON hubspot_activity_logs(action);
CREATE INDEX IF NOT EXISTS idx_hubspot_activity_contact_id ON hubspot_activity_logs(contact_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_activity_created_at ON hubspot_activity_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_hubspot_sync_user_id ON hubspot_sync_schedules(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_sync_type ON hubspot_sync_schedules(sync_type);
CREATE INDEX IF NOT EXISTS idx_hubspot_sync_next_sync ON hubspot_sync_schedules(next_sync);

-- Functions for token management
CREATE OR REPLACE FUNCTION refresh_hubspot_tokens(
    p_user_id VARCHAR(255),
    p_new_access_token TEXT,
    p_new_refresh_token TEXT,
    p_expires_at TIMESTAMP WITH TIME ZONE
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE hubspot_oauth_tokens
    SET 
        access_token = p_new_access_token,
        refresh_token = COALESCE(p_new_refresh_token, refresh_token),
        expires_at = p_expires_at,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION is_hubspot_token_expired(
    p_user_id VARCHAR(255)
) RETURNS BOOLEAN AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT expires_at INTO v_expires_at
    FROM hubspot_oauth_tokens
    WHERE user_id = p_user_id AND is_active = TRUE;
    
    RETURN v_expires_at IS NULL OR v_expires_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes';
END;
$$ LANGUAGE plpgsql;

-- Functions for analytics
CREATE OR REPLACE FUNCTION get_hubspot_stats(
    p_user_id VARCHAR(255)
) RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
    v_contacts_count INTEGER;
    v_companies_count INTEGER;
    v_deals_count INTEGER;
    v_won_deals_count INTEGER;
    v_total_deal_value NUMERIC;
    v_tickets_count INTEGER;
    v_open_tickets_count INTEGER;
BEGIN
    -- Get counts
    SELECT COUNT(*) INTO v_contacts_count
    FROM hubspot_contacts_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_companies_count
    FROM hubspot_companies_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_deals_count
    FROM hubspot_deals_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_won_deals_count
    FROM hubspot_deals_cache
    WHERE user_id = p_user_id AND is_won = TRUE;
    
    SELECT COALESCE(SUM(amount), 0) INTO v_total_deal_value
    FROM hubspot_deals_cache
    WHERE user_id = p_user_id AND is_won = TRUE;
    
    SELECT COUNT(*) INTO v_tickets_count
    FROM hubspot_tickets_cache
    WHERE user_id = p_user_id;
    
    SELECT COUNT(*) INTO v_open_tickets_count
    FROM hubspot_tickets_cache
    WHERE user_id = p_user_id AND is_closed = FALSE;
    
    -- Build result
    v_result := jsonb_build_object(
        'contacts', jsonb_build_object(
            'total', v_contacts_count,
            'customers', (SELECT COUNT(*) FROM hubspot_contacts_cache WHERE user_id = p_user_id AND is_customer = TRUE)
        ),
        'companies', jsonb_build_object(
            'total', v_companies_count,
            'industries', (SELECT COUNT(DISTINCT industry) FROM hubspot_companies_cache WHERE user_id = p_user_id AND industry IS NOT NULL)
        ),
        'deals', jsonb_build_object(
            'total', v_deals_count,
            'won', v_won_deals_count,
            'totalValue', v_total_deal_value,
            'conversionRate', CASE WHEN v_deals_count > 0 THEN (v_won_deals_count::NUMERIC / v_deals_count::NUMERIC) ELSE 0 END
        ),
        'tickets', jsonb_build_object(
            'total', v_tickets_count,
            'open', v_open_tickets_count,
            'closed', v_tickets_count - v_open_tickets_count
        )
    );
    
    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- Functions for cache management
CREATE OR REPLACE FUNCTION cleanup_hubspot_cache(
    p_user_id VARCHAR(255),
    p_days_old INTEGER DEFAULT 30
) RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- Clean up old activity logs
    DELETE FROM hubspot_activity_logs
    WHERE user_id = p_user_id
    AND created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    -- Clean up old engagement metrics
    DELETE FROM hubspot_engagement_metrics
    WHERE user_id = p_user_id
    AND metric_date < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_hubspot_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
CREATE TRIGGER tr_hubspot_oauth_tokens_updated
    BEFORE UPDATE ON hubspot_oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_updated_at();

CREATE TRIGGER tr_hubspot_contacts_updated
    BEFORE UPDATE ON hubspot_contacts_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_updated_at();

CREATE TRIGGER tr_hubspot_companies_updated
    BEFORE UPDATE ON hubspot_companies_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_updated_at();

CREATE TRIGGER tr_hubspot_deals_updated
    BEFORE UPDATE ON hubspot_deals_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_updated_at();

CREATE TRIGGER tr_hubspot_tickets_updated
    BEFORE UPDATE ON hubspot_tickets_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_updated_at();

CREATE TRIGGER tr_hubspot_pipelines_updated
    BEFORE UPDATE ON hubspot_pipelines_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_updated_at();

CREATE TRIGGER tr_hubspot_sync_updated
    BEFORE UPDATE ON hubspot_sync_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_updated_at();

-- Row Level Security (RLS)
ALTER TABLE hubspot_oauth_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_contacts_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_companies_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_deals_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_tickets_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_pipelines_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_engagement_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE hubspot_sync_schedules ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY hubspot_oauth_tokens_user_policy ON hubspot_oauth_tokens
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_contacts_user_policy ON hubspot_contacts_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_companies_user_policy ON hubspot_companies_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_deals_user_policy ON hubspot_deals_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_tickets_user_policy ON hubspot_tickets_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_pipelines_user_policy ON hubspot_pipelines_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_engagement_user_policy ON hubspot_engagement_metrics
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_activity_user_policy ON hubspot_activity_logs
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY hubspot_sync_user_policy ON hubspot_sync_schedules
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

COMMIT;