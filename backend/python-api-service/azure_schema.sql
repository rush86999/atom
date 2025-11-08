-- Azure OAuth Token Schema
-- Secure storage for Azure OAuth tokens and user profile data

-- Create Azure OAuth tokens table
CREATE TABLE IF NOT EXISTS oauth_azure_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    scope TEXT,
    token_type VARCHAR(50),
    profile_data JSONB,
    tenant_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_oauth_azure_user_id ON oauth_azure_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_azure_expires_at ON oauth_azure_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_azure_updated_at ON oauth_azure_tokens(updated_at);
CREATE INDEX IF NOT EXISTS idx_oauth_azure_tenant_id ON oauth_azure_tokens(tenant_id);

-- Create trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_azure_oauth_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_azure_oauth_updated_at
    BEFORE UPDATE ON oauth_azure_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_azure_oauth_updated_at();

-- Create Azure resources cache tables for better performance
CREATE TABLE IF NOT EXISTS azure_resources_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(500) NOT NULL,
    resource_data JSONB,
    region VARCHAR(100),
    resource_group VARCHAR(255),
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_azure_resources_user_id ON azure_resources_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_azure_resources_type ON azure_resources_cache(resource_type);
CREATE INDEX IF NOT EXISTS idx_azure_resources_id ON azure_resources_cache(resource_id);
CREATE INDEX IF NOT EXISTS idx_azure_resources_status ON azure_resources_cache(status);

-- Create trigger for cache tables
CREATE OR REPLACE FUNCTION update_azure_resources_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_azure_resources_cache_updated_at
    BEFORE UPDATE ON azure_resources_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_azure_resources_cache_updated_at();

-- Create Azure cost analysis table
CREATE TABLE IF NOT EXISTS azure_cost_analysis (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    resource_group VARCHAR(255),
    service_name VARCHAR(255),
    cost_amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    cost_date DATE NOT NULL,
    billing_period VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_azure_cost_user_id ON azure_cost_analysis(user_id);
CREATE INDEX IF NOT EXISTS idx_azure_cost_date ON azure_cost_analysis(cost_date);
CREATE INDEX IF NOT EXISTS idx_azure_cost_service ON azure_cost_analysis(service_name);

-- Create Azure activity logs table
CREATE TABLE IF NOT EXISTS azure_activity_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(500),
    action_details JSONB,
    status VARCHAR(50),
    error_message TEXT,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_azure_activity_user_id ON azure_activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_azure_activity_action ON azure_activity_logs(action);
CREATE INDEX IF NOT EXISTS idx_azure_activity_status ON azure_activity_logs(status);
CREATE INDEX IF NOT EXISTS idx_azure_activity_created_at ON azure_activity_logs(created_at);

-- Create Azure webhook events table for real-time updates
CREATE TABLE IF NOT EXISTS azure_webhook_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(500),
    subscription_id VARCHAR(255),
    user_id VARCHAR(255),
    event_data JSONB,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_azure_webhooks_event_id ON azure_webhook_events(event_id);
CREATE INDEX IF NOT EXISTS idx_azure_webhooks_subscription_id ON azure_webhook_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_azure_webhooks_user_id ON azure_webhook_events(user_id);
CREATE INDEX IF NOT EXISTS idx_azure_webhooks_processed ON azure_webhook_events(processed);

-- Function to clean up old cache entries
CREATE OR REPLACE FUNCTION cleanup_azure_cache_entries()
RETURNS void AS $$
BEGIN
    -- Clean up cache entries older than 30 days
    DELETE FROM azure_resources_cache WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Clean up processed webhook events older than 7 days
    DELETE FROM azure_webhook_events 
    WHERE processed = TRUE AND processed_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
    
    -- Clean up activity logs older than 90 days
    DELETE FROM azure_activity_logs WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto cleanup (optional - can be called manually)
-- CREATE TRIGGER trigger_cleanup_azure_cache
--     AFTER INSERT OR UPDATE ON azure_resources_cache
--     EXECUTE FUNCTION cleanup_azure_cache_entries();

-- Row Level Security for multi-tenant applications
ALTER TABLE oauth_azure_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE azure_resources_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE azure_cost_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE azure_activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE azure_webhook_events ENABLE ROW LEVEL SECURITY;

-- RLS Policies (example - adjust based on your auth system)
CREATE POLICY azure_tokens_user_policy ON oauth_azure_tokens
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY azure_resources_user_policy ON azure_resources_cache
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY azure_cost_user_policy ON azure_cost_analysis
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY azure_activity_user_policy ON azure_activity_logs
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY azure_webhooks_user_policy ON azure_webhook_events
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);