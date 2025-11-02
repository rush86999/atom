/**
 * ATOM Box Integration - Enhanced Types for Data Source
 * Cross-platform: Next.js & Tauri
 * Data Source Integration for ATOM Agent Ingestion Pipeline
 */

// Re-export all existing types
export * from './index';

// Enhanced Data Source Types
export interface AtomBoxDataSource {
  id: string;
  name: string;
  type: string;
  platform: 'box';
  config: AtomBoxIngestionConfig;
  authentication: {
    type: 'oauth2';
    accessToken: string;
    refreshToken?: string;
  };
  capabilities: {
    fileDiscovery: boolean;
    realTimeSync: boolean;
    incrementalSync: boolean;
    batchProcessing: boolean;
    metadataExtraction: boolean;
    previewGeneration: boolean;
    textExtraction: boolean;
  };
  status: 'active' | 'inactive' | 'error';
  createdAt: Date;
  lastUpdated: Date;
}

export interface AtomBoxDataSourceProps {
  // Box Authentication
  accessToken: string;
  refreshToken?: string;
  onTokenRefresh?: (refreshToken: string) => Promise<{ success: boolean; accessToken?: string; error?: string }>;
  
  // Existing ATOM Pipeline Integration
  atomIngestionPipeline?: {
    registerDataSource: (dataSource: AtomBoxDataSource) => Promise<void>;
    ingestBatch: (batch: AtomIngestionBatch) => Promise<AtomIngestionBatchResult>;
    getDataSourceStatus: (dataSourceId: string) => Promise<AtomDataSourceStatus>;
  };
  
  dataSourceRegistry?: {
    register: (dataSource: AtomBoxDataSource) => Promise<void>;
    get: (dataSourceId: string) => Promise<AtomBoxDataSource | null>;
    list: () => Promise<AtomBoxDataSource[]>;
  };
  
  // Data Source Configuration
  config?: Partial<AtomBoxIngestionConfig>;
  platform?: 'auto' | 'nextjs' | 'tauri';
  theme?: 'auto' | 'light' | 'dark';
  
  // Pipeline Events
  onDataSourceReady?: (dataSource: AtomBoxDataSource) => void;
  onIngestionStart?: (job: AtomIngestionJob) => void;
  onIngestionComplete?: (job: AtomIngestionJob) => void;
  onIngestionProgress?: (progress: AtomIngestionProgress) => void;
  onDataSourceError?: (error: string, context: string) => void;
  
  // Children
  children?: (props: AtomBoxDataSourceRenderProps) => React.ReactNode;
}

export interface AtomBoxDataSourceState {
  initialized: boolean;
  connected: boolean;
  loading: boolean;
  error: string | null;
  dataSource: AtomBoxDataSource | null;
  ingestionStatus: 'idle' | 'processing' | 'completed' | 'failed';
  lastIngestionTime: Date | null;
  discoveredFiles: BoxFile[];
  ingestionQueue: BoxFile[];
  processingIngestion: boolean;
  stats: AtomBoxDataSourceStats;
}

export interface AtomBoxDataSourceStats {
  totalFiles: number;
  ingestedFiles: number;
  failedIngestions: number;
  lastSyncTime: Date | null;
  dataSize: number;
}

export interface AtomBoxIngestionConfig {
  // Data Source Identity
  sourceId: string;
  sourceName: string;
  sourceType: string;
  
  // File Discovery
  supportedFileTypes: string[];
  maxFileSize: number;
  excludePatterns: string[];
  
  // Ingestion Settings
  autoIngest: boolean;
  ingestInterval: number;
  realTimeIngest: boolean;
  batchSize: number;
  maxConcurrentIngestions: number;
  
  // Sync Settings
  syncInterval: number;
  fullSyncInterval: number;
  incrementalSync: boolean;
  
  // Processing
  extractMetadata: boolean;
  generatePreviews: boolean;
  extractText: boolean;
  chunkSize: number;
  chunkOverlap: number;
  
