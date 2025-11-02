/**
 * ATOM Box Integration - TypeScript Types
 * Cross-platform: Next.js & Tauri
 */

// Base Types
export interface AtomUser {
  id: string;
  email: string;
  name: string;
  avatar?: string;
}

export interface AtomToken {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: Date;
  tokenType: string;
}

// Platform Detection
export type AtomPlatform = 'nextjs' | 'tauri';
export type AtomTheme = 'auto' | 'light' | 'dark';
export type AtomSize = 'small' | 'medium' | 'large';
export type AtomLayout = 'grid' | 'list' | 'compact';

// Box API Types
export interface BoxFile {
  id: string;
  type: 'file';
  name: string;
  size?: number;
  created_at: string;
  modified_at: string;
  parent?: BoxFolder;
  description?: string;
  shared_link?: BoxSharedLink;
  expiring_embed_link?: BoxEmbedLink;
  extensions?: string[];
  content_type?: string;
  metadata?: BoxMetadata;
  encryption_info?: BoxEncryptionInfo;
}

export interface BoxFolder {
  id: string;
  type: 'folder';
  name: string;
  created_at: string;
  modified_at: string;
  parent?: BoxFolder;
  description?: string;
  shared_link?: BoxSharedLink;
  metadata?: BoxMetadata;
  size?: number; // Total size of folder contents
  item_count?: number;
}

export interface BoxSharedLink {
  url: string;
  access: 'open' | 'company' | 'collaborators';
  download_url?: string;
  vanity_url?: string;
  is_password_enabled?: boolean;
  unshared_at?: string;
  download_count?: number;
  preview_count?: number;
}

export interface BoxEmbedLink {
  url: string;
  expiring_embed_link?: BoxEmbedLink;
  created_at?: string;
  expires_at?: string;
}

export interface BoxMetadata {
  global?: Record<string, any>;
  enterprise?: Record<string, any>;
  template?: Record<string, any>;
}

export interface BoxEncryptionInfo {
  encrypted?: boolean;
  algorithm?: string;
  key_id?: string;
}

// Search Types
export interface BoxSearchQuery {
  query: string;
  scope?: string;
  limit?: number;
  offset?: number;
  fields?: string[];
}

export interface BoxSearchResult {
  id: string;
  name: string;
  type: 'file' | 'folder';
  size?: number;
  created_at: string;
  modified_at: string;
  path?: string;
  description?: string;
  extensions?: string[];
  relevance_score?: number;
}

// Upload Types
export interface BoxUploadRequest {
  file: File;
  folderId?: string;
  name?: string;
  metadata?: BoxMetadata;
  onProgress?: (progress: BoxUploadProgress) => void;
}

export interface BoxUploadProgress {
  loaded: number;
  total: number;
  percentage: number;
  speed?: number;
  timeRemaining?: number;
}

export interface BoxUploadSession {
  id: string;
  folder_id: string;
  file_name: string;
  file_size: number;
  chunk_size?: number;
  total_parts?: number;
  upload_expires_at: string;
}

export interface BoxUploadPart {
  part_id: string;
  offset: number;
  size: number;
  sha1?: string;
}

// Download Types
export interface BoxDownloadRequest {
  fileId: string;
  version?: string;
  range?: { start: number; end: number };
  onProgress?: (progress: BoxDownloadProgress) => void;
}

export interface BoxDownloadProgress {
  loaded: number;
  total: number;
  percentage: number;
  speed?: number;
  timeRemaining?: number;
}

// Configuration Types
export interface AtomBoxConfig {
  apiBaseUrl: string;
  uploadChunkSize: number;
  maxConcurrentUploads: number;
  maxConcurrentDownloads: number;
  syncInterval: number;
  batchSize: number;
  retryAttempts: number;
  retryDelay: number;
  timeoutMs: number;
  encryptionKey?: string;
  enableEncryption: boolean;
  enableRealTimeSync: boolean;
  enableBackgroundSync: boolean;
  enableCache: boolean;
  cacheMaxSize: number;
  cacheMaxAge: number;
}

