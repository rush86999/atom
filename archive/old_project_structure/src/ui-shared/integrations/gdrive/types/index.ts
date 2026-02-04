/**
 * ATOM Google Drive Integration - TypeScript Types
 * File Storage → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 */

import { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';

// Google Drive API Types
export interface GDriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  createdTime: string;
  modifiedTime: string;
  viewedByMeTime?: string;
  parents?: string[];
  webViewLink: string;
  webContentLink?: string;
  trashed?: boolean;
  explicitlyTrashed?: boolean;
  owners: GDriveOwner[];
  permissions: GDrivePermission[];
  capabilities: GDriveCapabilities;
  thumbnailLink?: string;
  fullFileExtension?: string;
  fileExtension?: string;
  md5Checksum?: string;
  spaces: string[];
  kind: string;
}

export interface GDriveFolder {
  id: string;
  name: string;
  mimeType: string;
  createdTime: string;
  modifiedTime: string;
  parents?: string[];
  webViewLink: string;
  trashed?: boolean;
  explicitlyTrashed?: boolean;
  owners: GDriveOwner[];
  permissions: GDrivePermission[];
  capabilities: GDriveCapabilities;
  spaces: string[];
  kind: string;
}

export interface GDriveOwner {
  displayName: string;
  emailAddress?: string;
  kind: string;
  permissionId: string;
  me?: boolean;
}

export interface GDrivePermission {
  id?: string;
  type: string;
  role: string;
  emailAddress?: string;
  displayName?: string;
  kind: string;
}

export interface GDriveCapabilities {
  canAddChildren?: boolean;
  canDelete?: boolean;
  canDownload?: boolean;
  canEdit?: boolean;
  canListChildren?: boolean;
  canRemoveChildren?: boolean;
  canRename?: boolean;
  canShare?: boolean;
}

export interface GDriveChanges {
  nextPageToken?: string;
  newStartPageToken?: string;
  changes: GDriveChange[];
}

export interface GDriveChange {
  fileId: string;
  removed?: boolean;
  file?: GDriveFile | GDriveFolder;
  kind: string;
  type: string;
}

export interface GDriveSearchResponse {
  files: (GDriveFile | GDriveFolder)[];
  nextPageToken?: string;
  incompleteSearch: boolean;
}

// Google Drive Configuration Types
export interface GDriveConfig extends AtomFileStorageConfig {
  // API Configuration
  apiBaseUrl: string;
  scopes: string[];
  
  // Google Drive-specific settings
  teamDriveId?: string;
  includeSharedDrives: boolean;
  includeTeamDrives: boolean;
  
  // File Processing
  useGoogleDocsExport: boolean;
  exportFormats: Record<string, string>;
  
  // Sync Settings
  includeTrashed: boolean;
  includeSharedFiles: boolean;
  includeSharedFolders: boolean;
  
  // Rate Limiting
  apiCallsPerSecond: number;
  batchRequests: boolean;
  
  // Platform-specific
  tauriCommands?: {
    downloadFile: string;
    exportFile: string;
  };
}

// Enhanced Types
export interface GDriveFileEnhanced extends GDriveFile {
  source: 'gdrive';
  discoveredAt: string;
  textExtracted?: boolean;
  previewGenerated?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
  exportFormat?: string;
}

export interface GDriveFolderEnhanced extends GDriveFolder {
  source: 'gdrive';
  fileCount?: number;
  totalSize?: number;
  discoveredAt: string;
}

// Component Props
export interface AtomGDriveManagerProps extends AtomIntegrationProps<GDriveConfig> {
  // Google Drive-specific events
  onFolderCreated?: (folder: GDriveFolder) => void;
  onFolderDeleted?: (folderId: string) => void;
  onFileUploaded?: (file: GDriveFile) => void;
  onFileDeleted?: (fileId: string) => void;
  onFileDownloaded?: (file: GDriveFile) => void;
  onFileShared?: (file: GDriveFile) => void;
}

export interface AtomGDriveDataSourceProps extends AtomIntegrationProps<GDriveConfig, AtomGDriveIngestionConfig> {
  // Ingestion-specific events
  onFileDiscovered?: (file: GDriveFileEnhanced) => void;
  onFolderDiscovered?: (folder: GDriveFolderEnhanced) => void;
}

