-- QuickBooks Integration Database Schema
-- PostgreSQL schema for QuickBooks OAuth tokens and user/company data

-- OAuth tokens table for storing authentication credentials
CREATE TABLE IF NOT EXISTS quickbooks_oauth_tokens (
    user_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type TEXT DEFAULT 'Bearer',
    expires_in INTEGER DEFAULT 3600,
    x_refresh_token_expires_in INTEGER DEFAULT 864000,
    realm_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User/company data table for storing QuickBooks company information
CREATE TABLE IF NOT EXISTS quickbooks_user_data (
    user_id TEXT PRIMARY KEY,
    realm_id TEXT NOT NULL,
    company_name TEXT,
    legal_name TEXT,
    company_type TEXT,
    domain TEXT,
    email TEXT,
    phone TEXT,
    website TEXT,
    address_line1 TEXT,
    address_line2 TEXT,
    address_city TEXT,
    address_state TEXT,
    address_postal_code TEXT,
    address_country TEXT,
    environment TEXT DEFAULT 'sandbox',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_quickbooks_oauth_tokens_updated_at ON quickbooks_oauth_tokens(updated_at);
CREATE INDEX IF NOT EXISTS idx_quickbooks_oauth_tokens_user_id ON quickbooks_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_quickbooks_oauth_tokens_realm_id ON quickbooks_oauth_tokens(realm_id);
CREATE INDEX IF NOT EXISTS idx_quickbooks_user_data_realm_id ON quickbooks_user_data(realm_id);
CREATE INDEX IF NOT EXISTS idx_quickbooks_user_data_company_name ON quickbooks_user_data(company_name);
CREATE INDEX IF NOT EXISTS idx_quickbooks_user_data_environment ON quickbooks_user_data(environment);
CREATE INDEX IF NOT EXISTS idx_quickbooks_user_data_updated_at ON quickbooks_user_data(updated_at);

-- Triggers to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_quickbooks_oauth_tokens_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION update_quickbooks_user_data_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS trigger_update_quickbooks_oauth_tokens_updated_at ON quickbooks_oauth_tokens;
CREATE TRIGGER trigger_update_quickbooks_oauth_tokens_updated_at
    BEFORE UPDATE ON quickbooks_oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_quickbooks_oauth_tokens_updated_at();

DROP TRIGGER IF EXISTS trigger_update_quickbooks_user_data_updated_at ON quickbooks_user_data;
CREATE TRIGGER trigger_update_quickbooks_user_data_updated_at
    BEFORE UPDATE ON quickbooks_user_data
    FOR EACH ROW
    EXECUTE FUNCTION update_quickbooks_user_data_updated_at();

-- Row Level Security (RLS) for multi-tenant applications
-- Uncomment if using RLS in your PostgreSQL setup

-- ALTER TABLE quickbooks_oauth_tokens ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE quickbooks_user_data ENABLE ROW LEVEL SECURITY;

-- Policy examples (adjust based on your authentication system)
-- CREATE POLICY quickbooks_oauth_tokens_user_policy ON quickbooks_oauth_tokens
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- CREATE POLICY quickbooks_user_data_user_policy ON quickbooks_user_data
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- Comments for documentation
COMMENT ON TABLE quickbooks_oauth_tokens IS 'Stores OAuth tokens for QuickBooks API authentication';
COMMENT ON TABLE quickbooks_user_data IS 'Stores QuickBooks company/user data and configuration';

COMMENT ON COLUMN quickbooks_oauth_tokens.user_id IS 'ATOM user identifier';
COMMENT ON COLUMN quickbooks_oauth_tokens.access_token IS 'QuickBooks OAuth access token';
COMMENT ON COLUMN quickbooks_oauth_tokens.refresh_token IS 'QuickBooks OAuth refresh token (optional)';
COMMENT ON COLUMN quickbooks_oauth_tokens.token_type IS 'Token type, usually Bearer';
COMMENT ON COLUMN quickbooks_oauth_tokens.expires_in IS 'Token expiration time in seconds';
COMMENT ON COLUMN quickbooks_oauth_tokens.x_refresh_token_expires_in IS 'Refresh token expiration time in seconds';
COMMENT ON COLUMN quickbooks_oauth_tokens.realm_id IS 'QuickBooks company realm ID';
COMMENT ON COLUMN quickbooks_oauth_tokens.created_at IS 'Token creation timestamp';
COMMENT ON COLUMN quickbooks_oauth_tokens.updated_at IS 'Token last update timestamp';

COMMENT ON COLUMN quickbooks_user_data.user_id IS 'ATOM user identifier';
COMMENT ON COLUMN quickbooks_user_data.realm_id IS 'QuickBooks company realm ID';
COMMENT ON COLUMN quickbooks_user_data.company_name IS 'QuickBooks company display name';
COMMENT ON COLUMN quickbooks_user_data.legal_name IS 'QuickBooks legal company name';
COMMENT ON COLUMN quickbooks_user_data.company_type IS 'QuickBooks company type';
COMMENT ON COLUMN quickbooks_user_data.domain IS 'QuickBooks company domain';
COMMENT ON COLUMN quickbooks_user_data.email IS 'Company email address';
COMMENT ON COLUMN quickbooks_user_data.phone IS 'Company phone number';
COMMENT ON COLUMN quickbooks_user_data.website IS 'Company website URL';
COMMENT ON COLUMN quickbooks_user_data.address_line1 IS 'Company address line 1';
COMMENT ON COLUMN quickbooks_user_data.address_line2 IS 'Company address line 2';
COMMENT ON COLUMN quickbooks_user_data.address_city IS 'Company address city';
COMMENT ON COLUMN quickbooks_user_data.address_state IS 'Company address state/province';
COMMENT ON COLUMN quickbooks_user_data.address_postal_code IS 'Company address postal code';
COMMENT ON COLUMN quickbooks_user_data.address_country IS 'Company address country';
COMMENT ON COLUMN quickbooks_user_data.environment IS 'QuickBooks environment (sandbox/production)';
COMMENT ON COLUMN quickbooks_user_data.metadata IS 'Additional company metadata in JSON format';
COMMENT ON COLUMN quickbooks_user_data.created_at IS 'Company data creation timestamp';
COMMENT ON COLUMN quickbooks_user_data.updated_at IS 'Company data last update timestamp';

-- QuickBooks financial data tracking tables (optional for advanced features)
-- Uncomment if you want to track financial data locally

-- Invoice tracking table
-- CREATE TABLE IF NOT EXISTS quickbooks_invoice_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES quickbooks_user_data(user_id),
--     realm_id TEXT NOT NULL,
--     invoice_id TEXT NOT NULL,
--     invoice_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(realm_id, invoice_id)
-- );

-- Customer tracking table
-- CREATE TABLE IF NOT EXISTS quickbooks_customer_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES quickbooks_user_data(user_id),
--     realm_id TEXT NOT NULL,
--     customer_id TEXT NOT NULL,
--     customer_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(realm_id, customer_id)
-- );