// State Types
export interface AtomBoxState {
  authenticated: boolean;
  loading: boolean;
  error: string | null;
  files: BoxFile[];
  folders: BoxFolder[];
  selectedItems: (BoxFile | BoxFolder)[];
  searchResults: BoxSearchResult[];
  uploadProgress: Record<string, number>;
  downloadProgress: Record<string, number>;
  syncStatus: AtomSyncStatus;
  lastSyncTime: Date | null;
  currentFolder?: BoxFolder;
  breadcrumb: BoxFolder[];
  sortBy: BoxSortField;
  sortOrder: BoxSortOrder;
  viewMode: AtomLayout;
}

export type AtomSyncStatus = 'idle' | 'syncing' | 'synced' | 'error';

// Sort Types
export type BoxSortField = 'name' | 'size' | 'created_at' | 'modified_at' | 'type';
export type BoxSortOrder = 'asc' | 'desc';

// Event Types
export interface AtomBoxEvents {
  onAuthSuccess: (tokens: AtomToken) => void;
  onAuthError: (error: string) => void;
  onTokenRefresh: (refreshToken: string) => Promise<{ success: boolean; accessToken?: string; error?: string }>;
  onFileUpload: (file: BoxFile) => void;
  onFileDownload: (file: BoxFile) => void;
  onFolderCreated: (folder: BoxFolder) => void;
  onFolderDeleted: (folderId: string) => void;
  onFileDeleted: (fileId: string) => void;
  onSearch: (results: BoxSearchResult[]) => void;
  onProgress: (progress: AtomBoxProgress) => void;
  onSelectionChange: (items: (BoxFile | BoxFolder)[]) => void;
  onNavigate: (folder: BoxFolder) => void;
  onError: (error: string, context?: string) => void;
}

export interface AtomBoxProgress {
  type: 'upload' | 'download' | 'sync';
  fileId?: string;
  folderId?: string;
  loaded: number;
  total: number;
  percentage: number;
  speed?: number;
  timeRemaining?: number;
}

// API Response Types
export interface BoxApiResponse<T = any> {
  entries: T[];
  total_count: number;
  offset: number;
  limit: number;
  order: BoxSortField[];
  direction: BoxSortOrder[];
}

export interface BoxApiError {
  type: string;
  status: number;
  message: string;
  context_info?: Record<string, any>;
  request_id?: string;
  help_url?: string;
}

// Encryption Types
export interface AtomEncryptionPayload {
  encryptedData: number[];
  iv: number[];
  algorithm: string;
  version: string;
  timestamp: string;
}

export interface AtomEncryptedFile {
  encryptedChunks: number[][];
  iv: number[];
  algorithm: string;
  originalSize: number;
  originalName: string;
  encryptedSize: number;
  encryptionInfo: BoxEncryptionInfo;
}

// Sync Types
export interface AtomSyncEvent {
  type: 'fileChanged' | 'folderChanged' | 'syncStarted' | 'syncComplete' | 'syncError' | 'syncProgress';
  data: any;
  timestamp: Date;
  platform: AtomPlatform;
}

export interface AtomSyncQueue {
  id: string;
  type: 'file_upload' | 'file_download' | 'file_delete' | 'folder_create' | 'folder_delete' | 'filesystem';
  action: string;
  payload: any;
  timestamp: Date;
  platform: AtomPlatform;
  priority: number;
  attempts: number;
  maxAttempts: number;
  lastAttempt?: Date;
}

export interface AtomSyncStatus {
  initialized: boolean;
  platform: AtomPlatform;
  syncInProgress: boolean;
  queueLength: number;
  lastSyncTimestamp: Date | null;
  encryptionEnabled: boolean;
  websocketConnected: boolean;
  cacheSize: number;
}

