-- ============================================
-- Enhanced Salesforce Integration - Phase 1 Schema
-- Real-time webhooks, bulk API, custom objects, enhanced analytics
-- ============================================

-- Salesforce Webhook Subscriptions Table
CREATE TABLE IF NOT EXISTS salesforce_webhook_subscriptions (
    subscription_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    events JSONB NOT NULL,
    callback_url TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_webhook_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Salesforce Webhook Events Table
CREATE TABLE IF NOT EXISTS salesforce_webhook_events (
    event_id VARCHAR(255) PRIMARY KEY,
    subscription_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    object_id VARCHAR(255) NOT NULL,
    change_type VARCHAR(50) NOT NULL,
    changed_fields JSONB,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT fk_webhook_event_subscription FOREIGN KEY (subscription_id) 
        REFERENCES salesforce_webhook_subscriptions(subscription_id) ON DELETE SET NULL
);

-- Salesforce Bulk Jobs Table
CREATE TABLE IF NOT EXISTS salesforce_bulk_jobs (
    job_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    operation VARCHAR(50) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Queued',
    total_records INTEGER NOT NULL,
    successful_records INTEGER DEFAULT 0,
    failed_records INTEGER DEFAULT 0,
    error_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT fk_bulk_job_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Salesforce Bulk Job Batches Table
CREATE TABLE IF NOT EXISTS salesforce_bulk_job_batches (
    batch_id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) NOT NULL,
    batch_number INTEGER NOT NULL,
    successful_records INTEGER DEFAULT 0,
    failed_records INTEGER DEFAULT 0,
    error_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_batch_job FOREIGN KEY (job_id) 
        REFERENCES salesforce_bulk_jobs(job_id) ON DELETE CASCADE,
    CONSTRAINT unique_job_batch UNIQUE(job_id, batch_number)
);

-- Salesforce Custom Objects Cache Table
CREATE TABLE IF NOT EXISTS salesforce_custom_objects_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    cache_data JSONB NOT NULL,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    CONSTRAINT fk_custom_objects_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_cache UNIQUE(user_id)
);

-- Salesforce Real-time Analytics Table
CREATE TABLE IF NOT EXISTS salesforce_realtime_analytics (
    id SERIAL PRIMARY KEY,
    metric_type VARCHAR(100) NOT NULL,
    object_type VARCHAR(100),
    metric_value NUMERIC NOT NULL DEFAULT 1,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_realtime_metric_type (metric_type),
    INDEX idx_realtime_object_type (object_type),
    INDEX idx_realtime_created_at (created_at)
);

-- Salesforce Webhook Activity Log Table
CREATE TABLE IF NOT EXISTS salesforce_webhook_activity_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    activity_type VARCHAR(100) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_webhook_activity_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_webhook_activity_user (user_id),
    INDEX idx_webhook_activity_type (activity_type),
    INDEX idx_webhook_activity_created (created_at)
);

-- Salesforce Enhanced Analytics Cache Table
CREATE TABLE IF NOT EXISTS salesforce_analytics_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    analytics_type VARCHAR(100) NOT NULL,
    date_range VARCHAR(20) NOT NULL,
    cache_data JSONB NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    CONSTRAINT fk_analytics_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_analytics UNIQUE(user_id, analytics_type, date_range)
);