// State Types
export interface AtomGDriveState extends AtomIntegrationState {
  files: GDriveFile[];
  folders: GDriveFolder[];
  currentFolder?: GDriveFolder;
  breadcrumb: GDriveFolder[];
  selectedItems: (GDriveFile | GDriveFolder)[];
  uploadProgress: Record<string, number>;
  downloadProgress: Record<string, number>;
  searchResults: (GDriveFile | GDriveFolder)[];
  sortBy: GDriveSortField;
  sortOrder: GDriveSortOrder;
  viewMode: 'grid' | 'list' | 'compact';
}

export interface AtomGDriveDataSourceState extends AtomIntegrationState {
  discoveredFiles: GDriveFileEnhanced[];
  discoveredFolders: GDriveFolderEnhanced[];
  ingestionQueue: GDriveFileEnhanced[];
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
export interface AtomGDriveIngestionConfig {
  sourceId: string;
  sourceName: string;
  sourceType: 'gdrive';
  
  // File Discovery
  supportedFileTypes: string[];
  supportedMimeTypes: string[];
  maxFileSize: number;
  excludePatterns: string[];
  includeSharedFiles: boolean;
  includeTrashed: boolean;
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  realTimeIngest: boolean;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Sync Settings
  syncInterval: number;
  incrementalSync: boolean;
  useChangeNotifications: boolean;
  pageToken?: string;
  
  // Processing
  extractMetadata: boolean;
  generatePreviews: boolean;
  extractText: boolean;
  useGoogleDocsExport: boolean;
  exportFormats: Record<string, string>;
  chunkSize: number;
  chunkOverlap: number;
  
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
export interface AtomGDriveAPI extends AtomIntegrationAPI<GDriveFile | GDriveFolder, GDriveConfig> {
  // File Operations
  getFiles: (folderId?: string, recursive?: boolean) => Promise<GDriveFile[]>;
  getFile: (fileId: string) => Promise<GDriveFile>;
  uploadFile: (file: File, folderId?: string) => Promise<GDriveFile>;
  downloadFile: (fileId: string, acknowledgeAbuse?: boolean) => Promise<Blob>;
  deleteFile: (fileId: string) => Promise<void>;
  exportFile: (fileId: string, mimeType: string) => Promise<Blob>;
  
  // Folder Operations
  createFolder: (name: string, parentId?: string) => Promise<GDriveFolder>;
  deleteFolder: (folderId: string) => Promise<void>;
  
  // Search Operations
  search: (query: string, options?: GDriveSearchOptions) => Promise<GDriveSearchResponse>;
  
  // Sync Operations
  getChanges: (pageToken?: string) => Promise<GDriveChanges>;
  
  // Utility Operations
  getPermission: (fileId: string, permissionId: string) => Promise<GDrivePermission>;
  createPermission: (fileId: string, permission: GDrivePermission) => Promise<GDrivePermission>;
  deletePermission: (fileId: string, permissionId: string) => Promise<void>;
  shareFile: (fileId: string, emailAddress: string, role?: string) => Promise<GDrivePermission>;
}

export interface GDriveSearchOptions {
  fields?: string;
  pageSize?: number;
  pageToken?: string;
  orderBy?: string;
  q?: string;
  corpora?: string;
  driveId?: string;
  includeItemsFromAllDrives?: boolean;
}

// Hook Types
export interface AtomGDriveHookReturn extends AtomIntegrationHookReturn<GDriveFile | GDriveFolder> {
  state: AtomGDriveState;
  api: AtomGDriveAPI;
  actions: AtomGDriveActions;
  config: GDriveConfig;
}

export interface AtomGDriveDataSourceHookReturn extends AtomIntegrationHookReturn<GDriveFileEnhanced> {
  state: AtomGDriveDataSourceState;
  api: AtomGDriveAPI;
  actions: AtomGDriveDataSourceActions;
  config: AtomGDriveIngestionConfig;
}

// Actions Types
export interface AtomGDriveActions {
  // File Actions
  uploadFiles: (files: FileList, folderId?: string) => Promise<GDriveFile[]>;
  downloadFile: (fileId: string) => Promise<void>;
  exportFile: (fileId: string, mimeType: string) => Promise<void>;
  deleteFiles: (fileIds: string[]) => Promise<void>;
  shareFile: (fileId: string, emailAddress: string, role?: string) => Promise<void>;
  
  // Folder Actions
  createFolder: (name: string, parentId?: string) => Promise<GDriveFolder>;
  deleteFolder: (folderId: string) => Promise<void>;
  
  // Navigation Actions
  navigateToFolder: (folder: GDriveFolder) => void;
  navigateUp: () => void;
  
  // Search Actions
  search: (query: string, options?: GDriveSearchOptions) => Promise<GDriveSearchResponse>;
  
