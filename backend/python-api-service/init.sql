-- Initial database setup for ATOM
-- This file runs when the PostgreSQL container starts

-- Create database if it doesn't exist
-- Note: This is handled by docker-compose environment variables

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance
-- These will be created by SQLAlchemy migrations, but we can add additional ones here

-- Example: Full-text search index for messages
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_body_fts ON messages USING gin(to_tsvector('english', body));

-- Example: Index for task due dates
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_due_date ON tasks(due_date) WHERE due_date IS NOT NULL;

-- Example: Index for calendar events
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time);

-- Example: Partial index for unread messages
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_unread ON messages(user_id, timestamp DESC) WHERE unread = true;
