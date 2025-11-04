-- Asana OAuth Token Table for ATOM Integration
-- SQL schema for Asana OAuth token storage with encryption support

-- Create Asana OAuth tokens table
CREATE TABLE IF NOT EXISTS user_asana_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT DEFAULT '',
    expires_at TIMESTAMPTZ NOT NULL,
    scope TEXT DEFAULT '',
    user_info JSONB DEFAULT '{}',
    state VARCHAR(255) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast user lookup
CREATE INDEX IF NOT EXISTS idx_user_asana_oauth_tokens_user_id 
    ON user_asana_oauth_tokens(user_id);

-- Create index for token expiration checks
CREATE INDEX IF NOT EXISTS idx_user_asana_oauth_tokens_expires_at 
    ON user_asana_oauth_tokens(expires_at);

-- Create index for state lookup
CREATE INDEX IF NOT EXISTS idx_user_asana_oauth_tokens_state 
    ON user_asana_oauth_tokens(state);

-- Add comments
COMMENT ON TABLE user_asana_oauth_tokens IS 
    'Stores Asana OAuth tokens for ATOM users with encrypted access and refresh tokens';
COMMENT ON COLUMN user_asana_oauth_tokens.user_id IS 
    'Unique user identifier from ATOM system';
COMMENT ON COLUMN user_asana_oauth_tokens.access_token IS 
    'Encrypted Asana access token (JWT format)';
COMMENT ON COLUMN user_asana_oauth_tokens.refresh_token IS 
    'Encrypted Asana refresh token for token renewal';
COMMENT ON COLUMN user_asana_oauth_tokens.expires_at IS 
    'Token expiration timestamp in UTC';
COMMENT ON COLUMN user_asana_oauth_tokens.scope IS 
    'OAuth scopes granted by the user';
COMMENT ON COLUMN user_asana_oauth_tokens.user_info IS 
    'Asana user profile information (JSON format)';
COMMENT ON COLUMN user_asana_oauth_tokens.state IS 
    'OAuth state parameter for CSRF protection';

-- Create Asana tasks table for metadata storage
CREATE TABLE IF NOT EXISTS user_asana_tasks (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    name TEXT NOT NULL,
    notes TEXT DEFAULT '',
    completed BOOLEAN DEFAULT FALSE,
    assignee_id VARCHAR(255) DEFAULT '',
    assignee_name VARCHAR(255) DEFAULT '',
    assignee_email VARCHAR(255) DEFAULT '',
    project_id VARCHAR(255) DEFAULT '',
    project_name VARCHAR(255) DEFAULT '',
    project_color VARCHAR(255) DEFAULT 'blue',
    section_id VARCHAR(255) DEFAULT '',
    section_name VARCHAR(255) DEFAULT '',
    due_on DATE DEFAULT NULL,
    due_at TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    tags JSONB DEFAULT '[]',
    custom_fields JSONB DEFAULT '[]',
    status VARCHAR(255) DEFAULT 'todo',
    metadata JSONB DEFAULT '{}',
    stored_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, task_id)
);

