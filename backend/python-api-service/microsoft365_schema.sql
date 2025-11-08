-- Microsoft 365 Integration Database Schema
-- Complete schema for Microsoft 365 unified platform integration

-- M365 Integration Table
CREATE TABLE IF NOT EXISTS m365_integrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id VARCHAR(255) NOT NULL UNIQUE,
    client_id VARCHAR(255) NOT NULL,
    client_secret VARCHAR(500) NOT NULL,
    redirect_uri VARCHAR(500) NOT NULL,
    scopes TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    integration_status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50) DEFAULT 'idle',
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    settings JSON DEFAULT '{}',
    metadata JSON DEFAULT '{}',
    FOREIGN KEY (tenant_id) REFERENCES users(id) ON DELETE CASCADE
);

-- M365 Users Table
CREATE TABLE IF NOT EXISTS m365_users (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    mail VARCHAR(255),
    user_principal_name VARCHAR(255) NOT NULL UNIQUE,
    job_title VARCHAR(255),
    department VARCHAR(255),
    office_location VARCHAR(255),
    company_name VARCHAR(255),
    last_sign_in_date_time TIMESTAMP,
    usage_location VARCHAR(100),
    license_details JSON DEFAULT '{}',
    account_enabled BOOLEAN DEFAULT TRUE,
    user_type VARCHAR(50) DEFAULT 'member',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE
);

-- M365 Teams Table
CREATE TABLE IF NOT EXISTS m365_teams (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    visibility VARCHAR(50) DEFAULT 'public',
    mail_nickname VARCHAR(255),
    created_date_time TIMESTAMP,
    team_type VARCHAR(50) DEFAULT 'standard',
    is_archived BOOLEAN DEFAULT FALSE,
    member_count INTEGER DEFAULT 0,
    channel_count INTEGER DEFAULT 0,
    owner_id VARCHAR(255),
    tags TEXT DEFAULT '',
    settings JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES m365_users(id) ON DELETE SET NULL
);

-- M365 Team Channels Table
CREATE TABLE IF NOT EXISTS m365_team_channels (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    team_id VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    is_favorite_by_default BOOLEAN DEFAULT FALSE,
    email VARCHAR(255),
    membership_type VARCHAR(50) DEFAULT 'standard',
    created_date_time TIMESTAMP,
    web_url VARCHAR(500),
    message_count INTEGER DEFAULT 0,
    moderator_count INTEGER DEFAULT 0,
    settings JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES m365_teams(id) ON DELETE CASCADE
);

-- M365 Team Members Table
CREATE TABLE IF NOT EXISTS m365_team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    team_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'member',
    display_name VARCHAR(255),
    email VARCHAR(255),
    joined_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    permissions JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(integration_id, team_id, user_id),
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES m365_teams(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES m365_users(id) ON DELETE CASCADE
);

-- M365 Messages Table (Teams Chat and Email)
CREATE TABLE IF NOT EXISTS m365_messages (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    message_type VARCHAR(50) NOT NULL, -- email, chat, channel_message
    subject TEXT,
    body TEXT NOT NULL,
    from_address VARCHAR(255) NOT NULL,
    to_addresses TEXT DEFAULT '',
    cc_addresses TEXT DEFAULT '',
    bcc_addresses TEXT DEFAULT '',
    timestamp TIMESTAMP NOT NULL,
    attachments JSON DEFAULT '[]',
    conversation_id VARCHAR(255),
    channel_id VARCHAR(255),
    team_id VARCHAR(255),
    importance VARCHAR(50) DEFAULT 'normal',
    is_read BOOLEAN DEFAULT FALSE,
    is_draft BOOLEAN DEFAULT FALSE,
    parent_message_id VARCHAR(255),
    thread_id VARCHAR(255),
    message_format VARCHAR(50) DEFAULT 'html',
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES m365_team_channels(id) ON DELETE SET NULL,
    FOREIGN KEY (team_id) REFERENCES m365_teams(id) ON DELETE SET NULL
);

-- M365 Documents Table (OneDrive and SharePoint)
CREATE TABLE IF NOT EXISTS m365_documents (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100),
    size_bytes BIGINT DEFAULT 0,
    modified_date TIMESTAMP NOT NULL,
    created_date TIMESTAMP NOT NULL,
    file_path VARCHAR(1000),
    share_link VARCHAR(500),
    owner_id VARCHAR(255),
    parent_folder_id VARCHAR(255),
    document_type VARCHAR(50) DEFAULT 'onedrive', -- onedrive, sharepoint, teams_file
    collaboration_link VARCHAR(500),
    version_count INTEGER DEFAULT 1,
    tags TEXT DEFAULT '',
    metadata JSON DEFAULT '{}',
    content_hash VARCHAR(255),
    is_shared BOOLEAN DEFAULT FALSE,
    sharing_permissions JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES m365_users(id) ON DELETE SET NULL
);

