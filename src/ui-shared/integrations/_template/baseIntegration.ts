/**
 * ATOM 3rd Party Integration Base Template
 * Cross-platform: Next.js & Tauri
 * Production: OAuth, API, Real-time Sync, Ingestion Pipeline
 */

// Base Types Template
export interface AtomIntegrationBase<T = any> {
  // Integration Identity
  id: string;
  name: string;
  type: 'file-storage' | 'messaging' | 'email' | 'document' | 'collaboration';
  platform: string; // 'dropbox', 'gdrive', 'slack', 'gmail', 'notion', etc.
  
  // Authentication
  authentication: {
    type: 'oauth2' | 'api-key' | 'basic';
    accessToken: string;
    refreshToken?: string;
    apiKey?: string;
    expiresAt?: Date;
  };
  
  // Configuration
  config: T;
  
  // Capabilities
  capabilities: {
    fileDiscovery: boolean;
    realTimeSync: boolean;
    ingestionPipeline: boolean;
    searchIntegration: boolean;
    webhookSupport: boolean;
    apiQuota: number;
    rateLimits: {
      requests: number;
      window: number; // milliseconds
    };
  };
  
  // Status
  status: 'active' | 'inactive' | 'error' | 'limited';
  lastUpdated: Date;
  error?: string;
  
  // Statistics
  stats: {
    totalItems: number;
    ingestedItems: number;
    failedIngestions: number;
    lastSyncTime: Date | null;
    dataProcessed: number; // bytes
    apiCalls: number;
    lastApiCall: Date | null;
  };
}

// Base Props Template
export interface AtomIntegrationProps<T = any, U = any> {
  // Authentication
  accessToken: string;
  refreshToken?: string;
  apiKey?: string;
  onTokenRefresh?: (refreshToken: string) => Promise<{ success: boolean; accessToken?: string; error?: string }>;
  
  // ATOM Pipeline Integration
  atomIngestionPipeline?: {
    registerDataSource: (dataSource: any) => Promise<void>;
    ingestBatch: (batch: any) => Promise<any>;
    getDataSourceStatus: (dataSourceId: string) => Promise<any>;
  };
  
  dataSourceRegistry?: {
    register: (dataSource: any) => Promise<void>;
    get: (dataSourceId: string) => Promise<any>;
    list: () => Promise<any[]>;
  };
  
  // Integration Configuration
  config?: Partial<T>;
  platform?: 'auto' | 'nextjs' | 'tauri';
  theme?: 'auto' | 'light' | 'dark';
  
  // Pipeline Configuration (for ingestion integrations)
  ingestionConfig?: Partial<U>;
  
  // Events
  onIntegrationReady?: (integration: AtomIntegrationBase<T>) => void;
  onIngestionStart?: (job: any) => void;
  onIngestionComplete?: (job: any) => void;
  onIngestionProgress?: (progress: any) => void;
  onIntegrationError?: (error: string, context: string) => void;
  
  // Children (for render prop pattern)
  children?: (props: any) => React.ReactNode;
}

// Base State Template
export interface AtomIntegrationState {
  initialized: boolean;
  connected: boolean;
  loading: boolean;
  error: string | null;
  
  // Integration-specific state
  data: any[];
  selectedItem: any;
  searchResults: any[];
  
  // Ingestion state (for data sources)
  ingestionStatus: 'idle' | 'processing' | 'completed' | 'failed';
  lastIngestionTime: Date | null;
  discoveredItems: any[];
  processingIngestion: boolean;
  
  // Sync state
  syncStatus: 'idle' | 'syncing' | 'synced' | 'error';
  lastSyncTime: Date | null;
  
  // Platform state
  isDesktop: boolean;
  currentPlatform: 'nextjs' | 'tauri';
}

// Base Configuration Templates
export interface AtomFileStorageConfig {
  // File Discovery
  supportedFileTypes: string[];
  maxFileSize: number;
  excludePatterns: string[];
  
  // Ingestion Pipeline
  ingestionEnabled: boolean;
  autoIngest: boolean;
  ingestInterval: number;
  realTimeIngest: boolean;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Sync Settings
  syncInterval: number;
  incrementalSync: boolean;
  fullSyncInterval: number;
  
  // Processing
  extractMetadata: boolean;
  generatePreviews: boolean;
  extractText: boolean;
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

export interface AtomMessagingConfig {
  // Message Discovery
  ingestionEnabled: boolean;
  messageTypes: string[];
  channels: string[];
  users: string[];
  dateRange: {
    start: Date;
    end: Date;
  };
  
  // Ingestion Pipeline
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
  
  // Pipeline Integration
  pipelineConfig: {
    targetTable: string;
    embeddingModel: string;
    embeddingDimension: number;
    indexType: string;
    numPartitions: number;
  };
}

export interface AtomEmailConfig {
  // Email Discovery
  ingestionEnabled: boolean;
  folders: string[];
  dateRange: {
    start: Date;
    end: Date;
  };
  includeAttachments: boolean;
  
