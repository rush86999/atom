/**
 * ATOM Notion Integration - TypeScript Types
 * Documents → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// Notion API Types
export interface NotionPage {
  id: string;
  created_time: string;
  created_by: NotionUser;
  last_edited_time: string;
  last_edited_by: NotionUser;
  cover?: NotionFileObject;
  icon?: NotionFileObject;
  parent: NotionParent;
  archived: boolean;
  properties: NotionPageProperties;
  url: string;
  object: 'page';
}

export interface NotionDatabase {
  id: string;
  created_time: string;
  created_by: NotionUser;
  last_edited_time: string;
  last_edited_by: NotionUser;
  title: NotionPropertyItem[];
  description: NotionPropertyItem[];
  icon?: NotionFileObject;
  cover?: NotionFileObject;
  is_inline: boolean;
  parent: NotionParent;
  archived: boolean;
  properties: NotionDatabaseProperties;
  url: string;
  object: 'database';
}

export interface NotionBlock {
  id: string;
  created_time: string;
  created_by: NotionUser;
  last_edited_time: string;
  last_edited_by: NotionUser;
  has_children: boolean;
  archived: false;
  type: NotionBlockType;
  [key: string]: any; // Additional properties based on block type
}

export interface NotionUser {
  id: string;
  name?: string;
  avatar_url?: string;
  type: 'person' | 'bot';
  person?: {
    email: string;
  };
  bot?: {
    owner: NotionUser;
  };
  object: 'user';
}

export interface NotionParent {
  type: 'workspace' | 'database_id' | 'page_id';
  workspace: boolean;
  database_id?: string;
  page_id?: string;
}

export interface NotionFileObject {
  type: 'external' | 'file';
  external?: {
    url: string;
  };
  file?: {
    url: string;
    expiry_time: string;
  };
}

export interface NotionPageProperties {
  [key: string]: NotionPropertyItem;
}

export interface NotionDatabaseProperties {
  [key: string]: NotionProperty;
}

export interface NotionPropertyItem {
  id?: string;
  type: string;
  [key: string]: any; // Additional properties based on type
}

export interface NotionProperty {
  id: string;
  name: string;
  type: string;
  [key: string]: any; // Additional properties based on type
}

export type NotionBlockType = 
  | 'paragraph'
  | 'heading_1'
  | 'heading_2'
  | 'heading_3'
  | 'bulleted_list_item'
  | 'numbered_list_item'
  | 'to_do'
  | 'toggle'
  | 'child_page'
  | 'child_database'
  | 'embed'
  | 'image'
  | 'video'
  | 'file'
  | 'pdf'
  | 'bookmark'
  | 'callout'
  | 'quote'
  | 'column_list'
  | 'column'
  | 'template'
  | 'link_to_page'
  | 'table_of_contents'
  | 'breadcrumb'
  | 'synced_block'
  | 'divider'
  | 'backlink'
  | 'equation'
  | 'link_preview';

export interface NotionRichText {
  type: 'text';
  text: {
    content: string;
    link?: NotionLink;
  };
  annotations?: NotionAnnotations;
  plain_text: string;
  href?: string;
}

export interface NotionLink {
  url: string;
}

export interface NotionAnnotations {
  bold: boolean;
  italic: boolean;
  strikethrough: boolean;
  underline: boolean;
  code: boolean;
  color: string;
}

export interface NotionPageChildren {
  object: 'list';
  results: NotionBlock[];
  next_cursor?: string;
  has_more: boolean;
}

export interface NotionSearchResponse {
  object: 'list';
  results: (NotionPage | NotionDatabase)[];
  next_cursor?: string;
  has_more: boolean;
}

export interface NotionDatabaseQuery {
  filter?: NotionFilter;
  sorts?: NotionSort[];
  start_cursor?: string;
  page_size?: number;
}

export interface NotionFilter {
  and?: NotionFilter[];
  or?: NotionFilter[];
  property: string;
  [key: string]: any; // Additional properties based on filter type
}

export interface NotionSort {
  property: string;
  direction: 'ascending' | 'descending';
  timestamp?: 'created_time' | 'last_edited_time';
}

export interface NotionComment {
  id: string;
  parent: NotionParent;
  discussion_id: string;
  created_time: string;
  last_edited_time: string;
  created_by: NotionUser;
  rich_text: NotionRichText[];
  resolved: boolean;
  object: 'comment';
}

export interface NotionDiscussion {
  id: string;
  parent: NotionParent;
  comments: NotionComment[];
  resolved: boolean;
  object: 'discussion';
}

// Notion Configuration Types
export interface NotionConfig extends AtomFileStorageConfig {
  // API Configuration
  apiBaseUrl: string;
  version: string;
  
  // Notion-specific settings
  workspaceId?: string;
  includeArchivedPages: boolean;
  includeArchivedBlocks: boolean;
  
  // Page Processing
  includePageContent: boolean;
  includeBlockContent: boolean;
  includeComments: boolean;
  includeDatabasePages: boolean;
  maxPageDepth: number;
  
  // Content Processing
  extractMarkdown: boolean;
  extractPlainText: boolean;
  extractBlockTypes: NotionBlockType[];
  includeFormatting: boolean;
  
  // Search Settings
  searchQuery?: string;
  searchFilter?: NotionFilter;
  searchSort?: NotionSort[];
  
  // Rate Limiting
  apiCallsPerSecond: number;
  useBatchRequests: boolean;
  
  // Platform-specific
  tauriCommands?: {
    downloadFile: string;
    exportPage: string;
  };
}

// Enhanced Types
export interface NotionPageEnhanced extends NotionPage {
  source: 'notion';
  discoveredAt: string;
  processedAt?: string;
  contentExtracted?: boolean;
  blocksProcessed?: boolean;
  commentsProcessed?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  blockInfo?: NotionBlockInfo;
  commentInfo?: NotionCommentInfo;
  markdownContent?: string;
  plainTextContent?: string;
}

export interface NotionBlockInfo {
  totalBlocks: number;
  blockTypes: Record<NotionBlockType, number>;
  hasChildren: boolean;
  childPageIds: string[];
  imageCount: number;
  fileCount: number;
  linkCount: number;
}

export interface NotionCommentInfo {
  totalComments: number;
  totalDiscussions: number;
  resolvedComments: number;
  commentAuthors: string[];
}

// Component Props
export interface NotionManagerProps extends AtomIntegrationProps<NotionConfig> {
  // Notion-specific events
  onPageCreated?: (page: NotionPage) => void;
  onPageUpdated?: (page: NotionPage) => void;
  onPageDeleted?: (pageId: string) => void;
  onBlockAdded?: (block: NotionBlock, pageId: string) => void;
  onBlockUpdated?: (block: NotionBlock, pageId: string) => void;
  onBlockDeleted?: (blockId: string, pageId: string) => void;
  onCommentAdded?: (comment: NotionComment, pageId: string) => void;
}

export interface NotionDataSourceProps extends AtomIntegrationProps<NotionConfig, NotionIngestionConfig> {
  // Ingestion-specific events
  onPageDiscovered?: (page: NotionPageEnhanced) => void;
  onDatabaseDiscovered?: (database: NotionDatabase) => void;
  onBlockDiscovered?: (block: NotionBlock) => void;
  onCommentDiscovered?: (comment: NotionComment) => void;
}

// State Types
export interface NotionState extends AtomIntegrationState {
  pages: NotionPage[];
  databases: NotionDatabase[];
  blocks: NotionBlock[];
  comments: NotionComment[];
  currentPage?: NotionPage;
  selectedItems: (NotionPage | NotionDatabase | NotionBlock)[];
  searchResults: NotionSearchResponse;
  sortBy: NotionSortField;
  sortOrder: NotionSortOrder;
  viewMode: 'grid' | 'list' | 'tree';
  filters: NotionFilters;
}

export interface NotionDataSourceState extends AtomIntegrationState {
  discoveredPages: NotionPageEnhanced[];
  discoveredDatabases: NotionDatabase[];
  discoveredBlocks: NotionBlock[];
  discoveredComments: NotionComment[];
  ingestionQueue: NotionPageEnhanced[];
  processingIngestion: boolean;
  stats: {
    totalPages: number;
    totalDatabases: number;
    totalBlocks: number;
    totalComments: number;
    ingestedPages: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataSize: number;
  };
}

// Ingestion Configuration
export interface NotionIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'notion';
  
  // API Configuration
  apiBaseUrl: string;
  version: string;
  
  // Page Discovery
  includeArchivedPages: boolean;
  includeArchivedBlocks: boolean;
  dateRange?: {
    start: Date;
    end: Date;
  };
  maxPageDepth: number;
  
  // Database Filtering
  includeDatabases: boolean;
  excludedDatabaseIds: string[];
  includedDatabaseIds: string[];
  
  // Page Processing
  includePageContent: boolean;
  includeBlockContent: boolean;
  includeComments: boolean;
  includeDatabasePages: boolean;
  extractBlockTypes: NotionBlockType[];
  
  // Content Processing
  extractMarkdown: boolean;
  extractPlainText: boolean;
  includeFormatting: boolean;
  includeImages: boolean;
  includeFiles: boolean;
  maxFileSize: number;
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  batchSize: number;
  maxConcurrentIngestions: number;
  
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
export interface NotionAPI extends AtomIntegrationAPI<NotionPage, NotionConfig> {
  // Page Operations
  getPages: (databaseId?: string, filter?: NotionFilter, sorts?: NotionSort[], pageSize?: number, startCursor?: string) => Promise<NotionSearchResponse>;
  getPage: (pageId: string) => Promise<NotionPage>;
  updatePage: (pageId: string, properties: NotionPageProperties) => Promise<NotionPage>;
  deletePage: (pageId: string) => Promise<void>;
  
  // Block Operations
  getBlockChildren: (blockId: string, pageSize?: number, startCursor?: string) => Promise<NotionPageChildren>;
  getBlock: (blockId: string) => Promise<NotionBlock>;
  appendBlockChildren: (blockId: string, children: any[]) => Promise<NotionPageChildren>;
  deleteBlock: (blockId: string) => Promise<void>;
  
  // Database Operations
  getDatabase: (databaseId: string) => Promise<NotionDatabase>;
  queryDatabase: (databaseId: string, query: NotionDatabaseQuery) => Promise<NotionSearchResponse>;
  createDatabase: (parent: NotionParent, properties: NotionDatabaseProperties) => Promise<NotionDatabase>;
  
  // Search Operations
  search: (query?: string, filter?: NotionFilter, sorts?: NotionSort[], startCursor?: string, pageSize?: number) => Promise<NotionSearchResponse>;
  
  // Comment Operations
  getComments: (blockId: string) => Promise<NotionDiscussion[]>;
  createComment: (parentId: NotionParent, richText: NotionRichText[]) => Promise<NotionComment>;
  
  // User Operations
  getCurrentUser: () => Promise<NotionUser>;
  getUser: (userId: string) => Promise<NotionUser>;
}

// Hook Types
export interface NotionHookReturn extends AtomIntegrationHookReturn<NotionPage> {
  state: NotionState;
  api: NotionAPI;
  actions: NotionActions;
  config: NotionConfig;
}

export interface NotionDataSourceHookReturn extends AtomIntegrationHookReturn<NotionPageEnhanced> {
  state: NotionDataSourceState;
  api: NotionAPI;
  actions: NotionDataSourceActions;
  config: NotionIngestionConfig;
}

// Actions Types
export interface NotionActions {
  // Page Actions
  createPage: (parentId: string, properties: NotionPageProperties, children?: any[]) => Promise<NotionPage>;
  updatePage: (pageId: string, properties: NotionPageProperties) => Promise<NotionPage>;
  deletePages: (pageIds: string[]) => Promise<void>;
  archivePage: (pageId: string) => Promise<void>;
  
  // Block Actions
  createBlock: (blockId: string, block: any) => Promise<NotionBlock>;
  updateBlock: (blockId: string, block: any) => Promise<NotionBlock>;
  deleteBlocks: (blockIds: string[]) => Promise<void>;
  moveBlock: (blockId: string, targetBlockId: string, position: 'before' | 'after' | 'child') => Promise<void>;
  
  // Navigation Actions
  navigateToPage: (page: NotionPage) => void;
  navigateUp: () => void;
  
  // Search Actions
  search: (query?: string, filter?: NotionFilter, sorts?: NotionSort[]) => Promise<NotionSearchResponse>;
  
  // UI Actions
  selectItems: (items: (NotionPage | NotionDatabase | NotionBlock)[]) => void;
  sortBy: (field: NotionSortField, order: NotionSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'tree') => void;
  setFilters: (filters: NotionFilters) => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface NotionDataSourceActions {
  // Discovery Actions
  discoverPages: (databaseId?: string) => Promise<NotionPageEnhanced[]>;
  discoverDatabases: () => Promise<NotionDatabase[]>;
  discoverBlocks: (pageId: string) => Promise<NotionBlock[]>;
  discoverComments: (pageId: string) => Promise<NotionComment[]>;
  
  // Ingestion Actions
  ingestPages: (pages: NotionPageEnhanced[]) => Promise<void>;
  ingestDatabase: (databaseId: string) => Promise<void>;
  
  // Sync Actions
  syncPages: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Filters Type
export interface NotionFilters {
  databases: string[];
  pageTypes: string[];
  hasComments: boolean;
  isArchived: boolean;
  dateRange?: {
    start: Date;
    end: Date;
  };
}

// Sort Types
export type NotionSortField = 'title' | 'created_time' | 'last_edited_time' | 'created_by' | 'type';
export type NotionSortOrder = 'asc' | 'desc';

// Error Types
export class NotionError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;
  public statusCode?: number;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string, statusCode?: number) {
    super(message);
    this.name = 'NotionError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

// Constants
export const notionConfigDefaults: Partial<NotionConfig> = {
  apiBaseUrl: 'https://api.notion.com/v1',
  version: '2022-06-28',
  includeArchivedPages: false,
  includeArchivedBlocks: false,
  includePageContent: true,
  includeBlockContent: true,
  includeComments: true,
  includeDatabasePages: true,
  maxPageDepth: 10,
  extractMarkdown: true,
  extractPlainText: true,
  extractBlockTypes: [
    'paragraph',
    'heading_1',
    'heading_2',
    'heading_3',
    'bulleted_list_item',
    'numbered_list_item',
    'to_do',
    'toggle',
    'quote',
    'callout',
    'image',
    'file',
    'pdf',
    'bookmark'
  ],
  includeFormatting: true,
  apiCallsPerSecond: 3, // Notion API rate limit
  useBatchRequests: true
};

export const notionIngestionConfigDefaults: Partial<NotionIngestionConfig> = {
  sourceId: 'notion-integration',
  sourceName: 'Notion',
  sourceType: 'notion',
  apiBaseUrl: 'https://api.notion.com/v1',
  version: '2022-06-28',
  includeArchivedPages: false,
  includeArchivedBlocks: false,
  maxPageDepth: 10,
  includeDatabases: true,
  excludedDatabaseIds: [],
  includedDatabaseIds: [],
  includePageContent: true,
  includeBlockContent: true,
  includeComments: true,
  includeDatabasePages: true,
  extractBlockTypes: [
    'paragraph',
    'heading_1',
    'heading_2',
    'heading_3',
    'bulleted_list_item',
    'numbered_list_item',
    'to_do',
    'toggle',
    'quote',
    'callout',
    'image',
    'file',
    'pdf',
    'bookmark'
  ],
  extractMarkdown: true,
  extractPlainText: true,
  includeFormatting: true,
  includeImages: false,
  includeFiles: true,
  maxFileSize: 50 * 1024 * 1024, // 50MB
  autoIngest: true,
  ingestInterval: 1800000, // 30 minutes
  batchSize: 25, // Notion API limit
  maxConcurrentIngestions: 2,
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const notionSearchDefaults = {
  pageSize: 100,
  sorts: [
    {
      property: 'last_edited_time',
      direction: 'descending'
    }
  ]
};

export const notionSortFields: NotionSortField[] = ['title', 'created_time', 'last_edited_time', 'created_by', 'type'];
export const notionSortOrders: NotionSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';