-- Create indexes for tasks
CREATE INDEX IF NOT EXISTS idx_user_asana_tasks_user_id 
    ON user_asana_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_tasks_task_id 
    ON user_asana_tasks(task_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_tasks_project_id 
    ON user_asana_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_tasks_completed 
    ON user_asana_tasks(completed);
CREATE INDEX IF NOT EXISTS idx_user_asana_tasks_status 
    ON user_asana_tasks(status);
CREATE INDEX IF NOT EXISTS idx_user_asana_tasks_due_on 
    ON user_asana_tasks(due_on);
CREATE INDEX IF NOT EXISTS idx_user_asana_tasks_created_at 
    ON user_asana_tasks(created_at);

-- Add comments for tasks
COMMENT ON TABLE user_asana_tasks IS 
    'Stores Asana task metadata for ATOM users';
COMMENT ON COLUMN user_asana_tasks.task_id IS 
    'Asana task identifier (GID)';
COMMENT ON COLUMN user_asana_tasks.assignee_id IS 
    'Asana assignee user identifier';
COMMENT ON COLUMN user_asana_tasks.tags IS 
    'Task tags and labels (JSON array)';
COMMENT ON COLUMN user_asana_tasks.custom_fields IS 
    'Custom field values (JSON array)';
COMMENT ON COLUMN user_asana_tasks.status IS 
    'Task status (todo, in_progress, completed, etc.)';
COMMENT ON COLUMN user_asana_tasks.metadata IS 
    'Additional task metadata (JSON object)';

-- Create Asana projects table for metadata storage
CREATE TABLE IF NOT EXISTS user_asana_projects (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    project_id VARCHAR(255) NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    color VARCHAR(255) DEFAULT 'blue',
    public BOOLEAN DEFAULT FALSE,
    owner_id VARCHAR(255) DEFAULT '',
    owner_name VARCHAR(255) DEFAULT '',
    team_id VARCHAR(255) DEFAULT '',
    team_name VARCHAR(255) DEFAULT '',
    archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    workspace_id VARCHAR(255) DEFAULT '',
    workspace_name VARCHAR(255) DEFAULT '',
    members_count INTEGER DEFAULT 0,
    tasks_count INTEGER DEFAULT 0,
    completed_count INTEGER DEFAULT 0,
    progress INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    stored_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, project_id)
);

