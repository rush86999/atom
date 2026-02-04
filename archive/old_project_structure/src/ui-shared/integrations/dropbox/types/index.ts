/**
 * ATOM Dropbox Integration - TypeScript Types
 * File Storage → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// Dropbox API Types
export interface DropboxFile {
  id: string;
  name: string;
  path_lower: string;
  path_display: string;
  size: number;
  client_modified: string;
  server_modified: string;
  rev: string;
  content_hash: string;
  is_downloadable: boolean;
  .tag: 'file';
  has_explicit_shared_members: boolean;
  file_hash_info?: {
    content_hash: string;
    hash_type: string;
  };
  media_info?: DropboxMediaInfo;
  sharing_info?: DropboxSharingInfo;
}

export interface DropboxFolder {
  id: string;
  name: string;
  path_lower: string;
  path_display: string;
  .tag: 'folder';
  sharing_info?: DropboxSharingInfo;
}

export interface DropboxMediaInfo {
  \.tag: 'photo' | 'video';
  metadata?: {
    dimensions?: {
      height: number;
      width: number;
    };
    time_taken?: string;
    gps_coordinates?: {
      latitude: number;
      longitude: number;
    };
  };
  thumbnail?: string;
}

export interface DropboxSharingInfo {
  read_only: boolean;
  parent_shared_folder_id?: string;
  shared_folder_id?: string;
  modified_by?: string;
}

// Dropbox Configuration Types
export interface DropboxConfig extends AtomFileStorageConfig {
  // API Configuration
  apiBaseUrl: string;
  apiVersion: string;
  
  // Dropbox-specific settings
  teamId?: string;
  businessAccount: boolean;
  
  // File Processing
  useThumbnailApi: boolean;
  thumbnailSize: string; // 'w64h64', 'w128h128', etc.
  
  // Sync Settings
  includeDeleted: boolean;
  includeShared: boolean;
  
  // Rate Limiting
  apiCallsPerMinute: number;
  retryStrategy: 'linear' | 'exponential';
  
  // Platform-specific
  tauriCommands?: {
    downloadFile: string;
    monitorFolder: string;
  };
}

// Dropbox API Response Types
export interface DropboxApiResponse<T = any> {
  entries: T[];
  cursor?: string;
  has_more?: boolean;
}

export interface DropboxSearchResponse {
  matches: DropboxSearchMatch[];
  has_more: boolean;
  start: number;
}

export interface DropboxSearchMatch {
  metadata: DropboxFile | DropboxFolder;
  match_type: {
    \.tag: 'filename' | 'content';
  };
}

export interface DropboxWebhookEvent {
  list_folder: {
    accounts: string[];
    cursor?: string;
  };
}

// Enhanced Types
export interface DropboxFileEnhanced extends DropboxFile {
  source: 'dropbox';
  discoveredAt: string;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  textExtracted?: boolean;
  thumbnailGenerated?: boolean;
}

export interface DropboxFolderEnhanced extends DropboxFolder {
  source: 'dropbox';
  fileCount?: number;
  totalSize?: number;
  discoveredAt: string;
}

// Component Props
export interface AtomDropboxManagerProps extends AtomIntegrationProps<DropboxConfig> {
  // Dropbox-specific events
  onFolderCreated?: (folder: DropboxFolder) => void;
  onFolderDeleted?: (folderId: string) => void;
  onFileUploaded?: (file: DropboxFile) => void;
  onFileDeleted?: (fileId: string) => void;
  onFileDownloaded?: (file: DropboxFile) => void;
}

export interface AtomDropboxDataSourceProps extends AtomIntegrationProps<DropboxConfig, AtomDropboxIngestionConfig> {
  // Ingestion-specific events
  onFileDiscovered?: (file: DropboxFileEnhanced) => void;
  onFolderDiscovered?: (folder: DropboxFolderEnhanced) => void;
}

// State Types
export interface AtomDropboxState extends AtomIntegrationState {
  files: DropboxFile[];
  folders: DropboxFolder[];
  currentFolder?: DropboxFolder;
  breadcrumb: DropboxFolder[];
  selectedItems: (DropboxFile | DropboxFolder)[];
  uploadProgress: Record<string, number>;
  downloadProgress: Record<string, number>;
  searchResults: DropboxSearchMatch[];
  sortBy: DropboxSortField;
  sortOrder: DropboxSortOrder;
  viewMode: 'grid' | 'list' | 'compact';
}

export interface AtomDropboxDataSourceState extends AtomIntegrationState {
  discoveredFiles: DropboxFileEnhanced[];
  discoveredFolders: DropboxFolderEnhanced[];
  ingestionQueue: DropboxFileEnhanced[];
  processingIngestion: boolean;
  stats: {
    totalFiles: number;
    ingestedFiles: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataSize: number;
  };
}

// Ingestion Configuration
export interface AtomDropboxIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'dropbox';
  
  // File Discovery
  supportedFileTypes: string[];
  maxFileSize: number;
  excludePatterns: string[];
  includeShared: boolean;
  includeDeleted: boolean;
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  realTimeIngest: boolean;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Processing
  extractMetadata: boolean;
  generateThumbnails: boolean;
  extractText: boolean;
  chunkSize: number;
  chunkOverlap: number;
  
  // Dropbox-specific
  useThumbnailApi: boolean;
  thumbnailSize: string;
  
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
export interface AtomDropboxAPI extends AtomIntegrationAPI<DropboxFile | DropboxFolder, DropboxConfig> {
  // File Operations
  getFiles: (folderPath?: string, recursive?: boolean) => Promise<DropboxFile[]>;
  getFile: (filePath: string) => Promise<DropboxFile>;
  uploadFile: (file: File, path?: string) => Promise<DropboxFile>;
  downloadFile: (filePath: string) => Promise<Blob>;
  deleteFile: (filePath: string) => Promise<void>;
  
  // Folder Operations
  createFolder: (path: string) => Promise<DropboxFolder>;
  deleteFolder: (path: string) => Promise<void>;
  
  // Search Operations
  search: (query: string, options?: DropboxSearchOptions) => Promise<DropboxSearchMatch[]>;
  
  // Sync Operations
  getChanges: (cursor?: string) => Promise<DropboxApiResponse<DropboxFile | DropboxFolder>>;
  
  // Utility Operations
  getTemporaryLink: (filePath: string) => Promise<string>;
  getThumbnail: (filePath: string, size?: string) => Promise<Blob>;
  getAccountInfo: () => Promise<DropboxAccountInfo>;
}

export interface DropboxSearchOptions {
  path?: string;
  includeDeleted: boolean;
  fileStatus: 'active' | 'deleted';
  fileExtensions?: string[];
  fileCategories?: string[];
  maxResults?: number;
}

export interface DropboxAccountInfo {
  name: string;
  email: string;
  account_type: {
    \.tag: 'basic' | 'pro' | 'business';
  };
  used_space: number;
  allocated_space: number;
  country: string;
  locale: string;
}

// Hook Types
export interface AtomDropboxHookReturn extends AtomIntegrationHookReturn<DropboxFile | DropboxFolder> {
  state: AtomDropboxState;
  api: AtomDropboxAPI;
  actions: AtomDropboxActions;
  config: DropboxConfig;
}

export interface AtomDropboxDataSourceHookReturn extends AtomIntegrationHookReturn<DropboxFileEnhanced> {
  state: AtomDropboxDataSourceState;
  api: AtomDropboxAPI;
  actions: AtomDropboxDataSourceActions;
  config: AtomDropboxIngestionConfig;
}

// Actions Types
export interface AtomDropboxActions {
  // File Actions
  uploadFiles: (files: FileList, path?: string) => Promise<DropboxFile[]>;
  downloadFile: (filePath: string) => Promise<void>;
  deleteFiles: (filePaths: string[]) => Promise<void>;
  
  // Folder Actions
  createFolder: (path: string) => Promise<DropboxFolder>;
  deleteFolder: (path: string) => Promise<void>;
  
  // Navigation Actions
  navigateToFolder: (folder: DropboxFolder) => void;
  navigateUp: () => void;
  
  // Search Actions
  search: (query: string) => Promise<DropboxSearchMatch[]>;
  
  // UI Actions
  selectItems: (items: (DropboxFile | DropboxFolder)[]) => void;
  sortBy: (field: DropboxSortField, order: DropboxSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'compact') => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface AtomDropboxDataSourceActions {
  // Discovery Actions
  discoverFiles: (recursive?: boolean) => Promise<DropboxFileEnhanced[]>;
  discoverFolders: (recursive?: boolean) => Promise<DropboxFolderEnhanced[]>;
  
  // Ingestion Actions
  ingestFiles: (files: DropboxFileEnhanced[]) => Promise<void>;
  ingestFolder: (folderPath: string, recursive?: boolean) => Promise<void>;
  
  // Sync Actions
  syncFiles: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Sort Types
export type DropboxSortField = 'name' | 'size' | 'modified' | 'type' | 'path';
export type DropboxSortOrder = 'asc' | 'desc';

// Error Types
export class AtomDropboxError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string) {
    super(message);
    this.name = 'AtomDropboxError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
  }
}

// Webhook Types
export interface DropboxWebhookEvent {
  type: 'file_add' | 'file_delete' | 'folder_add' | 'folder_delete' | 'file_modified';
  account_id: string;
  users: DropboxWebhookUser[];
  delta: {
    users: string[];
  };
}

export interface DropboxWebhookUser {
  account_id: string;
  display_name: string;
  email: string;
}

// Constants
export const dropboxConfigDefaults: Partial<DropboxConfig> = {
  apiBaseUrl: 'https://api.dropboxapi.com/2',
  apiVersion: '2',
  businessAccount: false,
  useThumbnailApi: true,
  thumbnailSize: 'w128h128',
  includeDeleted: false,
  includeShared: true,
  apiCallsPerMinute: 100,
  retryStrategy: 'exponential'
};

export const dropboxIngestionConfigDefaults: Partial<AtomDropboxIngestionConfig> = {
  sourceId: 'dropbox-integration',
  sourceName: 'Dropbox',
  sourceType: 'dropbox',
  supportedFileTypes: [
    '.txt', '.md', '.pdf', '.doc', '.docx', 
    '.rtf', '.odt', '.html', '.htm', '.csv',
    '.json', '.xml', '.yaml', '.yml', '.log',
    '.js', '.ts', '.jsx', '.tsx', '.py', '.java',
    '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'
  ],
  maxFileSize: 150 * 1024 * 1024, // 150MB (Dropbox limit)
  excludePatterns: [
    '*/node_modules/*',
    '*/.git/*',
    '*/dist/*',
    '*/build/*',
    '*/temp/*',
    '*/tmp/*'
  ],
  autoIngest: true,
  ingestInterval: 3600000, // 1 hour
  realTimeIngest: true,
  batchSize: 25, // Dropbox API limit
  maxConcurrentIngestions: 2,
  extractMetadata: true,
  generateThumbnails: true,
  extractText: true,
  chunkSize: 1000,
  chunkOverlap: 100,
  useThumbnailApi: true,
  thumbnailSize: 'w128h128',
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const dropboxSearchDefaults: DropboxSearchOptions = {
  includeDeleted: false,
  fileStatus: 'active',
  maxResults: 100
};

export const dropboxSortFields: DropboxSortField[] = ['name', 'size', 'modified', 'type', 'path'];
export const dropboxSortOrders: DropboxSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';