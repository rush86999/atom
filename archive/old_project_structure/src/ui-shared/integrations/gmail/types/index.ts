/**
 * ATOM Gmail Integration - TypeScript Types
 * Email → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomEmailConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// Gmail API Types
export interface GmailMessage {
  id: string;
  threadId: string;
  labelIds: string[];
  snippet: string;
  sizeEstimate: number;
  historyId: string;
  internalDate: string;
  payload: GmailMessagePayload;
  raw?: string;
}

export interface GmailMessagePayload {
  partId?: string;
  mimeType: string;
  filename: string;
  headers: GmailHeader[];
  body: GmailMessageBody;
  parts?: GmailMessagePayload[];
}

export interface GmailHeader {
  name: string;
  value: string;
}

export interface GmailMessageBody {
  attachmentId?: string;
  size?: number;
  data?: string;
}

export interface GmailThread {
  id: string;
  snippet: string;
  historyId: string;
  messages: GmailMessage[];
}

export interface GmailLabel {
  id: string;
  name: string;
  messageListVisibility: 'show' | 'hide';
  labelListVisibility: 'labelShow' | 'labelHide';
  type: 'system' | 'user';
  messagesTotal: number;
  messagesUnread: number;
  threadsTotal: number;
  threadsUnread: number;
  color?: GmailLabelColor;
}

export interface GmailLabelColor {
  backgroundColor: string;
  textColor: string;
}

export interface GmailAttachment {
  messageId: string;
  attachmentId: string;
  filename: string;
  mimeType: string;
  size: number;
  data?: string;
  url?: string;
}

export interface GmailSearchResponse {
  messages: GmailMessage[];
  nextPageToken?: string;
  resultSizeEstimate: number;
}

export interface GmailHistoryResponse {
  historyId: string;
  history: GmailHistory[];
  nextPageToken?: string;
}

export interface GmailHistory {
  id: string;
  messages: GmailMessage[];
  messagesAdded?: GmailMessage[];
  messagesDeleted?: GmailMessage[];
  labelsAdded?: GmailLabelChange[];
  labelsRemoved?: GmailLabelChange[];
}

export interface GmailLabelChange {
  messageId: string;
  labelIds: string[];
}

// Gmail Configuration Types
export interface GmailConfig extends AtomEmailConfig {
  // API Configuration
  apiBaseUrl: string;
  scopes: string[];
  
  // Gmail-specific settings
  userId: string;
  includeSpam: boolean;
  includeTrash: boolean;
  includeDrafts: boolean;
  
  // Message Processing
  includeHeaders: boolean;
  includeBody: boolean;
  includeAttachments: boolean;
  parseHtml: boolean;
  extractCalendar: boolean;
  extractContacts: boolean;
  maxAttachmentSize: number;
  
  // Label Filtering
  includedLabels: string[];
  excludedLabels: string[];
  
  // Search Filtering
  searchQuery: string;
  maxResults: number;
  
  // Rate Limiting
  apiCallsPerSecond: number;
  useBatchRequests: boolean;
  
  // Platform-specific
  tauriCommands?: {
    downloadAttachment: string;
    exportEmail: string;
  };
}

// Enhanced Types
export interface GmailMessageEnhanced extends GmailMessage {
  source: 'gmail';
  discoveredAt: string;
  processedAt?: string;
  headersExtracted?: boolean;
  bodyExtracted?: boolean;
  attachmentsProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  threadInfo?: GmailThreadInfo;
  headerInfo?: GmailHeaderInfo;
  attachmentInfo?: GmailAttachmentInfo;
  contactInfo?: GmailContactInfo;
  calendarInfo?: GmailCalendarInfo;
}

export interface GmailThreadInfo {
  threadId: string;
  messageCount: number;
  participants: string[];
  subject: string;
  dateRange: {
    start: string;
    end: string;
  };
}

export interface GmailHeaderInfo {
  from: string;
  to: string[];
  cc: string[];
  bcc: string[];
  subject: string;
  date: string;
  messageId: string;
  inReplyTo?: string;
  references?: string[];
  listId?: string;
  priority?: string;
  importance?: string;
}

export interface GmailAttachmentInfo {
  totalAttachments: number;
  totalSize: number;
  processedAttachments: GmailAttachment[];
  fileTypes: string[];
  hasImages: boolean;
  hasDocuments: boolean;
  hasArchives: boolean;
}

export interface GmailContactInfo {
  senders: string[];
  recipients: string[];
  ccRecipients: string[];
  bccRecipients: string[];
  contacts: GmailContact[];
}

export interface GmailContact {
  email: string;
  name?: string;
  frequency: number;
  lastContact: string;
}

export interface GmailCalendarInfo {
  hasCalendarEvent: boolean;
  events: GmailCalendarEvent[];
  invitations: GmailCalendarEvent[];
}

export interface GmailCalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  location?: string;
  organizer?: string;
  attendees?: string[];
  status: string;
}

// Component Props
export interface AtomGmailManagerProps extends AtomIntegrationProps<GmailConfig> {
  // Gmail-specific events
  onMessageReceived?: (message: GmailMessage) => void;
  onMessageUpdated?: (message: GmailMessage) => void;
  onMessageDeleted?: (messageId: string) => void;
  onLabelCreated?: (label: GmailLabel) => void;
  onLabelUpdated?: (label: GmailLabel) => void;
  onAttachmentReceived?: (attachment: GmailAttachment) => void;
  onThreadUpdated?: (thread: GmailThread) => void;
}

export interface AtomGmailDataSourceProps extends AtomIntegrationProps<GmailConfig, AtomGmailIngestionConfig> {
  // Ingestion-specific events
  onMessageDiscovered?: (message: GmailMessageEnhanced) => void;
  onThreadDiscovered?: (thread: GmailThread) => void;
  onLabelDiscovered?: (label: GmailLabel) => void;
  onAttachmentDiscovered?: (attachment: GmailAttachment) => void;
  onContactDiscovered?: (contact: GmailContact) => void;
}

// State Types
export interface AtomGmailState extends AtomIntegrationState {
  messages: GmailMessage[];
  threads: GmailThread[];
  labels: GmailLabel[];
  attachments: GmailAttachment[];
  currentLabel?: GmailLabel;
  selectedItems: (GmailMessage | GmailThread | GmailLabel)[];
  searchResults: GmailMessage[];
  sortBy: GmailSortField;
  sortOrder: GmailSortOrder;
  viewMode: 'grid' | 'list' | 'compact';
  filters: GmailFilters;
}

export interface AtomGmailDataSourceState extends AtomIntegrationState {
  discoveredMessages: GmailMessageEnhanced[];
  discoveredThreads: GmailThread[];
  discoveredLabels: GmailLabel[];
  discoveredAttachments: GmailAttachment[];
  discoveredContacts: GmailContact[];
  ingestionQueue: GmailMessageEnhanced[];
  processingIngestion: boolean;
  stats: {
    totalMessages: number;
    totalThreads: number;
    totalLabels: number;
    totalAttachments: number;
    totalContacts: number;
    ingestedMessages: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataSize: number;
  };
}

// Ingestion Configuration
export interface AtomGmailIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'gmail';
  
  // API Configuration
  apiBaseUrl: string;
  scopes: string[];
  userId: string;
  
  // Message Discovery
  folders: string[];
  dateRange: {
    start: Date;
    end: Date;
  };
  includeSpam: boolean;
  includeTrash: boolean;
  includeDrafts: boolean;
  
  // Label Filtering
  includedLabels: string[];
  excludedLabels: string[];
  
  // Search Filtering
  searchQuery: string;
  maxResults: number;
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Processing
  extractHeaders: boolean;
  extractBody: boolean;
  extractAttachments: boolean;
  parseHtml: boolean;
  extractCalendar: boolean;
  extractContacts: boolean;
  maxAttachmentSize: number;
  supportedAttachmentTypes: string[];
  
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
export interface AtomGmailAPI extends AtomIntegrationAPI<GmailMessage, GmailConfig> {
  // Message Operations
  getMessages: (labelIds?: string[], pageToken?: string, maxResults?: number) => Promise<GmailSearchResponse>;
  getMessage: (messageId: string, format?: 'full' | 'raw' | 'metadata' | 'minimal') => Promise<GmailMessage>;
  getThread: (threadId: string) => Promise<GmailThread>;
  sendMessage: (message: GmailSendMessageRequest) => Promise<GmailMessage>;
  deleteMessage: (messageId: string) => Promise<void>;
  
  // Label Operations
  getLabels: () => Promise<GmailLabel[]>;
  createLabel: (label: GmailCreateLabelRequest) => Promise<GmailLabel>;
  updateLabel: (labelId: string, label: GmailUpdateLabelRequest) => Promise<GmailLabel>;
  deleteLabel: (labelId: string) => Promise<void>;
  
  // Attachment Operations
  getAttachment: (messageId: string, attachmentId: string) => Promise<GmailAttachment>;
  downloadAttachment: (messageId: string, attachmentId: string) => Promise<Blob>;
  
  // Search Operations
  search: (query: string, options?: GmailSearchOptions) => Promise<GmailSearchResponse>;
  
  // Sync Operations
  getHistory: (historyId?: string, labelIds?: string[]) => Promise<GmailHistoryResponse>;
  
  // Batch Operations
  batchGet: (resourceRequests: GmailBatchRequest[]) => Promise<GmailBatchResponse>;
  
  // Profile Operations
  getProfile: () => Promise<GmailProfile>;
}

export interface GmailSendMessageRequest {
  raw?: string;
  threadId?: string;
  subject?: string;
  to?: string[];
  cc?: string[];
  bcc?: string[];
  htmlBody?: string;
  textBody?: string;
  attachments?: GmailAttachment[];
}

export interface GmailCreateLabelRequest {
  name: string;
  messageListVisibility?: 'show' | 'hide';
  labelListVisibility?: 'labelShow' | 'labelHide';
  color?: GmailLabelColor;
}

export interface GmailUpdateLabelRequest {
  name?: string;
  messageListVisibility?: 'show' | 'hide';
  labelListVisibility?: 'labelShow' | 'labelHide';
  color?: GmailLabelColor;
}

export interface GmailSearchOptions {
  maxResults?: number;
  pageToken?: string;
  includeSpamTrash?: boolean;
  labelIds?: string[];
  userId?: string;
}

export interface GmailBatchRequest {
  method: string;
  url: string;
  headers?: Record<string, string>;
  body?: any;
}

export interface GmailBatchResponse {
  responses: GmailBatchResponseItem[];
  batchId?: string;
}

export interface GmailBatchResponseItem {
  status: number;
  statusText: string;
  body?: any;
}

export interface GmailProfile {
  emailAddress: string;
  messagesTotal: number;
  threadsTotal: number;
  historyId: string;
}

// Hook Types
export interface AtomGmailHookReturn extends AtomIntegrationHookReturn<GmailMessage> {
  state: AtomGmailState;
  api: AtomGmailAPI;
  actions: AtomGmailActions;
  config: GmailConfig;
}

export interface AtomGmailDataSourceHookReturn extends AtomIntegrationHookReturn<GmailMessageEnhanced> {
  state: AtomGmailDataSourceState;
  api: AtomGmailAPI;
  actions: AtomGmailDataSourceActions;
  config: AtomGmailIngestionConfig;
}

// Actions Types
export interface AtomGmailActions {
  // Message Actions
  sendMessage: (message: GmailSendMessageRequest) => Promise<GmailMessage>;
  deleteMessages: (messageIds: string[]) => Promise<void>;
  moveMessages: (messageIds: string[], labelIds: string[]) => Promise<void>;
  markMessagesAsRead: (messageIds: string[]) => Promise<void>;
  archiveMessages: (messageIds: string[]) => Promise<void>;
  
  // Label Actions
  createLabel: (label: GmailCreateLabelRequest) => Promise<GmailLabel>;
  updateLabel: (labelId: string, label: GmailUpdateLabelRequest) => Promise<GmailLabel>;
  deleteLabel: (labelId: string) => Promise<void>;
  
  // Navigation Actions
  navigateToLabel: (label: GmailLabel) => void;
  
  // Search Actions
  search: (query: string, options?: GmailSearchOptions) => Promise<GmailSearchResponse>;
  
  // UI Actions
  selectItems: (items: (GmailMessage | GmailThread | GmailLabel)[]) => void;
  sortBy: (field: GmailSortField, order: GmailSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'compact') => void;
  setFilters: (filters: GmailFilters) => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface AtomGmailDataSourceActions {
  // Discovery Actions
  discoverMessages: (labelIds?: string[], dateRange?: { start: Date; end: Date }) => Promise<GmailMessageEnhanced[]>;
  discoverThreads: () => Promise<GmailThread[]>;
  discoverLabels: () => Promise<GmailLabel[]>;
  discoverAttachments: () => Promise<GmailAttachment[]>;
  discoverContacts: () => Promise<GmailContact[]>;
  
  // Ingestion Actions
  ingestMessages: (messages: GmailMessageEnhanced[]) => Promise<void>;
  ingestLabel: (labelId: string) => Promise<void>;
  
  // Sync Actions
  syncMessages: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Filters Type
export interface GmailFilters {
  labels: string[];
  dateRange?: {
    start: Date;
    end: Date;
  };
  hasAttachments: boolean;
  isUnread: boolean;
  isImportant: boolean;
  isStarred: boolean;
  searchQuery?: string;
}

// Sort Types
export type GmailSortField = 'date' | 'subject' | 'from' | 'to' | 'size' | 'labels';
export type GmailSortOrder = 'asc' | 'desc';

// Error Types
export class AtomGmailError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;
  public statusCode?: number;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string, statusCode?: number) {
    super(message);
    this.name = 'AtomGmailError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

// Constants
export const gmailConfigDefaults: Partial<GmailConfig> = {
  apiBaseUrl: 'https://gmail.googleapis.com/gmail/v1',
  scopes: [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.modify'
  ],
  userId: 'me',
  includeSpam: false,
  includeTrash: false,
  includeDrafts: false,
  includeHeaders: true,
  includeBody: true,
  includeAttachments: true,
  parseHtml: true,
  extractCalendar: false,
  extractContacts: true,
  maxAttachmentSize: 25 * 1024 * 1024, // 25MB (Gmail limit)
  includedLabels: ['INBOX', 'SENT'],
  excludedLabels: ['SPAM', 'TRASH'],
  searchQuery: '',
  maxResults: 100,
  apiCallsPerSecond: 100,
  useBatchRequests: true
};

export const gmailIngestionConfigDefaults: Partial<AtomGmailIngestionConfig> = {
  sourceId: 'gmail-integration',
  sourceName: 'Gmail',
  sourceType: 'gmail',
  apiBaseUrl: 'https://gmail.googleapis.com/gmail/v1',
  scopes: [
    'https://www.googleapis.com/auth/gmail.readonly'
  ],
  userId: 'me',
  folders: ['INBOX', 'SENT'],
  dateRange: {
    start: new Date(Date.now() - 30 * 24 * 3600 * 1000), // 30 days ago
    end: new Date()
  },
  includeSpam: false,
  includeTrash: false,
  includeDrafts: false,
  includedLabels: ['INBOX', 'SENT'],
  excludedLabels: ['SPAM', 'TRASH'],
  searchQuery: '',
  maxResults: 1000,
  autoIngest: true,
  ingestInterval: 900000, // 15 minutes
  batchSize: 50,
  maxConcurrentIngestions: 3,
  extractHeaders: true,
  extractBody: true,
  extractAttachments: true,
  parseHtml: true,
  extractCalendar: false,
  extractContacts: true,
  maxAttachmentSize: 25 * 1024 * 1024, // 25MB
  supportedAttachmentTypes: [
    'text/plain',
    'text/html',
    'text/csv',
    'application/json',
    'application/xml',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg',
    'image/png',
    'image/gif',
    'application/zip',
    'application/x-rar-compressed'
  ],
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const gmailSearchDefaults: GmailSearchOptions = {
  maxResults: 100,
  includeSpamTrash: false,
  userId: 'me'
};

export const gmailSortFields: GmailSortField[] = ['date', 'subject', 'from', 'to', 'size', 'labels'];
export const gmailSortOrders: GmailSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomEmailConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';