// Hook Types
export interface AtomBoxHookReturn {
  state: AtomBoxState;
  api: AtomBoxApi;
  actions: AtomBoxActions;
  config: AtomBoxConfig;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface AtomBoxActions {
  authenticate: (tokens: AtomToken) => Promise<void>;
  refreshToken: () => Promise<boolean>;
  loadFiles: (folderId?: string) => Promise<void>;
  loadFile: (fileId: string) => Promise<BoxFile>;
  uploadFiles: (files: FileList, folderId?: string) => Promise<BoxFile[]>;
  downloadFile: (fileId: string, localPath?: string) => Promise<void>;
  deleteFiles: (fileIds: string[]) => Promise<void>;
  createFolder: (name: string, parentId?: string) => Promise<BoxFolder>;
  deleteFolder: (folderId: string) => Promise<void>;
  search: (query: string, scope?: string) => Promise<BoxSearchResult[]>;
  selectItems: (items: (BoxFile | BoxFolder)[]) => void;
  navigateToFolder: (folder: BoxFolder) => void;
  sortBy: (field: BoxSortField, order: BoxSortOrder) => void;
  setViewMode: (mode: AtomLayout) => void;
  refresh: () => Promise<void>;
  clearError: () => void;
}

// API Types
export interface AtomBoxApi {
  // Authentication
  authenticate: (tokens: AtomToken) => Promise<boolean>;
  refreshToken: (refreshToken: string) => Promise<{ success: boolean; accessToken?: string; error?: string }>;
  
  // File Operations
  getFiles: (folderId?: string, limit?: number) => Promise<BoxFile[]>;
  getFile: (fileId: string) => Promise<BoxFile>;
  uploadFile: (request: BoxUploadRequest) => Promise<BoxFile>;
  downloadFile: (request: BoxDownloadRequest) => Promise<Blob>;
  deleteFile: (fileId: string) => Promise<void>;
  search: (query: BoxSearchQuery) => Promise<BoxSearchResult[]>;
  
  // Folder Operations
  createFolder: (name: string, parentId?: string) => Promise<BoxFolder>;
  deleteFolder: (folderId: string) => Promise<void>;
  
  // Utility Methods
  getSharedLink: (fileId: string, access?: string) => Promise<BoxSharedLink>;
  getFileInfo: (fileId: string) => Promise<BoxFile>;
  getFolderInfo: (folderId: string) => Promise<BoxFolder>;
  moveItem: (itemId: string, newParentId: string) => Promise<void>;
  copyItem: (itemId: string, newParentId: string) => Promise<BoxFile | BoxFolder>;
}

// Component Props Types
export interface AtomBoxManagerProps {
  // Authentication
  user?: AtomUser;
  accessToken?: string;
  refreshToken?: string;
  
  // Configuration
  config?: Partial<AtomBoxConfig>;
  platform?: AtomPlatform;
  theme?: AtomTheme;
  size?: AtomSize;
  layout?: AtomLayout;
  
  // Features
  enableRealTimeSync?: boolean;
  enableBatchProcessing?: boolean;
  enableEncryption?: boolean;
  
  // Events
  onAuthSuccess?: (tokens: AtomToken) => void;
  onAuthError?: (error: string) => void;
  onTokenRefresh?: (refreshToken: string) => Promise<{ success: boolean; accessToken?: string; error?: string }>;
  onFileUpload?: (file: BoxFile) => void;
  onFileDownload?: (file: BoxFile) => void;
  onFolderCreated?: (folder: BoxFolder) => void;
  onFolderDeleted?: (folderId: string) => void;
  onFileDeleted?: (fileId: string) => void;
  onSearch?: (results: BoxSearchResult[]) => void;
  onProgress?: (progress: AtomBoxProgress) => void;
  onSelectionChange?: (items: (BoxFile | BoxFolder)[]) => void;
  onNavigate?: (folder: BoxFolder) => void;
  onError?: (error: string, context?: string) => void;
  