-- M365 Calendar Events Table
CREATE TABLE IF NOT EXISTS m365_calendar_events (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    subject VARCHAR(500) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    attendees TEXT DEFAULT '',
    organizer VARCHAR(255) NOT NULL,
    description TEXT,
    location VARCHAR(500),
    event_type VARCHAR(50) DEFAULT 'meeting', -- meeting, appointment, all_day_event
    teams_meeting_url VARCHAR(500),
    recording_url VARCHAR(500),
    meeting_id VARCHAR(255),
    is_online BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'scheduled', -- scheduled, started, ended, cancelled
    is_all_day BOOLEAN DEFAULT FALSE,
    recurrence_pattern TEXT,
    reminder_minutes INTEGER DEFAULT 15,
    attachments JSON DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE
);

-- M365 Power Automate Flows Table
CREATE TABLE IF NOT EXISTS m365_power_automate_flows (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    display_name VARCHAR(500) NOT NULL,
    description TEXT,
    flow_type VARCHAR(50) DEFAULT 'automated', -- automated, instant, scheduled
    status VARCHAR(50) DEFAULT 'enabled', -- enabled, disabled, failed
    created_date_time TIMESTAMP NOT NULL,
    last_execution_time TIMESTAMP,
    execution_count INTEGER DEFAULT 0,
    trigger_type VARCHAR(255),
    connector_count INTEGER DEFAULT 0,
    environment_name VARCHAR(255) DEFAULT 'Default',
    flow_definition JSON DEFAULT '{}',
    error_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 100.0,
    last_error TEXT,
    tags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE
);

-- M365 SharePoint Sites Table
CREATE TABLE IF NOT EXISTS m365_sharepoint_sites (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    web_url VARCHAR(500) NOT NULL,
    site_type VARCHAR(50) DEFAULT 'team_site', -- team_site, communication_site, group_site
    created_date_time TIMESTAMP NOT NULL,
    last_modified_date_time TIMESTAMP NOT NULL,
    storage_quota_bytes BIGINT DEFAULT 0,
    storage_used_bytes BIGINT DEFAULT 0,
    owner_id VARCHAR(255),
    member_count INTEGER DEFAULT 0,
    permission_level VARCHAR(50) DEFAULT 'read', -- read, write, admin
    is_hub_site BOOLEAN DEFAULT FALSE,
    hub_site_id VARCHAR(255),
    template VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    tags TEXT DEFAULT '',
    settings JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES m365_users(id) ON DELETE SET NULL
);

-- M365 Workflows Table (Cross-service workflows)
CREATE TABLE IF NOT EXISTS m365_workflows (
    id VARCHAR(255) PRIMARY KEY,
    integration_id INTEGER NOT NULL,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    workflow_type VARCHAR(50) DEFAULT 'cross_service',
    status VARCHAR(50) DEFAULT 'active', -- active, inactive, paused, error
    trigger_config JSON DEFAULT '{}',
    action_config JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_execution_at TIMESTAMP,
    execution_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    settings JSON DEFAULT '{}',
    created_by VARCHAR(255),
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES m365_users(id) ON DELETE SET NULL
);

-- M365 Workflow Executions Table
CREATE TABLE IF NOT EXISTS m365_workflow_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    workflow_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'running', -- running, completed, failed, cancelled
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    execution_time_seconds INTEGER,
    trigger_data JSON DEFAULT '{}',
    result_data JSON DEFAULT '{}',
    error_message TEXT,
    logs TEXT,
    metadata JSON DEFAULT '{}',
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (workflow_id) REFERENCES m365_workflows(id) ON DELETE CASCADE
);

-- M365 API Usage Table
CREATE TABLE IF NOT EXISTS m365_api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(255),
    request_size_bytes INTEGER DEFAULT 0,
    response_size_bytes INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSON DEFAULT '{}',
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES m365_users(id) ON DELETE SET NULL
);

-- M365 Sync Status Table
CREATE TABLE IF NOT EXISTS m365_sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    sync_type VARCHAR(50) NOT NULL, -- full, incremental, webhook
    status VARCHAR(50) DEFAULT 'idle', -- idle, running, completed, failed, paused
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    records_processed INTEGER DEFAULT 0,
    records_total INTEGER DEFAULT 0,
    records_success INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    last_sync_point TEXT,
    error_message TEXT,
    progress_percentage DECIMAL(5,2) DEFAULT 0.0,
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(integration_id, service_name, sync_type),
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE
);

