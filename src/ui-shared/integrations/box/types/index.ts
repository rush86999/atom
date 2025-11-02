/**
 * ATOM Box Integration - TypeScript Types
 * File Storage → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// Box API Types
export interface BoxFile {
  id: string;
  type: 'file';
  name: string;
  description?: string;
  size: number;
  created_at: string;
  modified_at: string;
  content_created_at: string;
  content_modified_at: string;
  etag: string;
  file_version?: BoxFileVersion;
  sha1: string;
  created_by: BoxUser;
  modified_by: BoxUser;
  owned_by: BoxUser;
  shared_link?: BoxSharedLink;
  parent: BoxFolder;
  item_collection?: BoxItemCollection;
  tags?: string[];
  purged_at?: string;
  trashed_at?: string;
}

export interface BoxFolder {
  id: string;
  type: 'folder';
  name: string;
  description?: string;
  size?: number;
  created_at: string;
  modified_at: string;
  trashed_at?: string;
  purged_at?: string;
  content_created_at?: string;
  content_modified_at?: string;
  created_by?: BoxUser;
  modified_by?: BoxUser;
  owned_by?: BoxUser;
  shared_link?: BoxSharedLink;
  folder_upload_email?: BoxFolderUploadEmail;
  parent?: BoxFolder;
  item_collection?: BoxItemCollection;
  sync_state?: 'not_synced' | 'partially_synced' | 'synced';
  has_collaborations?: boolean;
  can_non_owners_invite?: boolean;
  is_externally_owned?: boolean;
  path_collection?: BoxPathCollection;
  tags?: string[];
}

export interface BoxFileVersion {
  id: string;
  type: 'file_version';
  sha1: string;
  name: string;
  size: number;
  created_at: string;
  modified_at: string;
  modified_by?: BoxUser;
  trashed_at?: string;
  purged_at?: string;
}

export interface BoxUser {
  id: string;
  type: 'user';
  name: string;
  login: string;
  created_at?: string;
  modified_at?: string;
  language?: string;
  timezone?: string;
  space_amount?: number;
  max_upload_size?: number;
  tracking_codes?: string[];
  can_see_managed_users?: boolean;
  is_sync_enabled?: boolean;
  is_external_collab_restricted?: boolean;
  status: 'active' | 'inactive' | 'cannot_delete_edit';
  job_title?: string;
  phone?: string;
  address?: string;
  avatar_url?: string;
}

export interface BoxSharedLink {
  url: string;
  download_url?: string;
  vanity_url?: string;
  is_password_enabled: boolean;
  unshared_at?: string;
  download_count?: number;
  preview_count?: number;
  access: 'open' | 'company' | 'collaborators';
  permissions: BoxSharedLinkPermissions;
  effective_access?: 'open' | 'company' | 'collaborators';
  effective_permission?: 'can_download' | 'can_preview' | 'can_edit';
}

export interface BoxSharedLinkPermissions {
  can_download: boolean;
  can_preview: boolean;
  can_edit: boolean;
}

export interface BoxItemCollection {
  total_count: number;
  entries: (BoxFile | BoxFolder)[];
  limit: number;
  offset: number;
  order: BoxCollectionOrder[];
}

export interface BoxCollectionOrder {
  by: 'type' | 'name' | 'id' | 'date' | 'size';
  direction: 'ASC' | 'DESC';
}

export interface BoxFolderUploadEmail {
  access: 'open' | 'collaborators';
  email: string;
}

export interface BoxPathCollection {
  total_count: number;
  entries: BoxFolder[];
}

export interface BoxCollectionResponse {
  total_count: number;
  entries: (BoxFile | BoxFolder)[];
  limit: number;
  offset: number;
  order: BoxCollectionOrder[];
  next_marker?: string;
  prev_marker?: string;
}

export interface BoxUploadResponse {
  id: string;
  type: 'file';
  name: string;
  size: number;
  parent: BoxFolder;
  created_at: string;
  modified_at: string;
  created_by: BoxUser;
  modified_by: BoxUser;
  owned_by: BoxUser;
  sha1: string;
  etag: string;
}

export interface BoxDownloadResponse {
  blob: Blob;
  filename: string;
  contentType: string;
  size: number;
}

export interface BoxSearchResponse {
  total_count: number;
  limit: number;
  offset: number;
  entries: (BoxFile | BoxFolder)[];
  next_marker?: string;
  prev_marker?: string;
  query: string;
  scopes: string[];
  created_at_range: {
    lt?: string;
    gte?: string;
  };
  updated_at_range: {
    lt?: string;
    gte?: string;
  };
}

export interface BoxWebhook {
  id: string;
  type: 'webhook';
  target: {
    id: string;
    type: 'folder' | 'file';
  };
  address: string;
  triggers: string[];
  created_at: string;
  modified_at: string;
  created_by: BoxUser;
  active: boolean;
}

// Box Configuration Types
export interface BoxConfig extends AtomFileStorageConfig {
  // API Configuration
  apiBaseUrl: string;
  uploadApiUrl: string;
  
  // Box-specific settings
  clientId: string;
  clientSecret: string;
  enterpriseId?: string;
  
  // File Processing
  useChunkedUpload: boolean;
  chunkSize: number;
  maxFileSize: number;
  supportedFileTypes: string[];
  
  // Sync Settings
  includeSharedFiles: boolean;
  includeSharedFolders: boolean;
  excludePaths: string[];
  maxSyncDepth: number;
  
  // Rate Limiting
  apiCallsPerSecond: number;
  useRateLimiter: boolean;
  
  // Security Settings
  useEncryption: boolean;
  encryptionKey?: string;
  
  // Platform-specific
  tauriCommands?: {
    downloadFile: string;
    uploadFile: string;
    createFolder: string;
  };
}

// Enhanced Types
export interface BoxFileEnhanced extends BoxFile {
  source: 'box';
  discoveredAt: string;
  processedAt?: string;
  textExtracted?: boolean;
  previewGenerated?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  downloadUrl?: string;
  thumbnailUrl?: string;
  metadata?: BoxFileMetadata;
}

export interface BoxFolderEnhanced extends BoxFolder {
  source: 'box';
  discoveredAt: string;
  fileCount?: number;
  totalSize?: number;
  lastModified?: string;
  recursiveDiscovered?: boolean;
}

export interface BoxFileMetadata {
  extracted: {
    text?: string;
    images?: string[];
    links?: string[];
    tags?: string[];
  };
  analysis: {
    fileType: string;
    isEncrypted: boolean;
    isCorrupted: boolean;
    hasVirus: boolean;
    compliance: {
      gdprCompliant: boolean;
      hasPII: boolean;
      retentionRequired: boolean;
    };
  };
  preview: {
    thumbnailGenerated: boolean;
    previewUrl?: string;
    thumbnailUrl?: string;
  };
}

// Component Props
export interface AtomBoxManagerProps extends AtomIntegrationProps<BoxConfig> {
  // Box-specific events
  onFileUploaded?: (file: BoxFile) => void;
  onFileDownloaded?: (file: BoxFile) => void;
  onFolderCreated?: (folder: BoxFolder) => void;
  onFolderDeleted?: (folderId: string) => void;
  onFileShared?: (file: BoxFile, shareInfo: BoxSharedLink) => void;
  onWebhookCreated?: (webhook: BoxWebhook) => void;
  onPermissionChanged?: (itemId: string, permissions: any) => void;
}

export interface AtomBoxDataSourceProps extends AtomIntegrationProps<BoxConfig, AtomBoxIngestionConfig> {
  // Ingestion-specific events
  onFileDiscovered?: (file: BoxFileEnhanced) => void;
  onFolderDiscovered?: (folder: BoxFolderEnhanced) => void;
  onWebhookDiscovered?: (webhook: BoxWebhook) => void;
}

// State Types
export interface AtomBoxState extends AtomIntegrationState {
  files: BoxFile[];
  folders: BoxFolder[];
  webhooks: BoxWebhook[];
  currentFolder?: BoxFolder;
  breadcrumb: BoxFolder[];
  selectedItems: (BoxFile | BoxFolder)[];
  uploadProgress: Record<string, number>;
  downloadProgress: Record<string, number>;
  searchResults: BoxSearchResponse;
  sortBy: BoxSortField;
  sortOrder: BoxSortOrder;
  viewMode: 'grid' | 'list' | 'tree';
  filters: BoxFilters;
}

export interface AtomBoxDataSourceState extends AtomIntegrationState {
  discoveredFiles: BoxFileEnhanced[];
  discoveredFolders: BoxFolderEnhanced[];
  discoveredWebhooks: BoxWebhook[];
  ingestionQueue: BoxFileEnhanced[];
  processingIngestion: boolean;
  stats: {
    totalFiles: number;
    totalFolders: number;
    totalWebhooks: number;
    ingestedFiles: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataSize: number;
  };
}

// Ingestion Configuration
export interface AtomBoxIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'box';
  
  // API Configuration
  apiBaseUrl: string;
  uploadApiUrl: string;
  clientId: string;
  clientSecret: string;
  enterpriseId?: string;
  
  // File Discovery
  folderIds: string[];
  includeRoot: boolean;
  includeSharedFiles: boolean;
  includeSharedFolders: boolean;
  excludePaths: string[];
  maxSyncDepth: number;
  supportedFileTypes: string[];
  maxFileSize: number;
  
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
  useThumbnailApi: boolean;
  thumbnailSize: string;
  
  // Sync Settings
  useWebhooks: boolean;
  webhookEvents: string[];
  syncInterval: number;
  incrementalSync: boolean;
  
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
export interface AtomBoxAPI extends AtomIntegrationAPI<BoxFile | BoxFolder, BoxConfig> {
  // Authentication
  authenticate: (authCode: string) => Promise<BoxAuthResponse>;
  refreshToken: (refreshToken: string) => Promise<BoxAuthResponse>;
  
  // File Operations
  getFiles: (folderId?: string, limit?: number, offset?: number) => Promise<BoxCollectionResponse>;
  getFile: (fileId: string) => Promise<BoxFile>;
  uploadFile: (file: File, folderId?: string, onProgress?: (progress: number) => void) => Promise<BoxUploadResponse>;
  downloadFile: (fileId: string) => Promise<BoxDownloadResponse>;
  updateFile: (fileId: string, updates: Partial<BoxFile>) => Promise<BoxFile>;
  deleteFile: (fileId: string) => Promise<void>;
  copyFile: (fileId: string, targetFolderId: string, newName?: string) => Promise<BoxFile>;
  moveFile: (fileId: string, targetFolderId: string) => Promise<BoxFile>;
  
  // Folder Operations
  getFolders: (folderId?: string, limit?: number, offset?: number) => Promise<BoxCollectionResponse>;
  getFolder: (folderId: string) => Promise<BoxFolder>;
  createFolder: (name: string, parentId?: string) => Promise<BoxFolder>;
  updateFolder: (folderId: string, updates: Partial<BoxFolder>) => Promise<BoxFolder>;
  deleteFolder: (folderId: string, recursive?: boolean) => Promise<void>;
  
  // Search Operations
  search: (query: string, limit?: number, offset?: number, filters?: BoxSearchFilters) => Promise<BoxSearchResponse>;
  
  // Share Operations
  createSharedLink: (itemId: string, access?: string, password?: string) => Promise<BoxSharedLink>;
  updateSharedLink: (sharedLink: BoxSharedLink, updates: Partial<BoxSharedLink>) => Promise<BoxSharedLink>;
  deleteSharedLink: (itemId: string) => Promise<void>;
  
  // Webhook Operations
  createWebhook: (targetId: string, address: string, triggers: string[]) => Promise<BoxWebhook>;
  getWebhooks: () => Promise<BoxWebhook[]>;
  deleteWebhook: (webhookId: string) => Promise<void>;
  
  // Preview Operations
  getThumbnail: (fileId: string, size?: string) => Promise<string>;
  getPreview: (fileId: string, format?: string) => Promise<string>;
  
  // Chunked Upload Operations
  initiateChunkedUpload: (filename: string, fileSize: number, folderId?: string) => Promise<BoxChunkedUploadSession>;
  uploadChunk: (sessionId: string, chunk: Blob, partNumber: number, onProgress?: (progress: number) => void) => Promise<void>;
  completeChunkedUpload: (sessionId: string, parts: BoxChunkedUploadPart[]) => Promise<BoxFile>;
  abortChunkedUpload: (sessionId: string) => Promise<void>;
}

export interface BoxAuthResponse {
  access_token: string;
  expires_in: number;
  refresh_token: string;
  token_type: string;
}

export interface BoxChunkedUploadSession {
  session_id: string;
  part_size: number;
  total_parts: number;
  upload_url: string;
  file_size: number;
}

export interface BoxChunkedUploadPart {
  part_id: string;
  offset: number;
  size: number;
  sha1: string;
}

export interface BoxSearchFilters {
  name?: string;
  name_match?: 'contains' | 'starts_with' | 'exact_match';
  description?: string;
  size_range?: {
    lt?: number;
    gt?: number;
    gte?: number;
    lte?: number;
  };
  created_at_range?: {
    lt?: string;
    gt?: string;
    gte?: string;
    lte?: string;
  };
  updated_at_range?: {
    lt?: string;
    gt?: string;
    gte?: string;
    lte?: string;
  };
  owner_user_ids?: string[];
  ancestor_folder_ids?: string[];
  content_types?: string[];
  file_extensions?: string[];
  trash?: 'include' | 'exclude' | 'only';
}

// Hook Types
export interface AtomBoxHookReturn extends AtomIntegrationHookReturn<BoxFile | BoxFolder> {
  state: AtomBoxState;
  api: AtomBoxAPI;
  actions: AtomBoxActions;
  config: BoxConfig;
}

export interface AtomBoxDataSourceHookReturn extends AtomIntegrationHookReturn<BoxFileEnhanced> {
  state: AtomBoxDataSourceState;
  api: AtomBoxAPI;
  actions: AtomBoxDataSourceActions;
  config: AtomBoxIngestionConfig;
}

// Actions Types
export interface AtomBoxActions {
  // File Actions
  uploadFiles: (files: FileList, folderId?: string) => Promise<BoxUploadResponse[]>;
  downloadFile: (fileId: string, filename?: string) => Promise<void>;
  deleteFiles: (fileIds: string[]) => Promise<void>;
  moveFiles: (fileIds: string[], targetFolderId: string) => Promise<void>;
  copyFiles: (fileIds: string[], targetFolderId: string) => Promise<void>;
  shareFile: (fileId: string, access?: string, password?: string) => Promise<BoxSharedLink>;
  
  // Folder Actions
  createFolder: (name: string, parentId?: string) => Promise<BoxFolder>;
  deleteFolder: (folderId: string, recursive?: boolean) => Promise<void>;
  shareFolder: (folderId: string, access?: string, password?: string) => Promise<BoxSharedLink>;
  
  // Navigation Actions
  navigateToFolder: (folder: BoxFolder) => void;
  navigateUp: () => void;
  
  // Search Actions
  search: (query: string, filters?: BoxSearchFilters) => Promise<BoxSearchResponse>;
  
  // UI Actions
  selectItems: (items: (BoxFile | BoxFolder)[]) => void;
  sortBy: (field: BoxSortField, order: BoxSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'tree') => void;
  setFilters: (filters: BoxFilters) => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface AtomBoxDataSourceActions {
  // Discovery Actions
  discoverFiles: (folderIds?: string[]) => Promise<BoxFileEnhanced[]>;
  discoverFolders: (folderIds?: string[]) => Promise<BoxFolderEnhanced[]>;
  discoverWebhooks: () => Promise<BoxWebhook[]>;
  
  // Ingestion Actions
  ingestFiles: (files: BoxFileEnhanced[]) => Promise<void>;
  ingestFolder: (folderId: string, recursive?: boolean) => Promise<void>;
  
  // Sync Actions
  syncFiles: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Filters Type
export interface BoxFilters {
  fileTypes: string[];
  sizeRange?: {
    min: number;
    max: number;
  };
  dateRange?: {
    start: Date;
    end: Date;
  };
  owners: string[];
  tags: string[];
  isShared: boolean;
  hasWebhook: boolean;
}

// Sort Types
export type BoxSortField = 'name' | 'size' | 'created_at' | 'modified_at' | 'type' | 'id';
export type BoxSortOrder = 'asc' | 'desc';

// Error Types
export class AtomBoxError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;
  public statusCode?: number;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string, statusCode?: number) {
    super(message);
    this.name = 'AtomBoxError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

// Constants
export const boxConfigDefaults: Partial<BoxConfig> = {
  apiBaseUrl: 'https://api.box.com/2.0',
  uploadApiUrl: 'https://upload.box.com/api/2.0',
  useChunkedUpload: true,
  chunkSize: 8 * 1024 * 1024, // 8MB
  maxFileSize: 5 * 1024 * 1024 * 1024, // 5GB (Box limit)
  supportedFileTypes: [
    '.txt', '.md', '.pdf', '.doc', '.docx', 
    '.rtf', '.odt', '.html', '.htm', '.csv',
    '.json', '.xml', '.yaml', '.yml', '.log',
    '.js', '.ts', '.jsx', '.tsx', '.py', '.java',
    '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'
  ],
  includeSharedFiles: true,
  includeSharedFolders: true,
  excludePaths: [],
  maxSyncDepth: 10,
  apiCallsPerSecond: 1024, // Box rate limit
  useRateLimiter: true,
  useEncryption: false
};

export const boxIngestionConfigDefaults: Partial<AtomBoxIngestionConfig> = {
  sourceId: 'box-integration',
  sourceName: 'Box',
  sourceType: 'box',
  apiBaseUrl: 'https://api.box.com/2.0',
  uploadApiUrl: 'https://upload.box.com/api/2.0',
  folderIds: ['0'], // Root folder
  includeRoot: true,
  includeSharedFiles: true,
  includeSharedFolders: true,
  excludePaths: [],
  maxSyncDepth: 10,
  supportedFileTypes: [
    '.txt', '.md', '.pdf', '.doc', '.docx', 
    '.rtf', '.odt', '.html', '.htm', '.csv',
    '.json', '.xml', '.yaml', '.yml', '.log',
    '.js', '.ts', '.jsx', '.tsx', '.py', '.java',
    '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'
  ],
  maxFileSize: 5 * 1024 * 1024 * 1024, // 5GB
  autoIngest: true,
  ingestInterval: 3600000, // 1 hour
  realTimeIngest: true,
  batchSize: 25,
  maxConcurrentIngestions: 2,
  extractMetadata: true,
  generateThumbnails: true,
  extractText: true,
  chunkSize: 1000,
  chunkOverlap: 100,
  useThumbnailApi: true,
  thumbnailSize: '256x256',
  useWebhooks: true,
  webhookEvents: ['FILE.UPLOADED', 'FILE.DELETED', 'FILE.TRASHED', 'FILE.UNTRASHED'],
  syncInterval: 300000, // 5 minutes
  incrementalSync: true,
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const boxSearchDefaults: BoxSearchFilters = {
  trash: 'exclude'
};

export const boxSortFields: BoxSortField[] = ['name', 'size', 'created_at', 'modified_at', 'type', 'id'];
export const boxSortOrders: BoxSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';