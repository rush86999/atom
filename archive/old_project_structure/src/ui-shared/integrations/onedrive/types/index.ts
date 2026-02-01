/**
 * ATOM OneDrive Integration Types
 * File Storage → ATOM Ingestion Pipeline
 * Microsoft Graph API Integration
 */

export interface OneDriveFile {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  webUrl: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  parentReference: {
    id?: string;
    path?: string;
    driveId?: string;
    driveType?: string;
  };
  file?: {
    mimeType: string;
    hashes: {
      sha1Hash?: string;
      sha256Hash?: string;
      quickXorHash?: string;
    };
  };
  folder?: {
    childCount?: number;
  };
  package?: {
    type: string;
  };
  shared?: {
    scope?: string;
    owner?: {
      user?: {
        displayName: string;
        email: string;
      };
    };
  };
  deleted?: {
    state: string;
  };
  '@microsoft.graph.downloadUrl'?: string;
}

export interface OneDriveFolder {
  id: string;
  name: string;
  webUrl: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  parentReference: OneDriveFile['parentReference'];
  folder: {
    childCount: number;
    view?: {
      viewType: string;
      sortBy: string[];
    };
  };
  size: number;
}

export interface OneDriveSearchResult {
  '@odata.context': string;
  '@odata.nextLink'?: string;
  '@odata.count'?: number;
  value: OneDriveFile[];
}

export interface OneDriveUploadSession {
  '@odata.context': string;
  uploadUrl: string;
  expirationDateTime: string;
  nextExpectedRanges: string[];
}

export interface OneDriveDeltaResponse {
  '@odata.context': string;
  '@odata.nextLink'?: string;
  '@odata.deltaLink'?: string;
  value: (OneDriveFile | OneDriveFolder)[];
}

// ATOM Integration Types
export interface AtomOneDriveDataSourceProps {
  // Microsoft Graph Authentication
  accessToken: string;
  refreshToken?: string;
  onTokenRefresh?: (newToken: string) => void;
  tenantId?: string;
  
  // Existing ATOM Pipeline Integration
  atomIngestionPipeline?: any;
  dataSourceRegistry?: any;
  
  // Data Source Configuration
  config?: AtomOneDriveIngestionConfig;
  platform?: 'auto' | 'web' | 'desktop';
  theme?: 'auto' | 'light' | 'dark';
  
  // Events
  onDataSourceReady?: (dataSource: any) => void;
  onIngestionStart?: (config: any) => void;
  onIngestionComplete?: (results: any) => void;
  onIngestionProgress?: (progress: any) => void;
  onDataSourceError?: (error: any) => void;
  onFileProcessed?: (file: OneDriveFile) => void;
  onFolderProcessed?: (folder: OneDriveFolder) => void;
  
  // Children
  children?: React.ReactNode;
}

export interface AtomOneDriveDataSourceState {
  initialized: boolean;
  connected: boolean;
  loading: boolean;
  error: string | null;
  
  // OneDrive State
  driveInfo: {
    id: string;
    driveType: string;
    owner: {
      user: {
        displayName: string;
        email: string;
        id: string;
      };
    };
    quota: {
      total: number;
      used: number;
      remaining: number;
      deleted: number;
    };
  } | null;
  
  // File/Folder State
  files: OneDriveFile[];
  folders: OneDriveFolder[];
  currentFolder: OneDriveFolder | null;
  searchResults: OneDriveFile[];
  
  // Ingestion State
  ingestionActive: boolean;
  ingestionProgress: {
    total: number;
    processed: number;
    percentage: number;
    currentFile?: string;
  };
  ingestionResults: any[];
  
  // Sync State
  lastSync: string | null;
  deltaToken: string | null;
  syncActive: boolean;
}

export interface AtomOneDriveIngestionConfig {
  // File Filtering
  includeFileTypes?: string[];
  excludeFileTypes?: string[];
  maxFileSize?: number;
  includeHiddenFiles?: boolean;
  excludeSystemFiles?: boolean;
  
  // Folder Configuration
  rootFolder?: string;
  includeSubfolders?: boolean;
  excludedFolderNames?: string[];
  
  // Sync Configuration
  enableRealTimeSync?: boolean;
  syncInterval?: number;
  incrementalSync?: boolean;
  
  // Processing Configuration
  extractMetadata?: boolean;
  generatePreviews?: boolean;
  extractTextContent?: boolean;
  
  // Content Extraction
  processGoogleDocs?: boolean;
  processSpreadsheets?: boolean;
  processPresentations?: boolean;
  processImages?: boolean;
  processVideos?: boolean;
  processAudioFiles?: boolean;
  
  // Batch Processing
  batchSize?: number;
  concurrentProcessing?: boolean;
  maxConcurrency?: number;
  
  // Advanced Configuration
  webhookId?: string;
  changeTrackingEnabled?: boolean;
  retryFailedUploads?: boolean;
  maxRetries?: number;
  
  // Notifications
  enableNotifications?: boolean;
  notificationChannels?: string[];
}

// Enhanced File Types
export interface OneDriveFileEnhanced extends OneDriveFile {
  // ATOM Enhanced Metadata
  atomId: string;
  atomTimestamp: string;
  atomSource: 'onedrive';
  atomProcessed: boolean;
  atomIngestionId?: string;
  
