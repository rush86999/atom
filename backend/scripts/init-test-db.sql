-- Test Database Initialization Script
-- This script runs when the PostgreSQL test container is first created
-- It sets up the necessary extensions and schema for testing

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text similarity searches
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- For composite indexes

-- pgvector is optional - try to install but don't fail if not available
-- The codebase has graceful degradation for vector embeddings
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        CREATE EXTENSION IF NOT EXISTS "vector";
        RAISE NOTICE 'pgvector extension installed';
    ELSE
        RAISE NOTICE 'pgvector extension not available - vector embeddings will use JSON fallback';
    END IF;
END $$;

-- Create test schemas if needed
-- (Most schemas are created by Alembic migrations)
-- This is just for additional test-specific setup

-- Grant permissions (test database already created by POSTGRES_DB)
GRANT ALL PRIVILEGES ON DATABASE atom_test_db TO atom_test;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Test database initialized successfully';
END $$;