  // Existing Pipeline Integration
  pipelineConfig: {
    targetTable: string;
    embeddingModel: string;
    embeddingDimension: number;
    indexType: string;
    numPartitions: number;
  };
}

export interface AtomBoxDataSourceRenderProps {
  state: AtomBoxDataSourceState;
  actions: {
    discoverFiles: (fullDiscovery?: boolean) => Promise<BoxFile[]>;
    ingestFiles: (files: BoxFile[]) => Promise<void>;
    syncFiles: () => Promise<void>;
    registerDataSource: () => Promise<void>;
  };
  config: AtomBoxIngestionConfig;
  dataSource: AtomBoxDataSource | null;
}

// Ingestion Pipeline Types
export interface AtomIngestionBatch {
  dataSourceId: string;
  items: AtomIngestionItem[];
  config: AtomBoxIngestionConfig['pipelineConfig'];
}

export interface AtomIngestionItem {
  id: string;
  sourceId: string;
  sourceName: string;
  sourceType: string;
  fileName: string;
  filePath: string;
  contentType?: string;
  size?: number;
  createdAt?: string;
  modifiedAt?: string;
  metadata: {
    boxMetadata?: any;
    extractedMetadata?: any;
    content?: string;
  };
  content: string;
  chunkSize?: number;
  chunkOverlap?: number;
}

export interface AtomIngestionBatchResult {
  successful: number;
  failed: number;
  errors: string[];
  results: AtomIngestionItemResult[];
}

export interface AtomIngestionItemResult {
  itemId: string;
  success: boolean;
  error?: string;
  documentId?: string;
  vectorCount?: number;
}

export interface AtomDataSourceStatus {
  dataSourceId: string;
  status: 'active' | 'inactive' | 'error';
  lastIngestionTime?: Date;
  totalDocuments: number;
  totalVectors: number;
  errors: string[];
  config: AtomBoxIngestionConfig;
}