  // Ingestion Pipeline
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
  
  // Pipeline Integration
  pipelineConfig: {
    targetTable: string;
    embeddingModel: string;
    embeddingDimension: number;
    indexType: string;
    numPartitions: number;
  };
}

// Base API Template
export interface AtomIntegrationAPI<T = any, U = any> {
  // Authentication
  authenticate: (credentials: any) => Promise<boolean>;
  refreshToken: (refreshToken: string) => Promise<{ success: boolean; accessToken?: string; error?: string }>;
  
  // Data Operations
  discover: (options?: any) => Promise<T[]>;
  getItem: (id: string) => Promise<T>;
  search: (query: string, options?: any) => Promise<T[]>;
  download: (id: string) => Promise<Blob>;
  
  // Sync Operations
  getChanges: (since?: Date) => Promise<any[]>;
  
  // Platform-specific operations
  platformOperations: any;
}

// Base Hook Template
export interface AtomIntegrationHookReturn<T = any> {
  state: AtomIntegrationState;
  api: AtomIntegrationAPI<T>;
  actions: {
    connect: () => Promise<void>;
    disconnect: () => Promise<void>;
    refresh: () => Promise<void>;
    search: (query: string) => Promise<T[]>;
    selectItem: (item: T) => void;
    ingest: (items?: T[]) => Promise<void>;
    sync: () => Promise<void>;
  };
  config: T;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

// Default Configuration Templates
export const defaultFileStorageConfig: AtomFileStorageConfig = {
  supportedFileTypes: [
    '.txt', '.md', '.pdf', '.doc', '.docx', 
    '.rtf', '.odt', '.html', '.htm', '.csv',
    '.json', '.xml', '.yaml', '.yml', '.log',
    '.js', '.ts', '.jsx', '.tsx', '.py', '.java',
    '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'
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
  ingestionEnabled: true,
  autoIngest: true,
  ingestInterval: 3600000, // 1 hour
  realTimeIngest: true,
  batchSize: 50,
  maxConcurrentIngestions: 3,
  syncInterval: 300000, // 5 minutes
  incrementalSync: true,
  fullSyncInterval: 86400000, // 24 hours
  extractMetadata: true,
  generatePreviews: false,
  extractText: true,
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

export const defaultMessagingConfig: AtomMessagingConfig = {
  ingestionEnabled: true,
  messageTypes: ['message', 'file_share', 'reaction'],
  channels: [],
  users: [],
  dateRange: {
    start: new Date(Date.now() - 30 * 24 * 3600 * 1000), // 30 days ago
    end: new Date()
  },
  autoIngest: true,
  ingestInterval: 600000, // 10 minutes
  batchSize: 100,
  maxConcurrentIngestions: 5,
  extractMentions: true,
  extractLinks: true,
  extractAttachments: true,
  extractEmojis: false,
  parseMarkdown: true,
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

export const defaultEmailConfig: AtomEmailConfig = {
  ingestionEnabled: true,
  folders: ['INBOX', 'SENT'],
  dateRange: {
    start: new Date(Date.now() - 30 * 24 * 3600 * 1000), // 30 days ago
    end: new Date()
  },
  includeAttachments: true,
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
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

// Platform Detection Utility
export const detectPlatform = (): 'nextjs' | 'tauri' => {
  if (typeof window !== 'undefined' && (window as any).__TAURI__) {
    return 'tauri';
  }
  return 'nextjs';
};

// Theme Resolution Utility
export const resolveTheme = (theme: 'auto' | 'light' | 'dark'): 'light' | 'dark' => {
  if (theme === 'auto') {
    return (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  }
  return theme;
};

// Error Class Template
export class AtomIntegrationError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public platform?: string;
  public integrationId?: string;

  constructor(message: string, code: string, context?: Record<string, any>, platform?: string, integrationId?: string) {
    super(message);
    this.name = 'AtomIntegrationError';
    this.code = code;
    this.context = context;
    this.platform = platform;
    this.integrationId = integrationId;
  }
}

// Utility Functions Template
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle: boolean;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
};

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const formatDate = (date: Date | string): string => {
  const d = new Date(date);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
};

export const extractFileExtension = (fileName: string): string => {
  const parts = fileName.split('.');
  return parts.length > 1 ? '.' + parts.pop()!.toLowerCase() : '';
};

export const isFileTypeSupported = (fileName: string, supportedTypes: string[]): boolean => {
  const extension = extractFileExtension(fileName);
  return supportedTypes.includes(extension);
};

export const sanitizeFileName = (fileName: string): string => {
  return fileName.replace(/[^\w\s.-]/gi, '').trim();
};

export const generateId = (): string => {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
};

// Export all templates
export * from './types';
export * from './hooks';
export * from './utils';