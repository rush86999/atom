-- Xero OAuth Token Schema
-- Secure storage for Xero OAuth tokens and tenant information

-- Create Xero OAuth tokens table
CREATE TABLE IF NOT EXISTS oauth_xero_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    scope TEXT,
    token_type VARCHAR(50),
    tenant_id VARCHAR(255),
    tenant_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_oauth_xero_user_id ON oauth_xero_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_xero_expires_at ON oauth_xero_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_xero_updated_at ON oauth_xero_tokens(updated_at);
CREATE INDEX IF NOT EXISTS idx_oauth_xero_tenant_id ON oauth_xero_tokens(tenant_id);

-- Create trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_xero_oauth_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_xero_oauth_updated_at
    BEFORE UPDATE ON oauth_xero_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_xero_oauth_updated_at();

-- Create Xero API cache tables for better performance
CREATE TABLE IF NOT EXISTS xero_contacts_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    contact_id VARCHAR(255) NOT NULL,
    contact_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, contact_id)
);

CREATE TABLE IF NOT EXISTS xero_invoices_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    invoice_id VARCHAR(255) NOT NULL,
    invoice_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, invoice_id)
);

CREATE TABLE IF NOT EXISTS xero_accounts_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    account_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, account_id)
);

-- Create indexes for cache tables
CREATE INDEX IF NOT EXISTS idx_xero_contacts_user_id ON xero_contacts_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_xero_contacts_contact_id ON xero_contacts_cache(contact_id);
CREATE INDEX IF NOT EXISTS idx_xero_invoices_user_id ON xero_invoices_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_xero_invoices_invoice_id ON xero_invoices_cache(invoice_id);
CREATE INDEX IF NOT EXISTS idx_xero_accounts_user_id ON xero_accounts_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_xero_accounts_account_id ON xero_accounts_cache(account_id);

-- Create triggers for cache tables
CREATE OR REPLACE FUNCTION update_xero_contacts_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_xero_contacts_cache_updated_at
    BEFORE UPDATE ON xero_contacts_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_xero_contacts_cache_updated_at();

CREATE OR REPLACE FUNCTION update_xero_invoices_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_xero_invoices_cache_updated_at
    BEFORE UPDATE ON xero_invoices_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_xero_invoices_cache_updated_at();

CREATE OR REPLACE FUNCTION update_xero_accounts_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_xero_accounts_cache_updated_at
    BEFORE UPDATE ON xero_accounts_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_xero_accounts_cache_updated_at();

-- Create Xero webhook events table for real-time updates
CREATE TABLE IF NOT EXISTS xero_webhook_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    resource_url VARCHAR(500),
    tenant_id VARCHAR(255),
    user_id VARCHAR(255),
    event_data JSONB,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_xero_webhooks_event_id ON xero_webhook_events(event_id);
CREATE INDEX IF NOT EXISTS idx_xero_webhooks_tenant_id ON xero_webhook_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_xero_webhooks_user_id ON xero_webhook_events(user_id);
CREATE INDEX IF NOT EXISTS idx_xero_webhooks_processed ON xero_webhook_events(processed);

-- Function to clean up old cache entries
CREATE OR REPLACE FUNCTION cleanup_xero_cache_entries()
RETURNS void AS $$
BEGIN
    -- Clean up cache entries older than 30 days
    DELETE FROM xero_contacts_cache WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    DELETE FROM xero_invoices_cache WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    DELETE FROM xero_accounts_cache WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Clean up processed webhook events older than 7 days
    DELETE FROM xero_webhook_events 
    WHERE processed = TRUE AND processed_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto cleanup (optional - can be called manually)
-- CREATE TRIGGER trigger_cleanup_xero_cache
--     AFTER INSERT OR UPDATE ON xero_contacts_cache
--     EXECUTE FUNCTION cleanup_xero_cache_entries();

-- Row Level Security for multi-tenant applications
ALTER TABLE oauth_xero_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_contacts_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_invoices_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_accounts_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE xero_webhook_events ENABLE ROW LEVEL SECURITY;

-- RLS Policies (example - adjust based on your auth system)
CREATE POLICY xero_tokens_user_policy ON oauth_xero_tokens
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY xero_contacts_user_policy ON xero_contacts_cache
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY xero_invoices_user_policy ON xero_invoices_cache
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY xero_accounts_user_policy ON xero_accounts_cache
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);

CREATE POLICY xero_webhooks_user_policy ON xero_webhook_events
    FOR ALL USING (user_id = current_setting('app.current_user_id', '')::VARCHAR);