// Enhanced Search and Query Types
export interface AtomBoxQuery {
  query: string;
  dataSourceId?: string;
  filters?: AtomBoxQueryFilter[];
  limit?: number;
  offset?: number;
  includeContent?: boolean;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface AtomBoxQueryFilter {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'contains';
  value: any;
}

export interface AtomBoxSearchResult {
  id: string;
  sourceId: string;
  fileName: string;
  filePath: string;
  contentType?: string;
  relevanceScore: number;
  metadata: any;
  content?: string;
  chunkId?: string;
  chunkIndex?: number;
}

// Box Event Types for Real-time Sync
export interface BoxEvent {
  id: string;
  type: 'ITEM_UPLOAD' | 'ITEM_UPDATE' | 'ITEM_MOVE' | 'ITEM_COPY' | 'ITEM_TRASH' | 'ITEM_UNTRASH';
  created_at: string;
  created_by: BoxEventUser;
  source: BoxEventSource;
  details?: Record<string, any>;
}

export interface BoxEventUser {
  id: string;
  type: 'user';
  name: string;
  login: string;
}

export interface BoxEventSource {
  id: string;
  type: 'file' | 'folder';
  name: string;
  parent?: {
    id: string;
    type: 'folder';
    name: string;
  };
}

// Enhanced File Metadata
export interface BoxFileEnhanced extends BoxFile {
  source: 'box';
  discoveredAt: string;
  path?: string;
  textExtracted?: boolean;
  previewGenerated?: boolean;
  embeddingGenerated?: boolean;
  ingested?: boolean;
  ingestionTime?: string;
  documentId?: string;
  vectorCount?: number;
}

// Cache Types
export interface AtomBoxCache {
  files: Map<string, BoxFileEnhanced>;
  folders: Map<string, BoxFolder>;
  metadata: Map<string, any>;
  embeddings: Map<string, number[]>;
  lastSync: Map<string, Date>;
  vectorIndex: AtomVectorIndex;
}

export interface AtomVectorIndex {
  totalDocuments: number;
  totalVectors: number;
  lastIndexed: Date | null;
  indexingActive: boolean;
  dimension: number;
  indexType: string;
}

// Configuration Templates
export const defaultBoxIngestionConfig: AtomBoxIngestionConfig = {
  // Data Source Identity
  sourceId: 'box-integration',
  sourceName: 'Box',
  sourceType: 'cloud-storage',
  
  // File Discovery
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
  
  // Ingestion Settings
  autoIngest: true,
  ingestInterval: 3600000, // 1 hour
  realTimeIngest: true,
  batchSize: 50,
  maxConcurrentIngestions: 3,
  
  // Sync Settings
  syncInterval: 300000, // 5 minutes
  fullSyncInterval: 86400000, // 24 hours
  incrementalSync: true,
  
  // Processing
  extractMetadata: true,
  generatePreviews: false,
  extractText: true,
  chunkSize: 1000,
  chunkOverlap: 100,
  
  // Existing Pipeline Integration
  pipelineConfig: {
    targetTable: 'atom_memory',
    embeddingModel: 'text-embedding-3-large',
    embeddingDimension: 3072,
    indexType: 'IVF_FLAT',
    numPartitions: 256
  }
};

// Query Templates
export const boxQueryTemplates = {
  recentFiles: {
    query: '',
    filters: [
      { field: 'modifiedAt', operator: 'gte', value: new Date(Date.now() - 24 * 3600 * 1000).toISOString() }
    ],
    sortBy: 'modifiedAt',
    sortOrder: 'desc' as const,
    limit: 50
  },
  
  largeFiles: {
    query: '',
    filters: [
      { field: 'size', operator: 'gte', value: 10 * 1024 * 1024 } // 10MB
    ],
    sortBy: 'size',
    sortOrder: 'desc' as const,
    limit: 50
  },
  
  documentsOnly: {
    query: '',
    filters: [
      { field: 'contentType', operator: 'in', value: ['application/pdf', 'application/msword', 'text/plain'] }
    ],
    sortBy: 'modifiedAt',
    sortOrder: 'desc' as const,
    limit: 100
  },
  
  codeFiles: {
    query: '',
    filters: [
      { field: 'extension', operator: 'in', value: ['.js', '.ts', '.py', '.java', '.cpp', '.go', '.rs'] }
    ],
    sortBy: 'modifiedAt',
    sortOrder: 'desc' as const,
    limit: 100
  }
};

// Error Types
export class AtomBoxDataSourceError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public sourceId?: string;

  constructor(message: string, code: string, context?: Record<string, any>, sourceId?: string) {
    super(message);
    this.name = 'AtomBoxDataSourceError';
    this.code = code;
    this.context = context;
    this.sourceId = sourceId;
  }
}

// Status Enums
export enum BoxDataSourceStatus {
  INITIALIZING = 'initializing',
  CONNECTED = 'connected',
  REGISTERED = 'registered',
  INGESTING = 'ingesting',
  ERROR = 'error',
  DISCONNECTED = 'disconnected'
}

export enum BoxIngestionStatus {
  IDLE = 'idle',
  DISCOVERING = 'discovering',
  INGESTING = 'ingesting',
  COMPLETED = 'completed',
  FAILED = 'failed',
  PAUSED = 'paused'
}

// Utility Types
export type BoxDataSourceEventListener = (event: AtomBoxDataSourceEvent) => void;

export interface AtomBoxDataSourceEvent {
  type: 'discovery_started' | 'discovery_completed' | 'ingestion_started' | 'ingestion_completed' | 
        'ingestion_progress' | 'sync_started' | 'sync_completed' | 'error' | 'connected' | 'disconnected';
  dataSourceId: string;
  timestamp: Date;
  data?: any;
}

// Export enhanced default configuration
export { defaultAtomBoxConfig } from './index';