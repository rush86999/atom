-- PostgreSQL Test Database Initialization Script
-- Run all basic setup for Atom testing database

-- Create test tables for core functionality
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- API sessions for authentication
CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Calendar events tracking
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    calendar_provider VARCHAR(100),
    external_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notes and documentation
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    tags TEXT[],
    linked_event_id UUID REFERENCES events(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector embeddings for semantic search
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    embedding_vector vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- External integrations tracking
CREATE TABLE IF NOT EXISTS integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(100) NOT NULL,
    provider_user_id VARCHAR(255),
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    scopes TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Activity logs
CREATE TABLE IF NOT EXISTS activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_events_user_time ON events(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_search ON notes USING gin(to_tsvector('english', title || ' ' || content));
CREATE INDEX IF NOT EXISTS idx_integrations_user_provider ON integrations(user_id, provider);
CREATE INDEX IF NOT EXISTS idx_activity_logs_user_time ON activity_logs(user_id, created_at DESC);

-- Insert test data
INSERT INTO users (email, password_hash, name) VALUES
('test@example.com', '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'Test User'),
('admin@example.com', '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'Admin User')
ON CONFLICT (email) DO NOTHING;

-- Test data for events
INSERT INTO events (user_id, title, description, start_time, end_time, calendar_provider) VALUES
((SELECT id FROM users WHERE email = 'test@example.com'), 'Test Meeting', 'A test event for E2E testing',
 NOW() + INTERVAL '2 hours', NOW() + INTERVAL '3 hours', 'google'),
((SELECT id FROM users WHERE email = 'test@example.com'), 'Integration Test', 'Testing calendar integration',
 NOW() + INTERVAL '24 hours', NOW() + INTERVAL '25 hours', 'google')
ON CONFLICT DO NOTHING;

-- Test data for notes
INSERT INTO notes (user_id, title, content, tags) VALUES
((SELECT id FROM users WHERE email = 'test@example.com'), 'Test Note', 'This is a test note for E2E testing', ARRAY['test', 'e2e']),
((SELECT id FROM users WHERE email = 'test@example.com'), 'Meeting Notes', 'Summary of integration testing meeting', ARRAY['meeting', 'testing']),
((SELECT id FROM users WHERE email = 'test@example.com'), 'Feature Documentation', 'Documentation for new feature', ARRAY['documentation', 'feature'])
ON CONFLICT DO NOTHING;

-- Grant permissions to test user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO test_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO test_user;
GRANT ALL PRIVILEGES ON DATABASE atom_test TO test_user;

-- Create a function for health checking
CREATE OR REPLACE FUNCTION check_database_health()
RETURNS TABLE (
    table_name text,
    row_count bigint
) AS $$
BEGIN
    RETURN QUERY
    SELECT schemaname||'.'||tablename::text, t.total_rows
    FROM pg_tables t1
    CROSS JOIN LATERAL (
        SELECT COUNT(*) total_rows
        FROM table_name = t1.schemaname||'.'||t1.tablename
    ) t
    WHERE schemaname = 'public'
    ORDER BY t.total_rows DESC;
END;
$$ LANGUAGE plpgsql;

-- Log successful initialization
SELECT 'PostgreSQL Test Database Initialized Successfully' AS status;