-- Create indexes for projects
CREATE INDEX IF NOT EXISTS idx_user_asana_projects_user_id 
    ON user_asana_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_projects_project_id 
    ON user_asana_projects(project_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_projects_team_id 
    ON user_asana_projects(team_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_projects_archived 
    ON user_asana_projects(archived);
CREATE INDEX IF NOT EXISTS idx_user_asana_projects_public 
    ON user_asana_projects(public);
CREATE INDEX IF NOT EXISTS idx_user_asana_projects_created_at 
    ON user_asana_projects(created_at);

-- Add comments for projects
COMMENT ON TABLE user_asana_projects IS 
    'Stores Asana project metadata for ATOM users';
COMMENT ON COLUMN user_asana_projects.project_id IS 
    'Asana project identifier (GID)';
COMMENT ON COLUMN user_asana_projects.owner_id IS 
    'Asana project owner user identifier';
COMMENT ON COLUMN user_asana_projects.team_id IS 
    'Asana team identifier';
COMMENT ON COLUMN user_asana_projects.progress IS 
    'Project completion percentage';
COMMENT ON COLUMN user_asana_projects.metadata IS 
    'Additional project metadata (JSON object)';

-- Create Asana sections table for metadata storage
CREATE TABLE IF NOT EXISTS user_asana_sections (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    section_id VARCHAR(255) NOT NULL,
    name TEXT NOT NULL,
    project_id VARCHAR(255) DEFAULT '',
    project_name VARCHAR(255) DEFAULT '',
    project_color VARCHAR(255) DEFAULT 'blue',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    tasks_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    stored_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, section_id)
);

-- Create indexes for sections
CREATE INDEX IF NOT EXISTS idx_user_asana_sections_user_id 
    ON user_asana_sections(user_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_sections_section_id 
    ON user_asana_sections(section_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_sections_project_id 
    ON user_asana_sections(project_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_sections_created_at 
    ON user_asana_sections(created_at);

-- Add comments for sections
COMMENT ON TABLE user_asana_sections IS 
    'Stores Asana section metadata for ATOM users';
COMMENT ON COLUMN user_asana_sections.section_id IS 
    'Asana section identifier (GID)';
COMMENT ON COLUMN user_asana_sections.project_id IS 
    'Asana project identifier this section belongs to';
COMMENT ON COLUMN user_asana_sections.tasks_count IS 
    'Number of tasks in this section';
COMMENT ON COLUMN user_asana_sections.metadata IS 
    'Additional section metadata (JSON object)';

-- Create Asana teams table for metadata storage
CREATE TABLE IF NOT EXISTS user_asana_teams (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    team_id VARCHAR(255) NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    organization_id VARCHAR(255) DEFAULT '',
    organization_name VARCHAR(255) DEFAULT '',
    organization_url VARCHAR(255) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    members_count INTEGER DEFAULT 0,
    projects_count INTEGER DEFAULT 0,
    tasks_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    stored_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, team_id)
);

-- Create indexes for teams
CREATE INDEX IF NOT EXISTS idx_user_asana_teams_user_id 
    ON user_asana_teams(user_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_teams_team_id 
    ON user_asana_teams(team_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_teams_organization_id 
    ON user_asana_teams(organization_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_teams_created_at 
    ON user_asana_teams(created_at);

-- Add comments for teams
COMMENT ON TABLE user_asana_teams IS 
    'Stores Asana team metadata for ATOM users';
COMMENT ON COLUMN user_asana_teams.team_id IS 
    'Asana team identifier (GID)';
COMMENT ON COLUMN user_asana_teams.organization_id IS 
    'Asana organization identifier';
COMMENT ON COLUMN user_asana_teams.organization_url IS 
    'Asana organization permalink URL';
COMMENT ON COLUMN user_asana_teams.metadata IS 
    'Additional team metadata (JSON object)';

-- Create Asana users table for user metadata storage
CREATE TABLE IF NOT EXISTS user_asana_users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) DEFAULT '',
    avatar_url_128x128 VARCHAR(255) DEFAULT '',
    workspaces JSONB DEFAULT '[]',
    active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    stored_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for users
CREATE INDEX IF NOT EXISTS idx_user_asana_users_user_id 
    ON user_asana_users(user_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_users_email 
    ON user_asana_users(email);
CREATE INDEX IF NOT EXISTS idx_user_asana_users_active 
    ON user_asana_users(active);
CREATE INDEX IF NOT EXISTS idx_user_asana_users_last_login 
    ON user_asana_users(last_login);

-- Add comments for users
COMMENT ON TABLE user_asana_users IS 
    'Stores Asana user metadata for ATOM users';
COMMENT ON COLUMN user_asana_users.user_id IS 
    'Asana user identifier (GID)';
COMMENT ON COLUMN user_asana_users.avatar_url_128x128 IS 
    'User profile avatar URL (128x128 pixels)';
COMMENT ON COLUMN user_asana_users.workspaces IS 
    'User workspaces information (JSON array)';
COMMENT ON COLUMN user_asana_users.active IS 
    'Whether the user account is active';
COMMENT ON COLUMN user_asana_users.metadata IS 
    'Additional user metadata (JSON object)';

-- Create Asana webhook subscriptions table
CREATE TABLE IF NOT EXISTS user_asana_webhooks (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    webhook_id VARCHAR(255) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    resource_type VARCHAR(255) NOT NULL,
    target_url VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    filters JSONB DEFAULT '{}',
    last_triggered TIMESTAMPTZ DEFAULT NULL,
    trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    UNIQUE(user_id, webhook_id)
);

-- Create indexes for webhooks
CREATE INDEX IF NOT EXISTS idx_user_asana_webhooks_user_id 
    ON user_asana_webhooks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_webhooks_webhook_id 
    ON user_asana_webhooks(webhook_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_webhooks_resource_id 
    ON user_asana_webhooks(resource_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_webhooks_resource_type 
    ON user_asana_webhooks(resource_type);
CREATE INDEX IF NOT EXISTS idx_user_asana_webhooks_active 
    ON user_asana_webhooks(active);

-- Add comments for webhooks
COMMENT ON TABLE user_asana_webhooks IS 
    'Stores Asana webhook subscriptions for ATOM users';
COMMENT ON COLUMN user_asana_webhooks.webhook_id IS 
    'Asana webhook identifier';
COMMENT ON COLUMN user_asana_webhooks.resource_id IS 
    'Asana resource identifier the webhook monitors';
COMMENT ON COLUMN user_asana_webhooks.resource_type IS 
    'Resource type (task, project, story, etc.)';
COMMENT ON COLUMN user_asana_webhooks.target_url IS 
    'URL to receive webhook notifications';
COMMENT ON COLUMN user_asana_webhooks.filters IS 
    'Webhook event filters (JSON object)';
COMMENT ON COLUMN user_asana_webhooks.last_triggered IS 
    'Last time webhook was triggered';
COMMENT ON COLUMN user_asana_webhooks.trigger_count IS 
    'Number of times webhook has been triggered';
COMMENT ON COLUMN user_asana_webhooks.metadata IS 
    'Additional webhook metadata (JSON object)';

-- Create Asana sync logs table for audit trail
CREATE TABLE IF NOT EXISTS user_asana_sync_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    sync_type VARCHAR(255) NOT NULL,
    resource_type VARCHAR(255) DEFAULT '',
    resource_id VARCHAR(255) DEFAULT '',
    status VARCHAR(255) NOT NULL,
    message TEXT DEFAULT '',
    items_processed INTEGER DEFAULT 0,
    items_synced INTEGER DEFAULT 0,
    errors JSONB DEFAULT '[]',
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ DEFAULT NULL,
    duration_ms INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- Create indexes for sync logs
CREATE INDEX IF NOT EXISTS idx_user_asana_sync_logs_user_id 
    ON user_asana_sync_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_asana_sync_logs_sync_type 
    ON user_asana_sync_logs(sync_type);
CREATE INDEX IF NOT EXISTS idx_user_asana_sync_logs_status 
    ON user_asana_sync_logs(status);
CREATE INDEX IF NOT EXISTS idx_user_asana_sync_logs_started_at 
    ON user_asana_sync_logs(started_at);

-- Add comments for sync logs
COMMENT ON TABLE user_asana_sync_logs IS 
    'Stores Asana synchronization logs for ATOM users';
COMMENT ON COLUMN user_asana_sync_logs.sync_type IS 
    'Type of synchronization (full, incremental, webhook)';
COMMENT ON COLUMN user_asana_sync_logs.resource_type IS 
    'Type of resource being synchronized (tasks, projects, etc.)';
COMMENT ON COLUMN user_asana_sync_logs.resource_id IS 
    'Specific resource identifier being synchronized';
COMMENT ON COLUMN user_asana_sync_logs.status IS 
    'Sync status (started, running, completed, failed)';
COMMENT ON COLUMN user_asana_sync_logs.errors IS 
    'Array of errors encountered during sync (JSON array)';
COMMENT ON COLUMN user_asana_sync_logs.duration_ms IS 
    'Sync duration in milliseconds';
COMMENT ON COLUMN user_asana_sync_logs.metadata IS 
    'Additional sync metadata (JSON object)';

-- Update function for timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add update triggers
CREATE TRIGGER update_user_asana_oauth_tokens_updated_at 
    BEFORE UPDATE ON user_asana_oauth_tokens 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_asana_tasks_updated_at 
    BEFORE UPDATE ON user_asana_tasks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_asana_projects_updated_at 
    BEFORE UPDATE ON user_asana_projects 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_asana_teams_updated_at 
    BEFORE UPDATE ON user_asana_teams 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_asana_webhooks_updated_at 
    BEFORE UPDATE ON user_asana_webhooks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing (optional)
INSERT INTO user_asana_oauth_tokens (user_id, access_token, refresh_token, expires_at, scope, user_info) 
VALUES (
    'test-asana-user',
    'mock_access_token_' || ENCODE(GEN_RANDOM_BYTES(16), 'HEX'),
    'mock_refresh_token_' || ENCODE(GEN_RANDOM_BYTES(16), 'HEX'),
    CURRENT_TIMESTAMP + INTERVAL '1 hour',
    'default tasks:read tasks:write projects:read projects:write stories:read stories:write teams:read users:read webhooks:read webhooks:write',
    '{
        "gid": "1204910829086229",
        "name": "Alice Developer",
        "email": "alice@company.com",
        "avatar_url_128x128": "https://example.com/avatars/alice.png",
        "workspaces": [
            {
                "gid": "1204910829086249",
                "name": "Tech Company"
            }
        ],
        "active": true,
        "last_login": "' || CURRENT_TIMESTAMP || '"
    }'::jsonb
) ON CONFLICT (user_id) DO NOTHING;