-- Expense tracking table
-- CREATE TABLE IF NOT EXISTS quickbooks_expense_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES quickbooks_user_data(user_id),
--     realm_id TEXT NOT NULL,
--     expense_id TEXT NOT NULL,
--     expense_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(realm_id, expense_id)
-- );

-- Report cache table for performance
-- CREATE TABLE IF NOT EXISTS quickbooks_report_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES quickbooks_user_data(user_id),
--     realm_id TEXT NOT NULL,
--     report_type TEXT NOT NULL,
--     report_parameters JSONB,
--     report_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     expires_at TIMESTAMP,
--     UNIQUE(realm_id, report_type, md5(report_parameters::text))
-- );

-- Indexes for cache tables
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_invoice_cache_realm_invoice ON quickbooks_invoice_cache(realm_id, invoice_id);
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_invoice_cache_sync_time ON quickbooks_invoice_cache(sync_time);
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_customer_cache_realm_customer ON quickbooks_customer_cache(realm_id, customer_id);
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_customer_cache_sync_time ON quickbooks_customer_cache(sync_time);
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_expense_cache_realm_expense ON quickbooks_expense_cache(realm_id, expense_id);
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_expense_cache_sync_time ON quickbooks_expense_cache(sync_time);
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_report_cache_type ON quickbooks_report_cache(report_type);
-- CREATE INDEX IF NOT EXISTS idx_quickbooks_report_cache_expires ON quickbooks_report_cache(expires_at);

-- Partitioning for large datasets (uncomment if needed)
-- CREATE TABLE quickbooks_invoice_cache_partitioned (
--     LIKE quickbooks_invoice_cache INCLUDING ALL
-- ) PARTITION BY RANGE (sync_time);

-- CREATE TABLE quickbooks_invoice_cache_2024 PARTITION OF quickbooks_invoice_cache_partitioned
--     FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- Functions for data cleanup
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM quickbooks_oauth_tokens 
    WHERE updated_at < NOW() - INTERVAL '90 days'
    AND user_id NOT IN (
        SELECT DISTINCT user_id FROM quickbooks_user_data 
        WHERE updated_at > NOW() - INTERVAL '90 days'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanup_old_cache_data()
RETURNS void AS $$
BEGIN
    -- Clean up expired report cache data
    DELETE FROM quickbooks_report_cache 
    WHERE expires_at < NOW();
    
    -- Clean up old sync data (if cache tables exist)
    -- DELETE FROM quickbooks_invoice_cache WHERE sync_time < NOW() - INTERVAL '30 days';
    -- DELETE FROM quickbooks_customer_cache WHERE sync_time < NOW() - INTERVAL '30 days';
    -- DELETE FROM quickbooks_expense_cache WHERE sync_time < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup jobs (requires pg_cron extension)
-- Uncomment if you have pg_cron installed
-- SELECT cron.schedule('cleanup-quickbooks-data', '0 2 * * *', 'SELECT cleanup_expired_tokens(); SELECT cleanup_old_cache_data();');