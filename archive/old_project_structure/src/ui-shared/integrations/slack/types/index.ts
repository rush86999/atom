/**
 * ATOM Slack Integration - TypeScript Types
 * Messaging → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomMessagingConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// Slack API Types
export interface SlackUser {
  id: string;
  team_id: string;
  name: string;
  real_name: string;
  display_name: string;
  email?: string;
  profile: SlackUserProfile;
  is_bot: boolean;
  is_app_user: boolean;
  is_restricted: boolean;
  is_ultra_restricted: boolean;
  tz?: string;
  tz_label?: string;
  tz_offset?: number;
  updated: number;
  deleted?: boolean;
}

export interface SlackUserProfile {
  avatar_hash?: string;
  display_name?: string;
  display_name_normalized?: string;
  email?: string;
  first_name?: string;
  image_24?: string;
  image_32?: string;
  image_48?: string;
  image_72?: string;
  image_192?: string;
  image_512?: string;
  image_1024?: string;
  is_custom_image?: boolean;
  last_name?: string;
  phone?: string;
  pronouns?: string;
  real_name?: string;
  real_name_normalized?: string;
  status_emoji?: string;
  status_expiration?: number;
  status_text?: string;
  status_text_canonical?: string;
  title?: string;
}

export interface SlackChannel {
  id: string;
  name: string;
  is_channel: boolean;
  is_group: boolean;
  is_im: boolean;
  is_mpim: boolean;
  is_private: boolean;
  is_archived: boolean;
  is_general: boolean;
  name_normalized: string;
  parent_conversation?: string;
  creator?: string;
  last_read?: string;
  latest?: SlackMessage;
  unread_count?: number;
  unread_count_display?: number;
  members?: string[];
  topic: SlackTopic;
  purpose: SlackPurpose;
  previous_names: string[];
  num_members?: number;
}

export interface SlackTopic {
  value: string;
  creator: string;
  last_set: number;
}

export interface SlackPurpose {
  value: string;
  creator: string;
  last_set: number;
}

export interface SlackMessage {
  type: 'message';
  subtype?: string;
  team: string;
  channel: string;
  user: string;
  ts: string;
  thread_ts?: string;
  parent_user_id?: string;
  text: string;
  blocks?: SlackBlock[];
  files?: SlackFile[];
  upload?: boolean;
  display_as_bot?: boolean;
  reply_count?: number;
  replies?: SlackMessage[];
  reply_users?: string[];
  reply_users_count?: number;
  latest_reply?: string;
  last_read?: string;
  subscribed: boolean;
  unread_count?: number;
  mentions?: string[];
}

export interface SlackBlock {
  type: string;
  block_id: string;
  text?: SlackText;
  elements?: SlackElement[];
  fields?: SlackField[];
}

export interface SlackText {
  type: 'plain_text' | 'mrkdwn';
  text: string;
  emoji?: boolean;
  verbatim?: boolean;
}

export interface SlackElement {
  type: string;
  text?: SlackText;
  elements?: SlackElement[];
  fallback?: string;
  image_url?: string;
  alt_text?: string;
  title?: SlackText;
}

export interface SlackField {
  type: string;
  text?: SlackText;
  short?: boolean;
}

export interface SlackFile {
  id: string;
  created: number;
  timestamp: number;
  name: string;
  title?: string;
  mimetype?: string;
  filetype?: string;
  pretty_type?: string;
  user: string;
  mode: string;
  editable: boolean;
  size: number;
  is_public: boolean;
  public_url_shared: boolean;
  display_as_bot?: boolean;
  username?: string;
  url_private: string;
  url_private_download: string;
  permalink?: string;
  permalink_public?: string;
  thumb_64?: string;
  thumb_80?: string;
  thumb_160?: string;
  thumb_360?: string;
  thumb_480?: string;
  thumb_720?: string;
  thumb_960?: string;
  thumb_1024?: string;
  original_h?: number;
  original_w?: number;
  thumb_tiny?: string;
  external_id?: string;
  external_url?: string;
  has_rich_preview?: boolean;
  preview?: SlackPreview;
}

export interface SlackPreview {
  type: string;
  can_edit?: boolean;
  original_url?: string;
  can_remove?: boolean;
  page_link?: string;
}

// Slack Configuration Types
export interface SlackConfig extends AtomMessagingConfig {
  // API Configuration
  apiBaseUrl: string;
  scopes: string[];
  
  // Slack-specific settings
  teamId?: string;
  botToken?: string;
  userToken?: string;
  
  // Message Discovery
  includeBotMessages: boolean;
  includeReplies: boolean;
  includeThreads: boolean;
  maxMessageAge: number; // days
  
  // Channel Filtering
  channelTypes: string[];
  excludeArchivedChannels: boolean;
  includePrivateChannels: boolean;
  includeDMs: boolean;
  includeGroupDMs: boolean;
  
  // File Processing
  includeFileAttachments: boolean;
  downloadFiles: boolean;
  maxFileSize: number;
  
  // Rate Limiting
  apiCallsPerMinute: number;
  useSlackEvents: boolean;
  eventRetentionPolicy: number; // days
  
  // Platform-specific
  tauriCommands?: {
    downloadFile: string;
    subscribeToEvents: string;
  };
}

// Enhanced Types
export interface SlackMessageEnhanced extends SlackMessage {
  source: 'slack';
  discoveredAt: string;
  processedAt?: string;
  textExtracted?: boolean;
  filesProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  user_info?: SlackUser;
  channel_info?: SlackChannel;
  thread_info?: SlackThreadInfo;
  attachments_info?: SlackFile[];
  mention_info?: SlackMentionInfo;
}

export interface SlackThreadInfo {
  thread_ts: string;
  reply_count: number;
  replies: SlackMessage[];
  last_reply_ts: string;
  participants: string[];
}

export interface SlackMentionInfo {
  users: string[];
  channels: string[];
  user_groups: string[];
  everyone: boolean;
  here: boolean;
}

// Component Props
export interface AtomSlackManagerProps extends AtomIntegrationProps<SlackConfig> {
  // Slack-specific events
  onChannelCreated?: (channel: SlackChannel) => void;
  onChannelDeleted?: (channelId: string) => void;
  onMessageReceived?: (message: SlackMessage) => void;
  onMessageUpdated?: (message: SlackMessage) => void;
  onMessageDeleted?: (message: { channel: string; ts: string }) => void;
  onFileShared?: (file: SlackFile) => void;
  onUserJoined?: (user: SlackUser, channel: string) => void;
  onUserLeft?: (user: SlackUser, channel: string) => void;
}

export interface AtomSlackDataSourceProps extends AtomIntegrationProps<SlackConfig, AtomSlackIngestionConfig> {
  // Ingestion-specific events
  onMessageDiscovered?: (message: SlackMessageEnhanced) => void;
  onChannelDiscovered?: (channel: SlackChannel) => void;
  onUserDiscovered?: (user: SlackUser) => void;
  onFileDiscovered?: (file: SlackFile) => void;
}

// State Types
export interface AtomSlackState extends AtomIntegrationState {
  messages: SlackMessage[];
  channels: SlackChannel[];
  users: SlackUser[];
  currentChannel?: SlackChannel;
  selectedItems: (SlackMessage | SlackChannel | SlackUser)[];
  searchResults: SlackMessage[];
  sortBy: SlackSortField;
  sortOrder: SlackSortOrder;
  viewMode: 'grid' | 'list' | 'compact';
  filters: SlackFilters;
}

export interface AtomSlackDataSourceState extends AtomIntegrationState {
  discoveredMessages: SlackMessageEnhanced[];
  discoveredChannels: SlackChannel[];
  discoveredUsers: SlackUser[];
  discoveredFiles: SlackFile[];
  ingestionQueue: SlackMessageEnhanced[];
  processingIngestion: boolean;
  stats: {
    totalMessages: number;
    totalChannels: number;
    totalUsers: number;
    totalFiles: number;
    ingestedMessages: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataSize: number;
  };
}

// Ingestion Configuration
export interface AtomSlackIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'slack';
  
  // API Configuration
  apiBaseUrl: string;
  scopes: string[];
  teamId?: string;
  
  // Message Discovery
  messageTypes: string[];
  channels: string[];
  users: string[];
  dateRange: {
    start: Date;
    end: Date;
  };
  includeBotMessages: boolean;
  includeReplies: boolean;
  includeThreads: boolean;
  maxMessageAge: number;
  
  // Channel Filtering
  channelTypes: string[];
  excludeArchivedChannels: boolean;
  includePrivateChannels: boolean;
  includeDMs: boolean;
  includeGroupDMs: boolean;
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Processing
  extractMentions: boolean;
  extractLinks: boolean;
  extractAttachments: boolean;
  extractEmojis: boolean;
  parseMarkdown: boolean;
  includeUserContext: boolean;
  includeChannelContext: boolean;
  
  // File Processing
  includeFileAttachments: boolean;
  downloadFiles: boolean;
  maxFileSize: number;
  
  // Pipeline Integration
  pipelineConfig: {
    targetTable: string;
    embeddingModel: string;
    embeddingDimension: number;
    indexType: string;
    numPartitions: number;
  };
}

// API Types
export interface AtomSlackAPI extends AtomIntegrationAPI<SlackMessage, SlackConfig> {
  // Authentication
  testAuth: () => Promise<SlackAuthResponse>;
  
  // User Operations
  getUsers: (cursor?: string) => Promise<SlackUserListResponse>;
  getUser: (userId: string) => Promise<SlackUser>;
  
  // Channel Operations
  getChannels: (cursor?: string) => Promise<SlackChannelListResponse>;
  getChannel: (channelId: string) => Promise<SlackChannel>;
  getChannelHistory: (channelId: string, options?: SlackHistoryOptions) => Promise<SlackHistoryResponse>;
  
  // Message Operations
  getMessage: (channelId: string, messageId: string) => Promise<SlackMessage>;
  getThreadReplies: (channelId: string, threadTs: string) => Promise<SlackThreadResponse>;
  searchMessages: (query: string, options?: SlackSearchOptions) => Promise<SlackSearchResponse>;
  
  // File Operations
  getFiles: (options?: SlackFilesOptions) => Promise<SlackFilesResponse>;
  getFile: (fileId: string) => Promise<SlackFile>;
  downloadFile: (fileId: string) => Promise<Blob>;
  
  // Real-time Events
  subscribeToEvents: (eventTypes: string[], channelId?: string) => Promise<SlackEventSubscription>;
  unsubscribeFromEvents: (eventSubscriptionId: string) => Promise<void>;
  
  // Webhooks
  createWebhook: (requestUrl: string) => Promise<SlackWebhook>;
  deleteWebhook: (webhookId: string) => Promise<void>;
}

export interface SlackAuthResponse {
  ok: boolean;
  user: string;
  user_id: string;
  team: string;
  team_id: string;
  bot_id?: string;
  url?: string;
  error?: string;
}

export interface SlackUserListResponse {
  ok: boolean;
  members: SlackUser[];
  cache_ts: number;
  response_metadata?: {
    next_cursor?: string;
  };
}

export interface SlackChannelListResponse {
  ok: boolean;
  channels: SlackChannel[];
  response_metadata?: {
    next_cursor?: string;
  };
}

export interface SlackHistoryResponse {
  ok: boolean;
  messages: SlackMessage[];
  has_more: boolean;
  latest: string;
  oldest: string;
}

export interface SlackHistoryOptions {
  latest?: string;
  oldest?: string;
  inclusive?: boolean;
  count?: number;
  unreads?: boolean;
}

export interface SlackThreadResponse {
  ok: boolean;
  messages: SlackMessage[];
  has_more: boolean;
}

export interface SlackSearchResponse {
  ok: boolean;
  messages: SlackMessage[];
  files?: SlackFile[];
  posts?: any[];
  query: string;
  total: number;
}

export interface SlackSearchOptions {
  sort?: 'score' | 'timestamp';
  sort_dir?: 'asc' | 'desc';
  highlight?: boolean;
  count?: number;
  page?: number;
}

export interface SlackFilesOptions {
  user?: string;
  channel?: string;
  ts_from?: string;
  ts_to?: string;
  types?: string[];
  count?: number;
  page?: number;
}

export interface SlackFilesResponse {
  ok: boolean;
  files: SlackFile[];
  paging: {
    count: number;
    total: number;
    page: number;
    pages: number;
  };
}

export interface SlackEventSubscription {
  subscriptionId: string;
  eventTypes: string[];
  channelId?: string;
  webhookUrl: string;
  created: Date;
}

export interface SlackWebhook {
  id: string;
  team_id: string;
  channel_id: string;
  configuration_url: string;
  url: string;
  created_by: string;
  created_at: number;
}

// Hook Types
export interface AtomSlackHookReturn extends AtomIntegrationHookReturn<SlackMessage> {
  state: AtomSlackState;
  api: AtomSlackAPI;
  actions: AtomSlackActions;
  config: SlackConfig;
}

export interface AtomSlackDataSourceHookReturn extends AtomIntegrationHookReturn<SlackMessageEnhanced> {
  state: AtomSlackDataSourceState;
  api: AtomSlackAPI;
  actions: AtomSlackDataSourceActions;
  config: AtomSlackIngestionConfig;
}

// Actions Types
export interface AtomSlackActions {
  // Message Actions
  sendMessage: (channelId: string, text: string, blocks?: SlackBlock[]) => Promise<SlackMessage>;
  editMessage: (channelId: string, messageId: string, text: string) => Promise<SlackMessage>;
  deleteMessage: (channelId: string, messageId: string) => Promise<void>;
  reactToMessage: (channelId: string, messageId: string, emoji: string) => Promise<void>;
  
  // Channel Actions
  createChannel: (name: string, isPrivate?: boolean) => Promise<SlackChannel>;
  joinChannel: (channelId: string) => Promise<void>;
  leaveChannel: (channelId: string) => Promise<void>;
  
  // Search Actions
  searchMessages: (query: string, options?: SlackSearchOptions) => Promise<SlackSearchResponse>;
  searchUsers: (query: string) => Promise<SlackUser[]>;
  searchChannels: (query: string) => Promise<SlackChannel[]>;
  
  // UI Actions
  selectItems: (items: (SlackMessage | SlackChannel | SlackUser)[]) => void;
  sortBy: (field: SlackSortField, order: SlackSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'compact') => void;
  setFilters: (filters: SlackFilters) => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface AtomSlackDataSourceActions {
  // Discovery Actions
  discoverMessages: (channelIds?: string[], dateRange?: { start: Date; end: Date }) => Promise<SlackMessageEnhanced[]>;
  discoverChannels: () => Promise<SlackChannel[]>;
  discoverUsers: () => Promise<SlackUser[]>;
  discoverFiles: () => Promise<SlackFile[]>;
  
  // Ingestion Actions
  ingestMessages: (messages: SlackMessageEnhanced[]) => Promise<void>;
  ingestChannel: (channelId: string) => Promise<void>;
  
  // Sync Actions
  syncMessages: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Filters Type
export interface SlackFilters {
  channels: string[];
  users: string[];
  dateRange?: {
    start: Date;
    end: Date;
  };
  messageTypes: string[];
  hasFiles: boolean;
  hasReplies: boolean;
  isThread: boolean;
}

// Sort Types
export type SlackSortField = 'timestamp' | 'user' | 'channel' | 'replies' | 'reactions' | 'text';
export type SlackSortOrder = 'asc' | 'desc';

// Error Types
export class AtomSlackError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;
  public statusCode?: number;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string, statusCode?: number) {
    super(message);
    this.name = 'AtomSlackError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

// Constants
export const slackConfigDefaults: Partial<SlackConfig> = {
  apiBaseUrl: 'https://slack.com/api',
  scopes: [
    'channels:read',
    'channels:history',
    'users:read',
    'files:read',
    'search:read'
  ],
  includeBotMessages: false,
  includeReplies: true,
  includeThreads: true,
  maxMessageAge: 365, // 1 year
  channelTypes: ['public_channel'],
  excludeArchivedChannels: true,
  includePrivateChannels: false,
  includeDMs: false,
  includeGroupDMs: false,
  includeFileAttachments: true,
  downloadFiles: true,
  maxFileSize: 50 * 1024 * 1024, // 50MB
  apiCallsPerMinute: 60,
  useSlackEvents: true,
  eventRetentionPolicy: 90 // 90 days
};

export const slackIngestionConfigDefaults: Partial<AtomSlackIngestionConfig> = {
  sourceId: 'slack-integration',
  sourceName: 'Slack',
  sourceType: 'slack',
  apiBaseUrl: 'https://slack.com/api',
  scopes: [
    'channels:read',
    'channels:history',
    'users:read',
    'files:read',
    'search:read'
  ],
  messageTypes: ['message', 'file_share', 'message_changed'],
  channels: [],
  users: [],
  dateRange: {
    start: new Date(Date.now() - 30 * 24 * 3600 * 1000), // 30 days ago
    end: new Date()
  },
  includeBotMessages: false,
  includeReplies: true,
  includeThreads: true,
  maxMessageAge: 365,
  channelTypes: ['public_channel'],
  excludeArchivedChannels: true,
  includePrivateChannels: false,
  includeDMs: false,
  includeGroupDMs: false,
  autoIngest: true,
  ingestInterval: 600000, // 10 minutes
  batchSize: 100,
  maxConcurrentIngestions: 5,
  extractMentions: true,
  extractLinks: true,
  extractAttachments: true,
  extractEmojis: false,
  parseMarkdown: true,
  includeUserContext: true,
  includeChannelContext: true,
  includeFileAttachments: true,
  downloadFiles: true,
  maxFileSize: 50 * 1024 * 1024, // 50MB
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const slackSearchDefaults: SlackSearchOptions = {
  sort: 'timestamp',
  sort_dir: 'desc',
  count: 100
};

export const slackSortFields: SlackSortField[] = ['timestamp', 'user', 'channel', 'replies', 'reactions', 'text'];
export const slackSortOrders: SlackSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomMessagingConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';