/**
 * ATOM Unified Communication Services Types
 * Shared types for Slack, Teams, and unified operations
 */

// Base Service Types
export interface ServiceHealth {
  status: 'healthy' | 'error' | 'warning' | 'unknown';
  api_healthy?: boolean;
  config_healthy?: boolean;
  token_valid?: boolean;
  last_check?: string;
  error?: string;
}

export interface ServiceImplementation {
  current: 'mock' | 'real';
  mock_available: boolean;
  real_available: boolean;
  health?: ServiceHealth;
}

export interface UnifiedServicesStatus {
  timestamp: string;
  environment: 'mock' | 'real';
  services: {
    Slack: ServiceImplementation;
    MicrosoftTeams: ServiceImplementation;
  };
}

// Common Message Types
export interface UnifiedMessage {
  id: string;
  thread_id?: string;
  service: 'slack' | 'teams';
  workspace_id?: string;
  team_id?: string;
  channel_id: string;
  from: string;
  subject?: string;
  preview: string;
  content: string;
  timestamp?: string;
  updated_at?: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  unread: boolean;
  status: 'sent' | 'received' | 'draft' | 'deleted';
  attachments: UnifiedAttachment[];
  mentions: UnifiedMention[];
  reactions: UnifiedReactions;
  reply_count?: number;
  is_edited?: boolean;
  is_deleted?: boolean;
}

export interface UnifiedAttachment {
  id: string;
  name?: string;
  title?: string;
  url: string;
  type: string;
  size: number;
  thumb_url?: string;
  mime_type?: string;
  service: 'slack' | 'teams';
}

export interface UnifiedMention {
  user_id?: string;
  user_name?: string;
  display_name?: string;
  text: string;
  raw: string;
  service: 'slack' | 'teams';
}

export interface UnifiedReactions {
  like: number;
  love: number;
  laugh: number;
  wow: number;
  sad: number;
  angry: number;
  thumbs_up: number;
  thumbs_down: number;
  eyes: number;
  heart: number;
  rocket: number;
  raised_hands: number;
  confused: number;
}

// Common Workspace Types
export interface UnifiedWorkspace {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  service: 'slack' | 'teams';
  team_id?: string;
  workspace_id?: string;
  domain?: string;
  icon_url?: string;
  is_verified?: boolean;
  is_archived?: boolean;
  created_at?: string;
  updated_at?: string;
  member_count?: number;
  channel_count?: number;
  total_messages?: number;
  last_sync?: string;
}

// Common Channel Types
export interface UnifiedChannel {
  id: string;
  name: string;
  display_name: string;
  service: 'slack' | 'teams';
  workspace_id?: string;
  team_id?: string;
  channel_type: 'public' | 'private' | 'dm' | 'group_dm' | 'standard' | 'mpim';
  purpose?: string;
  topic?: string;
  description?: string;
  member_count?: number;
  is_archived?: boolean;
  is_private?: boolean;
  is_favorite?: boolean;
  created_at?: string;
  updated_at?: string;
  unread_count?: number;
  total_messages?: number;
  last_message?: UnifiedMessage;
  last_sync?: string;
}

// Service-specific Types (for compatibility)
export interface SlackMessage extends UnifiedMessage {
  service: 'slack';
  workspace_id: string;
  thread_info?: {
    thread_id: string;
    reply_count: number;
    last_reply: string;
  };
}

export interface TeamsMessage extends UnifiedMessage {
  service: 'teams';
  team_id: string;
  thread_id: string;
}

export interface SlackWorkspace extends UnifiedWorkspace {
  service: 'slack';
  workspace_id: string;
  domain: string;
  installation_type: 'user' | 'workspace' | 'bot';
}

export interface TeamsWorkspace extends UnifiedWorkspace {
  service: 'teams';
  team_id: string;
  team_type: 'Standard' | 'Education' | 'Template';
  visibility: 'Public' | 'Private';
}

export interface SlackChannel extends UnifiedChannel {
  service: 'slack';
  workspace_id: string;
  channel_type: 'public' | 'private' | 'dm' | 'group_dm' | 'mpim';
  is_starred?: boolean;
}

export interface TeamsChannel extends UnifiedChannel {
  service: 'teams';
  team_id: string;
  channel_type: 'public' | 'private' | 'dm' | 'group_dm' | 'standard';
}

// API Request/Response Types
export interface ServiceSwitchRequest {
  service_name: 'Slack' | 'MicrosoftTeams';
  implementation_type: 'mock' | 'real';
}

export interface ServiceSwitchResponse {
  ok: boolean;
  service_name: string;
  old_implementation?: string;
  new_implementation?: string;
  message?: string;
  error?: string;
}

export interface WorkspacesResponse {
  ok: boolean;
  workspaces: UnifiedWorkspace[];
  total_count: number;
  retrieved_at: string;
  error?: string;
}