-- M365 Webhooks Table
CREATE TABLE IF NOT EXISTS m365_webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    webhook_id VARCHAR(255) NOT NULL UNIQUE,
    resource VARCHAR(500) NOT NULL,
    event_types TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'active', -- active, inactive, expired, error
    notification_url VARCHAR(500) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    last_notification_at TIMESTAMP,
    notification_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    metadata JSON DEFAULT '{}',
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE
);

-- M365 Settings Table
CREATE TABLE IF NOT EXISTS m365_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    setting_key VARCHAR(255) NOT NULL,
    setting_value TEXT,
    setting_type VARCHAR(50) DEFAULT 'string', -- string, integer, boolean, json
    description TEXT,
    is_encrypted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(integration_id, setting_key),
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE
);

-- M365 Analytics Table
CREATE TABLE IF NOT EXISTS m365_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_id INTEGER NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    metric_value DECIMAL(15,2),
    metric_unit VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    period VARCHAR(50) DEFAULT 'hourly', -- hourly, daily, weekly, monthly
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (integration_id) REFERENCES m365_integrations(id) ON DELETE CASCADE
);

-- Create Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_m365_integrations_tenant_id ON m365_integrations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_m365_integrations_status ON m365_integrations(integration_status);
CREATE INDEX IF NOT EXISTS idx_m365_users_integration_id ON m365_users(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_users_upn ON m365_users(user_principal_name);
CREATE INDEX IF NOT EXISTS idx_m365_teams_integration_id ON m365_teams(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_teams_owner_id ON m365_teams(owner_id);
CREATE INDEX IF NOT EXISTS idx_m365_team_channels_team_id ON m365_team_channels(team_id);
CREATE INDEX IF NOT EXISTS idx_m365_team_channels_integration_id ON m365_team_channels(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_team_members_team_id ON m365_team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_m365_team_members_user_id ON m365_team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_m365_messages_integration_id ON m365_messages(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_messages_type ON m365_messages(message_type);
CREATE INDEX IF NOT EXISTS idx_m365_messages_timestamp ON m365_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_m365_messages_conversation_id ON m365_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_m365_documents_integration_id ON m365_documents(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_documents_type ON m365_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_m365_documents_owner_id ON m365_documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_m365_calendar_events_integration_id ON m365_calendar_events(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_calendar_events_start_time ON m365_calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_m365_power_flows_integration_id ON m365_power_automate_flows(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_power_flows_status ON m365_power_automate_flows(status);
CREATE INDEX IF NOT EXISTS idx_m365_sharepoint_sites_integration_id ON m365_sharepoint_sites(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_workflows_integration_id ON m365_workflows(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_workflow_executions_workflow_id ON m365_workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_m365_api_usage_integration_id ON m365_api_usage(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_api_usage_timestamp ON m365_api_usage(timestamp);
CREATE INDEX IF NOT EXISTS idx_m365_sync_status_integration_id ON m365_sync_status(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_webhooks_integration_id ON m365_webhooks(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_settings_integration_id ON m365_settings(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_analytics_integration_id ON m365_analytics(integration_id);
CREATE INDEX IF NOT EXISTS idx_m365_analytics_service_name ON m365_analytics(service_name);
CREATE INDEX IF NOT EXISTS idx_m365_analytics_timestamp ON m365_analytics(timestamp);

-- Create Triggers for Automatic Timestamp Updates
CREATE TRIGGER IF NOT EXISTS update_m365_integrations_updated_at
    AFTER UPDATE ON m365_integrations
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_users_updated_at
    AFTER UPDATE ON m365_users
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_teams_updated_at
    AFTER UPDATE ON m365_teams
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_team_channels_updated_at
    AFTER UPDATE ON m365_team_channels
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_team_members_updated_at
    AFTER UPDATE ON m365_team_members
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_messages_updated_at
    AFTER UPDATE ON m365_messages
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_documents_updated_at
    AFTER UPDATE ON m365_documents
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_calendar_events_updated_at
    AFTER UPDATE ON m365_calendar_events
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_power_flows_updated_at
    AFTER UPDATE ON m365_power_automate_flows
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_sharepoint_sites_updated_at
    AFTER UPDATE ON m365_sharepoint_sites
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_workflows_updated_at
    AFTER UPDATE ON m365_workflows
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

CREATE TRIGGER IF NOT EXISTS update_m365_settings_updated_at
    AFTER UPDATE ON m365_settings
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;

-- Insert Default Settings
INSERT OR IGNORE INTO m365_settings (integration_id, setting_key, setting_value, setting_type, description) VALUES
(0, 'sync_frequency', '3600', 'integer', 'Sync frequency in seconds'),
(0, 'max_retries', '3', 'integer', 'Maximum retry attempts for API calls'),
(0, 'request_timeout', '30', 'integer', 'Request timeout in seconds'),
(0, 'batch_size', '100', 'integer', 'Batch size for bulk operations'),
(0, 'enable_webhooks', 'true', 'boolean', 'Enable webhook processing'),
(0, 'enable_analytics', 'true', 'boolean', 'Enable analytics collection'),
(0, 'enable_audit_logging', 'true', 'boolean', 'Enable audit logging'),
(0, 'data_retention_days', '365', 'integer', 'Data retention period in days'),
(0, 'max_file_size_mb', '250', 'integer', 'Maximum file size in MB'),
(0, 'enable_encryption', 'true', 'boolean', 'Enable data encryption'),
(0, 'api_rate_limit', '6000', 'integer', 'API rate limit per minute'),
(0, 'enable_real_time_sync', 'true', 'boolean', 'Enable real-time synchronization'),
(0, 'backup_enabled', 'true', 'boolean', 'Enable automatic backups'),
(0, 'monitoring_enabled', 'true', 'boolean', 'Enable service monitoring');

-- Create Views for Common Queries
CREATE VIEW IF NOT EXISTS m365_active_integrations AS
SELECT * FROM m365_integrations WHERE integration_status = 'active';

CREATE VIEW IF NOT EXISTS m365_team_details AS
SELECT 
    t.*,
    u.display_name as owner_name,
    u.mail as owner_email,
    tc.channel_count,
    tm.member_count
FROM m365_teams t
LEFT JOIN m365_users u ON t.owner_id = u.id
LEFT JOIN (
    SELECT team_id, COUNT(*) as channel_count 
    FROM m365_team_channels 
    GROUP BY team_id
) tc ON t.id = tc.team_id
LEFT JOIN (
    SELECT team_id, COUNT(*) as member_count 
    FROM m365_team_members 
    WHERE is_active = 1 
    GROUP BY team_id
) tm ON t.id = tm.team_id;

CREATE VIEW IF NOT EXISTS m365_message_summary AS
SELECT 
    integration_id,
    message_type,
    DATE(timestamp) as message_date,
    COUNT(*) as message_count,
    COUNT(CASE WHEN is_read = 1 THEN 1 END) as read_count,
    COUNT(CASE WHEN is_draft = 0 THEN 1 END) as sent_count
FROM m365_messages
GROUP BY integration_id, message_type, DATE(timestamp);

CREATE VIEW IF NOT EXISTS m365_document_summary AS
SELECT 
    integration_id,
    document_type,
    owner_id,
    COUNT(*) as document_count,
    SUM(size_bytes) as total_size,
    AVG(size_bytes) as average_size,
    COUNT(CASE WHEN is_shared = 1 THEN 1 END) as shared_count
FROM m365_documents
GROUP BY integration_id, document_type, owner_id;

CREATE VIEW IF NOT EXISTS m365_api_usage_summary AS
SELECT 
    integration_id,
    service_name,
    DATE(timestamp) as usage_date,
    COUNT(*) as request_count,
    AVG(response_time_ms) as avg_response_time,
    COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count,
    SUM(response_size_bytes) as total_response_size
FROM m365_api_usage
GROUP BY integration_id, service_name, DATE(timestamp);

CREATE VIEW IF NOT EXISTS m365_workflow_performance AS
SELECT 
    integration_id,
    workflow_id,
    COUNT(*) as execution_count,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as success_count,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as error_count,
    AVG(execution_time_seconds) as avg_execution_time,
    MAX(started_at) as last_execution,
    MAX(CASE WHEN status = 'completed' THEN completed_at END) as last_success
FROM m365_workflow_executions
GROUP BY integration_id, workflow_id;

-- Schema Version and Metadata
CREATE TABLE IF NOT EXISTS m365_schema_info (
    version VARCHAR(20) DEFAULT '1.0.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT DEFAULT 'Microsoft 365 Integration Schema'
);

INSERT OR IGNORE INTO m365_schema_info (version, description) VALUES ('1.0.0', 'Initial Microsoft 365 Integration Schema');