-- Salesforce Predictive Insights Table
CREATE TABLE IF NOT EXISTS salesforce_predictive_insights (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    insight_type VARCHAR(100) NOT NULL,
    object_type VARCHAR(100),
    object_id VARCHAR(255),
    confidence_score NUMERIC(3,2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    prediction JSONB NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    
    CONSTRAINT fk_predictive_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_predictive_user_type (user_id, insight_type),
    INDEX idx_predictive_object (object_type, object_id),
    INDEX idx_predictive_valid_until (valid_until)
);

-- Salesforce Integration Metrics Table
CREATE TABLE IF NOT EXISTS salesforce_integration_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    user_id VARCHAR(255),
    api_calls INTEGER DEFAULT 0,
    webhooks_received INTEGER DEFAULT 0,
    bulk_jobs_created INTEGER DEFAULT 0,
    records_processed INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    avg_response_time NUMERIC(10,2),
    data_transferred_kb NUMERIC(12,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_metrics_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT unique_date_user UNIQUE(metric_date, user_id),
    INDEX idx_metrics_date (metric_date),
    INDEX idx_metrics_user (user_id)
);

-- ============================================
-- Indexes for Performance Optimization
-- ============================================

-- Webhook Subscriptions Indexes
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_user ON salesforce_webhook_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_object ON salesforce_webhook_subscriptions(object_type);
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_active ON salesforce_webhook_subscriptions(active);

-- Webhook Events Indexes
CREATE INDEX IF NOT EXISTS idx_webhook_events_user ON salesforce_webhook_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_object ON salesforce_webhook_events(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_processed ON salesforce_webhook_events(processed);
CREATE INDEX IF NOT EXISTS idx_webhook_events_created ON salesforce_webhook_events(created_at);

-- Bulk Jobs Indexes
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_user ON salesforce_bulk_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_status ON salesforce_bulk_jobs(status);
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_created ON salesforce_bulk_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_object ON salesforce_bulk_jobs(object_type);

-- Custom Objects Cache Indexes
CREATE INDEX IF NOT EXISTS idx_custom_objects_cache_user ON salesforce_custom_objects_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_objects_cache_expires ON salesforce_custom_objects_cache(expires_at);

-- Analytics Cache Indexes
CREATE INDEX IF NOT EXISTS idx_analytics_cache_user ON salesforce_analytics_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_cache_type ON salesforce_analytics_cache(analytics_type);
CREATE INDEX IF NOT EXISTS idx_analytics_cache_expires ON salesforce_analytics_cache(expires_at);

-- Integration Metrics Indexes
CREATE INDEX IF NOT EXISTS idx_integration_metrics_date_user ON salesforce_integration_metrics(metric_date, user_id);

-- ============================================
-- Triggers for Automatic Timestamp Updates
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at columns
CREATE TRIGGER update_webhook_subscriptions_updated_at 
    BEFORE UPDATE ON salesforce_webhook_subscriptions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bulk_jobs_updated_at 
    BEFORE UPDATE ON salesforce_bulk_jobs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Views for Enhanced Analytics
-- ============================================

-- Webhook Performance View
CREATE OR REPLACE VIEW webhook_performance AS
SELECT 
    DATE(created_at) as event_date,
    object_type,
    change_type,
    COUNT(*) as event_count,
    COUNT(CASE WHEN processed = true THEN 1 END) as processed_count,
    AVG(EXTRACT(EPOCH FROM (processed_at - created_at))) as avg_processing_time_seconds
FROM salesforce_webhook_events
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), object_type, change_type
ORDER BY event_date DESC, object_type, change_type;

-- Bulk Job Performance View
CREATE OR REPLACE VIEW bulk_job_performance AS
SELECT 
    DATE(created_at) as job_date,
    operation,
    object_type,
    status,
    COUNT(*) as job_count,
    SUM(total_records) as total_records_processed,
    SUM(successful_records) as successful_records,
    SUM(failed_records) as failed_records,
    CASE 
        WHEN SUM(total_records) > 0 
        THEN (SUM(successful_records)::NUMERIC / SUM(total_records)) * 100 
        ELSE 0 
    END as success_rate_percentage,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/60) as avg_processing_time_minutes
FROM salesforce_bulk_jobs
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), operation, object_type, status
ORDER BY job_date DESC, operation, object_type;

-- Real-time Metrics Summary View
CREATE OR REPLACE VIEW realtime_metrics_summary AS
SELECT 
    DATE(created_at) as metric_date,
    metric_type,
    SUM(metric_value) as total_value,
    COUNT(*) as event_count
FROM salesforce_realtime_analytics
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at), metric_type
ORDER BY metric_date DESC, metric_type;

-- ============================================
-- Functions for Data Maintenance
-- ============================================

-- Function to clean up expired cache data
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    cleanup_count INTEGER := 0;
BEGIN
    -- Clean up expired custom objects cache
    DELETE FROM salesforce_custom_objects_cache WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    
    -- Clean up expired analytics cache
    DELETE FROM salesforce_analytics_cache WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS cleanup_count = cleanup_count + ROW_COUNT;
    
    -- Clean up old webhook events (older than 90 days)
    DELETE FROM salesforce_webhook_events WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    GET DIAGNOSTICS cleanup_count = cleanup_count + ROW_COUNT;
    
    -- Clean up old webhook activity logs (older than 1 year)
    DELETE FROM salesforce_webhook_activity_log WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 year';
    GET DIAGNOSTICS cleanup_count = cleanup_count + ROW_COUNT;
    
    -- Clean up expired predictive insights
    DELETE FROM salesforce_predictive_insights WHERE valid_until < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS cleanup_count = cleanup_count + ROW_COUNT;
    
    RETURN cleanup_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Initial Data Setup
-- ============================================