export interface ChannelsResponse {
  ok: boolean;
  channels: UnifiedChannel[];
  total_count: number;
  retrieved_at: string;
  error?: string;
}

export interface MessagesResponse {
  ok: boolean;
  messages: UnifiedMessage[];
  channel_id: string;
  team_id?: string;
  workspace_id?: string;
  total_count: number;
  retrieved_at: string;
  has_more?: boolean;
  next_cursor?: string;
  error?: string;
}

export interface SendMessageRequest {
  content: string;
  channel_id: string;
  team_id?: string;
  workspace_id?: string;
  service?: 'slack' | 'teams';
}

export interface SendMessageResponse {
  ok: boolean;
  message_id?: string;
  channel_id: string;
  team_id?: string;
  workspace_id?: string;
  content: string;
  sent_at?: string;
  status?: string;
  error?: string;
}

export interface InstallRequest {
  user_id: string;
  service: 'slack' | 'teams';
  environment?: 'mock' | 'real';
}

export interface InstallResponse {
  ok: boolean;
  install_url?: string;
  state?: string;
  user_id: string;
  expires_in?: number;
  message?: string;
  error?: string;
  installation_state?: string;
}

// Real-time Events
export interface RealTimeEvent {
  type: 'message' | 'channel' | 'workspace' | 'reaction' | 'typing' | 'presence';
  service: 'slack' | 'teams';
  workspace_id?: string;
  team_id?: string;
  channel_id?: string;
  user_id?: string;
  timestamp: string;
  data: any;
}

export interface MessageEvent extends RealTimeEvent {
  type: 'message';
  data: {
    message: UnifiedMessage;
    event_type: 'created' | 'updated' | 'deleted';
    thread_parent?: string;
  };
}

export interface ChannelEvent extends RealTimeEvent {
  type: 'channel';
  data: {
    channel: UnifiedChannel;
    event_type: 'created' | 'updated' | 'deleted';
  };
}

export interface PresenceEvent extends RealTimeEvent {
  type: 'presence';
  data: {
    user_id: string;
    presence: 'active' | 'away' | 'offline' | 'busy';
    last_seen?: string;
  };
}

// Configuration Types
export interface ServiceConfiguration {
  service: 'slack' | 'teams';
  implementation: 'mock' | 'real';
  credentials: {
    client_id?: string;
    client_secret?: string;
    bot_token?: string;
    access_token?: string;
    refresh_token?: string;
    tenant_id?: string;
  };
  settings: {
    rate_limit: number;
    timeout: number;
    retry_attempts: number;
    enable_webhooks: boolean;
    enable_real_time: boolean;
    cache_ttl: number;
  };
  mock_data?: {
    workspaces_count: number;
    channels_per_workspace: number;
    messages_per_channel: number;
    seed: number;
  };
}

// Statistics and Monitoring
export interface ServiceStatistics {
  service: 'slack' | 'teams';
  implementation: 'mock' | 'real';
  timestamp: string;
  metrics: {
    workspaces_count: number;
    channels_count: number;
    messages_count: number;
    api_calls_today: number;
    api_errors_today: number;
    average_response_time: number;
    uptime_percentage: number;
  };
  health: ServiceHealth;
}

export interface UnifiedStatistics {
  timestamp: string;
  services: {
    slack: ServiceStatistics;
    teams: ServiceStatistics;
  };
  total_metrics: {
    total_workspaces: number;
    total_channels: number;
    total_messages: number;
    total_api_calls: number;
    total_api_errors: number;
  };
}

// Error Types
export interface ServiceError {
  service: 'slack' | 'teams' | 'unified';
  operation: string;
  code: string;
  message: string;
  details?: any;
  timestamp: string;
}

export interface OAuthError {
  error: string;
  error_description?: string;
  state?: string;
  timestamp: string;
  service: 'slack' | 'teams';
}

// Export all types for convenience
export type {
  // Base types
  ServiceHealth,
  ServiceImplementation,
  UnifiedServicesStatus,
  
  // Message types
  UnifiedMessage,
  SlackMessage,
  TeamsMessage,
  UnifiedAttachment,
  UnifiedMention,
  UnifiedReactions,
  
  // Workspace types
  UnifiedWorkspace,
  SlackWorkspace,
  TeamsWorkspace,
  
  // Channel types
  UnifiedChannel,
  SlackChannel,
  TeamsChannel,
  
  // API types
  ServiceSwitchRequest,
  ServiceSwitchResponse,
  WorkspacesResponse,
  ChannelsResponse,
  MessagesResponse,
  SendMessageRequest,
  SendMessageResponse,
  InstallRequest,
  InstallResponse,
  
  // Real-time types
  RealTimeEvent,
  MessageEvent,
  ChannelEvent,
  PresenceEvent,
  
  // Configuration types
  ServiceConfiguration,
  
  // Statistics types
  ServiceStatistics,
  UnifiedStatistics,
  
  // Error types
  ServiceError,
  OAuthError
};