  // Children
  children?: React.ReactNode;
}

// Webhook Types
export interface BoxWebhookEvent {
  type: string;
  created_at: string;
  triggered_by: {
    user: BoxUser;
    application?: BoxApplication;
  };
  source: BoxFile | BoxFolder;
  details?: Record<string, any>;
}

export interface BoxWebhookConfig {
  id: string;
  target_url: string;
  triggers: BoxWebhookTrigger[];
  address?: string;
  webhook_id?: string;
  created_at: string;
  created_by: BoxUser;
}

export interface BoxWebhookTrigger {
  event_type: string;
  scope_type: string;
  scope_id?: string;
}

// User Types
export interface BoxUser {
  id: string;
  type: 'user';
  name: string;
  login: string;
  created_at: string;
  modified_at: string;
  language: string;
  timezone: string;
  space_amount: number;
  space_used: number;
  max_upload_size: number;
  avatar_url?: string;
  status: 'active' | 'inactive' | 'cannot_delete_edit';
  job_title?: string;
  phone?: string;
  address?: string;
}

export interface BoxApplication {
  id: string;
  type: 'application';
  name: string;
  description?: string;
  created_at: string;
  modified_at: string;
  platform: string;
  app_website?: string;
  developer?: BoxUser;
}

// Utility Types
export type BoxItemType = 'file' | 'folder';
export type BoxAccessLevel = 'open' | 'company' | 'collaborators';
export type BoxEventName = 'FILE.UPLOADED' | 'FILE.DOWNLOADED' | 'FILE.DELETED' | 'FOLDER.CREATED' | 'FOLDER.DELETED';

// Error Types
export class AtomBoxError extends Error {
  public type: string;
  public code: string;
  public context?: Record<string, any>;

  constructor(message: string, type: string, code: string, context?: Record<string, any>) {
    super(message);
    this.name = 'AtomBoxError';
    this.type = type;
    this.code = code;
    this.context = context;
  }
}

// Cache Types
export interface AtomBoxCache {
  files: Map<string, BoxFile>;
  folders: Map<string, BoxFolder>;
  search: Map<string, BoxSearchResult[]>;
  metadata: Map<string, any>;
  lastSync: Map<string, Date>;
}

// Batch Types
export interface AtomBoxBatch<T> {
  items: T[];
  total: number;
  batchIndex: number;
  totalBatches: number;
  processed: number;
}

// Performance Types
export interface AtomBoxPerformance {
  loadTime: number;
  uploadTime: number;
  downloadTime: number;
  searchTime: number;
  syncTime: number;
  cacheHitRate: number;
  requestCount: number;
  errorCount: number;
}

// Security Types
export interface AtomBoxSecurity {
  encryptionEnabled: boolean;
  encryptionAlgorithm: string;
  keyRotationEnabled: boolean;
  auditLoggingEnabled: boolean;
  ipWhitelistEnabled: boolean;
  twoFactorAuthEnabled: boolean;
}

// Export default configuration
export const defaultAtomBoxConfig: AtomBoxConfig = {
  apiBaseUrl: 'https://api.box.com/2.0',
  uploadChunkSize: 1048576, // 1MB
  maxConcurrentUploads: 3,
  maxConcurrentDownloads: 5,
  syncInterval: 30000, // 30 seconds
  batchSize: 50,
  retryAttempts: 3,
  retryDelay: 1000,
  timeoutMs: 30000,
  enableEncryption: false,
  enableRealTimeSync: true,
  enableBackgroundSync: true,
  enableCache: true,
  cacheMaxSize: 1000,
  cacheMaxAge: 3600000 // 1 hour
};

// Export utilities
export const boxFileExtensions = {
  images: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
  documents: ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
  spreadsheets: ['.xls', '.xlsx', '.csv', '.ods'],
  presentations: ['.ppt', '.pptx', '.odp'],
  videos: ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
  audio: ['.mp3', '.wav', '.flac', '.aac', '.ogg'],
  archives: ['.zip', '.rar', '.7z', '.tar', '.gz'],
  code: ['.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs']
};

export const boxSortFields: BoxSortField[] = ['name', 'size', 'created_at', 'modified_at', 'type'];
export const boxSortOrders: BoxSortOrder[] = ['asc', 'desc'];
export const atomPlatforms: AtomPlatform[] = ['nextjs', 'tauri'];
export const atomThemes: AtomTheme[] = ['auto', 'light', 'dark'];
export const atomSizes: AtomSize[] = ['small', 'medium', 'large'];
export const atomLayouts: AtomLayout[] = ['grid', 'list', 'compact'];