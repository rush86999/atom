-- Create integration_catalog table
CREATE TABLE IF NOT EXISTS integration_catalog (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    icon TEXT,
    color TEXT DEFAULT '#6366F1',
    auth_type TEXT DEFAULT 'none',
    native_id TEXT, -- Link to native implementation (e.g., 'slack')
    triggers TEXT DEFAULT '[]', -- JSON field as text
    actions TEXT DEFAULT '[]', -- JSON field as text
    popular BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster filtering
CREATE INDEX IF NOT EXISTS idx_integration_catalog_category ON integration_catalog(category);
CREATE INDEX IF NOT EXISTS idx_integration_catalog_popular ON integration_catalog(popular);
