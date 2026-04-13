/**
 * Integration-specific type definitions
 * These types extend the auto-generated API types with integration-specific configurations
 */

export interface IntegrationConfig {
  id: string;
  name: string;
  provider: string;
  enabled: boolean;
  config: Record<string, unknown>;
}

export interface JiraConfig extends IntegrationConfig {
  provider: 'jira';
  domain: string;
  email: string;
  api_token: string;
}

export interface SlackConfig extends IntegrationConfig {
  provider: 'slack';
  workspace: string;
  bot_token: string;
}

export interface Microsoft365Config extends IntegrationConfig {
  provider: 'microsoft365';
  tenant_id: string;
  client_id: string;
}

export interface AsanaConfig extends IntegrationConfig {
  provider: 'asana';
  workspace_id: string;
  access_token: string;
}

export interface GoogleWorkspaceConfig extends IntegrationConfig {
  provider: 'google';
  calendar_id: string;
  api_key: string;
}

export interface TrelloConfig extends IntegrationConfig {
  provider: 'trello';
  board_id: string;
  api_key: string;
  token: string;
}

export interface BoxConfig extends IntegrationConfig {
  provider: 'box';
  folder_id: string;
  access_token: string;
}

export interface QuickBooksConfig extends IntegrationConfig {
  provider: 'quickbooks';
  realm_id: string;
  access_token: string;
}

export interface ZendeskConfig extends IntegrationConfig {
  provider: 'zendesk';
  subdomain: string;
  api_token: string;
}

export interface ZoomConfig extends IntegrationConfig {
  provider: 'zoom';
  client_id: string;
  access_token: string;
}

export interface NotionConfig extends IntegrationConfig {
  provider: 'notion';
  database_id: string;
  access_token: string;
}

export interface GitHubConfig extends IntegrationConfig {
  provider: 'github';
  repo_owner: string;
  repo_name: string;
  access_token: string;
}

export interface OutlookConfig extends IntegrationConfig {
  provider: 'outlook';
  mailbox: string;
  access_token: string;
}

export interface WhatsAppConfig extends IntegrationConfig {
  provider: 'whatsapp';
  phone_number_id: string;
  access_token: string;
}