-- Insert default real-time analytics metrics
INSERT INTO salesforce_realtime_analytics (metric_type, metric_value, created_at) VALUES
('webhook_events_received', 0, CURRENT_TIMESTAMP),
('bulk_jobs_created', 0, CURRENT_TIMESTAMP),
('records_processed', 0, CURRENT_TIMESTAMP),
('api_calls_made', 0, CURRENT_TIMESTAMP),
('cache_hits', 0, CURRENT_TIMESTAMP),
('cache_misses', 0, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- ============================================
-- Comments and Documentation
-- ============================================

COMMENT ON TABLE salesforce_webhook_subscriptions IS 'Stores real-time webhook subscriptions for Salesforce events';
COMMENT ON TABLE salesforce_webhook_events IS 'Stores incoming webhook events from Salesforce';
COMMENT ON TABLE salesforce_bulk_jobs IS 'Tracks bulk API jobs for large-scale data operations';
COMMENT ON TABLE salesforce_bulk_job_batches IS 'Stores batch-level details for bulk jobs';
COMMENT ON TABLE salesforce_custom_objects_cache IS 'Caches custom object metadata for performance';
COMMENT ON TABLE salesforce_realtime_analytics IS 'Stores real-time metrics for analytics dashboards';
COMMENT ON TABLE salesforce_webhook_activity_log IS 'Audit log for webhook-related activities';
COMMENT ON TABLE salesforce_analytics_cache IS 'Caches pre-computed analytics results';
COMMENT ON TABLE salesforce_predictive_insights IS 'Stores AI-generated predictive insights';
COMMENT ON TABLE salesforce_integration_metrics IS 'Daily metrics for Salesforce integration performance';

COMMENT ON FUNCTION cleanup_expired_cache() IS 'Removes expired cache data and old records to maintain performance';

-- ============================================
-- Security Considerations
-- ============================================

-- Row Level Security (RLS) for user data isolation
-- Note: Enable RLS based on your security requirements
-- ALTER TABLE salesforce_webhook_subscriptions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE salesforce_bulk_jobs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE salesforce_analytics_cache ENABLE ROW LEVEL SECURITY;

-- Example RLS policies (customize based on your security model)
-- CREATE POLICY user_webhook_subscriptions ON salesforce_webhook_subscriptions
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());
--
-- CREATE POLICY user_bulk_jobs ON salesforce_bulk_jobs
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- ============================================
-- Performance Recommendations
-- ============================================

-- 1. Schedule regular cleanup using the cleanup_expired_cache() function
--    Example: Run daily at 2 AM using a cron job:
--    SELECT cleanup_expired_cache();

-- 2. Monitor table sizes and consider partitioning for large tables:
--    - salesforce_webhook_events (partition by created_at)
--    - salesforce_realtime_analytics (partition by created_at)
--    - salesforce_bulk_jobs (partition by created_at)

-- 3. Consider using compression for large JSONB columns:
--    ALTER TABLE salesforce_webhook_events ALTER COLUMN payload SET STORAGE EXTERNAL;
--    ALTER TABLE salesforce_webhook_events ALTER COLUMN changed_fields SET STORAGE EXTERNAL;

-- 4. Set appropriate autovacuum settings for high-traffic tables:
--    ALTER TABLE salesforce_webhook_events SET (autovacuum_vacuum_scale_factor = 0.1);
--    ALTER TABLE salesforce_realtime_analytics SET (autovacuum_vacuum_scale_factor = 0.1);

-- ============================================
-- Migration Notes
-- ============================================

-- This schema is designed to be backward compatible with existing OAuth tables.
-- Ensure the following tables exist before running this schema:
-- - users (for foreign key constraints)
-- - salesforce_oauth_tokens (for integration with existing auth system)

-- To migrate from basic to enhanced integration:
-- 1. Run this schema file
-- 2. Update application code to use enhanced features
-- 3. Migrate existing data if needed
-- 4. Configure webhook endpoints and subscriptions
-- 5. Set up monitoring and alerting for new metrics

-- ============================================
-- Testing Data (for development only)
-- ============================================

-- Comment out or remove for production
-- INSERT INTO salesforce_webhook_subscriptions (
--     subscription_id, user_id, object_type, events, callback_url, active
-- ) VALUES
-- ('test_sub_1', 'test_user', 'Account', '["created", "updated"]', 'https://test.example.com/webhook', true),
-- ('test_sub_2', 'test_user', 'Opportunity', '["created", "updated", "deleted"]', 'https://test.example.com/webhook', true);