  // Content Extraction Results
  extractedText?: string;
  extractedMetadata?: {
    title?: string;
    author?: string;
    created?: string;
    modified?: string;
    keywords?: string[];
    language?: string;
    wordCount?: number;
    pageCount?: number;
  };
  
  // Processing Status
  processingStatus: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  processingError?: string;
  processingAttempts: number;
  
  // Preview Information
  previewUrl?: string;
  thumbnailUrl?: string;
  previewGenerated: boolean;
  
  // Search Enhancement
  searchVector?: number[];
  searchKeywords?: string[];
  searchRank?: number;
  
  // Sync Information
  lastSynced?: string;
  syncVersion?: string;
  syncStatus: 'synced' | 'pending' | 'conflict' | 'error';
  deltaToken?: string;
}

export interface OneDriveUser {
  id: string;
  displayName: string;
  email: string;
  userPrincipalName: string;
  jobTitle?: string;
  department?: string;
  officeLocation?: string;
  businessPhones?: string[];
  mobilePhone?: string;
}

export interface OneDrivePermission {
  id: string;
  grantedTo?: {
    user?: OneDriveUser;
    application?: {
      id: string;
      displayName: string;
    };
  };
  roles: string[];
  hasPassword?: boolean;
  expirationDateTime?: string;
}

// Event Types
export interface OneDriveChangeEvent {
  type: 'created' | 'updated' | 'deleted' | 'renamed' | 'moved';
  itemId: string;
  itemType: 'file' | 'folder';
  itemName: string;
  itemPath: string;
  timestamp: string;
  userId?: string;
  oldPath?: string;
  oldName?: string;
  parentFolderId?: string;
  oldParentFolderId?: string;
}

export interface OneDriveUploadProgress {
  file: OneDriveFile;
  progress: number;
  bytesUploaded: number;
  totalBytes: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
}

export interface OneDriveSearchQuery {
  query?: string;
  fileTypes?: string[];
  dateRange?: {
    from: string;
    to: string;
  };
  sizeRange?: {
    min: number;
    max: number;
  };
  folderId?: string;
  includeSubfolders?: boolean;
  sortBy?: 'name' | 'size' | 'createdDateTime' | 'lastModifiedDateTime';
  sortOrder?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// API Response Types
export interface OneDriveAPIResponse<T = any> {
  '@odata.context': string;
  '@odata.nextLink'?: string;
  '@odata.count'?: number;
  '@odata.deltaLink'?: string;
  value: T;
}

export interface OneDriveUploadResponse {
  id: string;
  name: string;
  size: number;
  webUrl: string;
  createdDateTime: string;
  lastModifiedDateTime: string;
  '@microsoft.graph.downloadUrl': string;
}

// Error Types
export interface OneDriveError {
  error: {
    code: string;
    message: string;
    innerError?: {
      code: string;
      message: string;
      date: string;
      request-id: string;
      client-request-id: string;
    };
  };
}

export interface OneDriveAPIError {
  code: string;
  message: string;
  requestPath?: string;
  timestamp?: string;
  requestId?: string;
  clientRequestId?: string;
}

// Constants
export const ONEDRIVE_DEFAULT_CONFIG: AtomOneDriveIngestionConfig = {
  includeFileTypes: [
    'text/plain',
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
    'image/webp'
  ],
  excludeFileTypes: [
    'application/x-executable',
    'application/x-msdownload',
    'application/x-msdos-program'
  ],
  maxFileSize: 100 * 1024 * 1024, // 100MB
  includeHiddenFiles: false,
  excludeSystemFiles: true,
  includeSubfolders: true,
  excludedFolderNames: ['$Recycle.Bin', 'Documents', 'Desktop', 'Downloads'],
  enableRealTimeSync: true,
  syncInterval: 5 * 60 * 1000, // 5 minutes
  incrementalSync: true,
  extractMetadata: true,
  generatePreviews: true,
  extractTextContent: true,
  processGoogleDocs: true,
  processSpreadsheets: true,
  processPresentations: true,
  processImages: true,
  processVideos: false,
  processAudioFiles: false,
  batchSize: 50,
  concurrentProcessing: true,
  maxConcurrency: 5,
  changeTrackingEnabled: true,
  retryFailedUploads: true,
  maxRetries: 3,
  enableNotifications: true
};

export const ONEDRIVE_SUPPORTED_FILE_TYPES = {
  'text/plain': {
    category: 'document',
    extractable: true,
    previewable: true
  },
  'application/pdf': {
    category: 'document',
    extractable: true,
    previewable: true
  },
  'application/msword': {
    category: 'document',
    extractable: true,
    previewable: true
  },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
    category: 'document',
    extractable: true,
    previewable: true
  },
  'application/vnd.ms-excel': {
    category: 'spreadsheet',
    extractable: true,
    previewable: true
  },
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
    category: 'spreadsheet',
    extractable: true,
    previewable: true
  },
  'application/vnd.ms-powerpoint': {
    category: 'presentation',
    extractable: true,
    previewable: true
  },
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': {
    category: 'presentation',
    extractable: true,
    previewable: true
  },
  'image/jpeg': {
    category: 'image',
    extractable: false,
    previewable: true
  },
  'image/png': {
    category: 'image',
    extractable: false,
    previewable: true
  },
  'image/gif': {
    category: 'image',
    extractable: false,
    previewable: true
  },
  'image/webp': {
    category: 'image',
    extractable: false,
    previewable: true
  }
} as const;