  // UI Actions
  selectItems: (items: (GDriveFile | GDriveFolder)[]) => void;
  sortBy: (field: GDriveSortField, order: GDriveSortOrder) => void;
  setViewMode: (mode: 'grid' | 'list' | 'compact') => void;
  
  // Data Actions
  refresh: () => Promise<void>;
  clearSelection: () => void;
}

export interface AtomGDriveDataSourceActions {
  // Discovery Actions
  discoverFiles: (recursive?: boolean) => Promise<GDriveFileEnhanced[]>;
  discoverFolders: (recursive?: boolean) => Promise<GDriveFolderEnhanced[]>;
  
  // Ingestion Actions
  ingestFiles: (files: GDriveFileEnhanced[]) => Promise<void>;
  ingestFolder: (folderId: string, recursive?: boolean) => Promise<void>;
  
  // Sync Actions
  syncFiles: () => Promise<void>;
  
  // Data Source Actions
  registerDataSource: () => Promise<void>;
}

// Sort Types
export type GDriveSortField = 'name' | 'size' | 'createdTime' | 'modifiedTime' | 'mimeType' | 'kind';
export type GDriveSortOrder = 'asc' | 'desc';

// Error Types
export class AtomGDriveError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public endpoint?: string;
  public statusCode?: number;

  constructor(message: string, code: string, context?: Record<string, any>, endpoint?: string, statusCode?: number) {
    super(message);
    this.name = 'AtomGDriveError';
    this.code = code;
    this.context = context;
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

// Constants
export const gdriveConfigDefaults: Partial<GDriveConfig> = {
  apiBaseUrl: 'https://www.googleapis.com/drive/v3',
  scopes: [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.readonly'
  ],
  includeSharedDrives: true,
  includeTeamDrives: false,
  useGoogleDocsExport: true,
  exportFormats: {
    'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.google-apps.drawing': 'image/png',
    'application/vnd.google-apps.script': 'application/vnd.google-apps.script+json',
    'application/vnd.google-apps.site': 'text/html',
    'application/vnd.google-apps.form': 'application/pdf'
  },
  includeTrashed: false,
  includeSharedFiles: true,
  includeSharedFolders: false,
  apiCallsPerSecond: 100,
  batchRequests: true
};

export const gdriveIngestionConfigDefaults: Partial<AtomGDriveIngestionConfig> = {
  sourceId: 'gdrive-integration',
  sourceName: 'Google Drive',
  sourceType: 'gdrive',
  supportedFileTypes: [
    '.txt', '.md', '.pdf', '.doc', '.docx', 
    '.rtf', '.odt', '.html', '.htm', '.csv',
    '.json', '.xml', '.yaml', '.yml', '.log',
    '.js', '.ts', '.jsx', '.tsx', '.py', '.java',
    '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'
  ],
  supportedMimeTypes: [
    'text/plain',
    'text/markdown',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/rtf',
    'application/vnd.oasis.opendocument.text',
    'text/html',
    'text/csv',
    'application/json',
    'application/xml',
    'application/x-yaml',
    'text/x-log',
    'text/javascript',
    'text/typescript',
    'text/x-python',
    'text/x-java-source',
    'text/x-c',
    'text/x-c++',
    'text/x-csharp',
    'text/x-php',
    'text/x-ruby',
    'text/x-go',
    'text/x-rust'
  ],
  maxFileSize: 100 * 1024 * 1024, // 100MB
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
  batchSize: 50,
  maxConcurrentIngestions: 3,
  syncInterval: 300000, // 5 minutes
  incrementalSync: true,
  useChangeNotifications: true,
  extractMetadata: true,
  generatePreviews: true,
  extractText: true,
  useGoogleDocsExport: true,
  exportFormats: {
    'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  },
  chunkSize: 1000,
  chunkOverlap: 100,
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const gdriveSearchDefaults: GDriveSearchOptions = {
  fields: 'nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, thumbnailLink, fileExtension)',
  pageSize: 100,
  orderBy: 'modifiedTime desc',
  corpora: 'default',
  includeItemsFromAllDrives: false
};

export const gdriveSortFields: GDriveSortField[] = ['name', 'size', 'createdTime', 'modifiedTime', 'mimeType', 'kind'];
export const gdriveSortOrders: GDriveSortOrder[] = ['asc', 'desc'];

// Export types
export type { AtomIntegrationBase, AtomIntegrationProps, AtomIntegrationState, AtomFileStorageConfig, AtomIntegrationAPI, AtomIntegrationHookReturn } from '../../_template/baseIntegration';