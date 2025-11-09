/**
 * ATOM OneDrive Integration Index
 * Main export file for OneDrive integration components
 * Microsoft Graph API integration with ATOM ingestion pipeline
 */

// Component exports
export { default as OneDriveIntegration } from './OneDriveIntegration';
export { default as OneDriveManager, AtomOneDriveManager } from './OneDriveManager';
export { OneDriveSkillsBundle } from './skills/oneDriveSkills';

// Re-export types
export type {
  OneDriveFile,
  OneDriveFolder,
  OneDriveSearchResult,
  OneDriveUploadSession,
  OneDriveDeltaResponse,
  AtomOneDriveDataSourceProps,
  AtomOneDriveDataSourceState,
  AtomOneDriveIngestionConfig,
  OneDriveFileEnhanced,
  OneDriveUser,
  OneDrivePermission,
  OneDriveChangeEvent,
  OneDriveUploadProgress,
  OneDriveSearchQuery,
  OneDriveAPIResponse,
  OneDriveUploadResponse,
  OneDriveError,
  OneDriveAPIError,
} from './types';

// Re-export constants
export {
  ONEDRIVE_DEFAULT_CONFIG,
  ONEDRIVE_SUPPORTED_FILE_TYPES,
} from './types';

// Utility functions
export const OneDriveUtils = {
  /**
   * Format file size in human-readable format
   */
  formatFileSize: (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  /**
   * Get file icon based on MIME type
   */
  getFileIcon: (mimeType: string): string => {
    const type = mimeType.toLowerCase();
    if (type.includes('pdf')) return '📄';
    if (type.includes('word') || type.includes('document')) return '📝';
    if (type.includes('excel') || type.includes('spreadsheet')) return '📊';
    if (type.includes('powerpoint') || type.includes('presentation')) return '📈';
    if (type.includes('image')) return '🖼️';
    if (type.includes('video')) return '🎥';
    if (type.includes('audio')) return '🎵';
    if (type.includes('zip') || type.includes('compressed')) return '🗜️';
    return '📄';
  },

  /**
   * Check if file type is supported for text extraction
   */
  isTextExtractable: (mimeType: string): boolean => {
    const extractableTypes = [
      'text/plain',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    ];
    return extractableTypes.includes(mimeType);
  },

  /**
   * Check if file type supports preview generation
   */
  isPreviewable: (mimeType: string): boolean => {
    const previewableTypes = [
      'text/plain',
      'application/pdf',
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/webp',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    return previewableTypes.includes(mimeType);
  },

  /**
   * Get file category from MIME type
   */
  getFileCategory: (mimeType: string): string => {
    const type = mimeType.toLowerCase();
    if (type.includes('text')) return 'document';
    if (type.includes('pdf')) return 'document';
    if (type.includes('word') || type.includes('document')) return 'document';
    if (type.includes('excel') || type.includes('spreadsheet')) return 'spreadsheet';
    if (type.includes('powerpoint') || type.includes('presentation')) return 'presentation';
    if (type.includes('image')) return 'image';
    if (type.includes('video')) return 'video';
    if (type.includes('audio')) return 'audio';
    if (type.includes('zip') || type.includes('compressed')) return 'archive';
    return 'other';
  },

  /**
   * Validate OneDrive file ID format
   */
  isValidFileId: (fileId: string): boolean => {
    // OneDrive file IDs are typically base64-encoded strings
    return typeof fileId === 'string' && fileId.length > 0 && fileId.length < 1000;
  },

  /**
   * Extract file extension from filename
   */
  getFileExtension: (fileName: string): string => {
    const lastDot = fileName.lastIndexOf('.');
    return lastDot > -1 ? fileName.slice(lastDot + 1).toLowerCase() : '';
  },

  /**
   * Sanitize filename for safe usage
   */
  sanitizeFileName: (fileName: string): string => {
    // Remove or replace invalid characters
    return fileName
      .replace(/[<>:"/\\|?*]/g, '_')
      .replace(/\s+/g, ' ')
      .trim();
  },

  /**
   * Calculate estimated processing time based on file size
   */
  estimateProcessingTime: (fileSizeBytes: number): number => {
    // Rough estimate: 1MB takes ~1 second to process
    return Math.max(1000, fileSizeBytes / (1024 * 1024) * 1000);
  },

  /**
   * Check if file size is within limits
   */
  isFileSizeValid: (fileSizeBytes: number, maxSizeBytes: number = 100 * 1024 * 1024): boolean => {
    return fileSizeBytes > 0 && fileSizeBytes <= maxSizeBytes;
  },

  /**
   * Create search query for Microsoft Graph API
   */
  createSearchQuery: (options: {
    query?: string;
    fileTypes?: string[];
    dateRange?: { from?: string; to?: string };
    sizeRange?: { min?: number; max?: number };
  }): string => {
    let searchQuery = options.query || '';
    const filters: string[] = [];

    // Add file type filters
    if (options.fileTypes && options.fileTypes.length > 0) {
      const fileFilter = options.fileTypes.map(type => `fileType:'${type}'`).join(' OR ');
      searchQuery += ` ${fileFilter}`;
    }

    // Add date range filters
    if (options.dateRange?.from) {
      filters.push(`lastModifiedDateTime ge ${options.dateRange.from}`);
    }
    if (options.dateRange?.to) {
      filters.push(`lastModifiedDateTime le ${options.dateRange.to}`);
    }

    // Add size range filters
    if (options.sizeRange?.min) {
      filters.push(`size ge ${options.sizeRange.min}`);
    }
    if (options.sizeRange?.max) {
      filters.push(`size le ${options.sizeRange.max}`);
    }

    return {
      searchQuery: searchQuery.trim(),
      filters: filters.join(' and '),
    };
  },

  /**
   * Parse OneDrive API error response
   */
  parseError: (error: any): { code: string; message: string; details?: any } => {
    if (error?.error) {
      return {
        code: error.error.code || 'UNKNOWN_ERROR',
        message: error.error.message || 'An unknown error occurred',
        details: error.error.innerError,
      };
    }

    if (typeof error === 'string') {
      return {
        code: 'UNKNOWN_ERROR',
        message: error,
      };
    }

    return {
      code: 'UNKNOWN_ERROR',
      message: error?.message || 'An unknown error occurred',
      details: error,
    };
  },

  /**
   * Generate unique upload session ID
   */
  generateUploadSessionId: (): string => {
    return `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  },

  /**
   * Calculate sync progress percentage
   */
  calculateProgress: (processed: number, total: number): number => {
    if (total === 0) return 0;
    return Math.round((processed / total) * 100);
  },

  /**
   * Get human-readable sync status
   */
  getSyncStatusText: (status: string): string => {
    const statusMap: Record<string, string> = {
      'idle': 'Idle',
      'running': 'Syncing...',
      'paused': 'Paused',
      'completed': 'Completed',
      'failed': 'Failed',
      'cancelled': 'Cancelled',
    };
    return statusMap[status] || status;
  },

  /**
   * Validate OneDrive configuration
   */
  validateConfig: (config: Partial<AtomOneDriveIngestionConfig>): {
    isValid: boolean;
    errors: string[];
  } => {
    const errors: string[] = [];

    if (config.maxFileSize && config.maxFileSize <= 0) {
      errors.push('Max file size must be greater than 0');
    }

    if (config.batchSize && (config.batchSize < 1 || config.batchSize > 1000)) {
      errors.push('Batch size must be between 1 and 1000');
    }

    if (config.maxRetries && config.maxRetries < 0) {
      errors.push('Max retries cannot be negative');
    }

    if (config.syncInterval && config.syncInterval < 60000) {
      errors.push('Sync interval must be at least 1 minute');
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  },
};

// Default configuration factory
export const createOneDriveConfig = (overrides?: Partial<AtomOneDriveIngestionConfig>): AtomOneDriveIngestionConfig => {
  return {
    ...ONEDRIVE_DEFAULT_CONFIG,
    ...overrides,
  };
};

// Integration metadata
export const OneDriveIntegrationMetadata = {
  name: 'OneDrive Integration',
  version: '1.0.0',
  description: 'Microsoft OneDrive integration with ATOM ingestion pipeline',
  author: 'ATOM Team',
  supportedFeatures: [
    'file-upload',
    'file-download',
    'folder-management',
    'search',
    'real-time-sync',
    'atom-ingestion',
    'batch-processing',
    'metadata-extraction',
    'preview-generation',
  ],
  apiVersion: 'v1.0',
  baseUrl: 'https://graph.microsoft.com',
  documentation: 'https://docs.microsoft.com/en-us/graph/api/resources/onedrive',
  authentication: 'OAuth 2.0',
  requiredScopes: [
    'Files.ReadWrite',
    'Sites.ReadWrite.All',
    'User.Read',
    'offline_access',
  ],
  optionalScopes: [
    'Files.ReadWrite.AppFolder',
    'Sites.Selected',
    'Mail.Read',
    'Calendars.Read',
  ],
  rateLimits: {
    requestsPerMinute: 10000,
    requestsPerHour: 600000,
    uploadThrottling: {
      maxFileSize: 250 * 1024 * 1024, // 250MB for simple upload
      recommendedChunkSize: 320 * 1024, // 320KB for resumable upload
      maxConcurrentUploads: 3,
    },
  },
  supportedFileTypes: Object.keys(ONEDRIVE_SUPPORTED_FILE_TYPES),
  maxConcurrentOperations: 5,
  defaultBatchSize: 50,
  syncInterval: 5 * 60 * 1000, // 5 minutes
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
};

export default {
  OneDriveIntegration,
  OneDriveManager,
  AtomOneDriveManager,
  OneDriveSkillsBundle,
  OneDriveUtils,
  createOneDriveConfig,
  OneDriveIntegrationMetadata,
};