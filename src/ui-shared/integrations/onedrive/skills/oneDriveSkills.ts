/**
 * ATOM OneDrive Skills Integration
 * Complete OneDrive automation skills for ATOM's skill system
 * Microsoft Graph API integration with advanced automation capabilities
 */

import {
  AtomSkill,
  AtomSkillContext,
  AtomSkillResult,
  SkillCategory,
  SkillPriority,
} from '@atom/agents';

import {
  OneDriveFile,
  OneDriveFolder,
  OneDriveSearchQuery,
  OneDriveUploadProgress,
  ONEDRIVE_DEFAULT_CONFIG,
} from '../types';

interface OneDriveSkillContext extends AtomSkillContext {
  // Microsoft Graph API client
  graphClient?: {
    get: (endpoint: string) => Promise<any>;
    post: (endpoint: string, data: any) => Promise<any>;
    put: (endpoint: string, data: any) => Promise<any>;
    delete: (endpoint: string) => Promise<any>;
  };
  
  // ATOM ingestion pipeline
  atomIngestionPipeline?: {
    processDocument: (document: any) => Promise<any>;
    searchDocuments: (query: string) => Promise<any>;
  };
  
  // OneDrive configuration
  onedriveConfig?: typeof ONEDRIVE_DEFAULT_CONFIG;
}

/**
 * Search OneDrive Files Skill
 * Search for files and folders in OneDrive using various filters
 */
export const SearchOneDriveFilesSkill: AtomSkill = {
  id: 'onedrive_search_files',
  name: 'Search OneDrive Files',
  description: 'Search for files and folders in OneDrive using filters, queries, and metadata',
  category: SkillCategory.FILE_MANAGEMENT,
  priority: SkillPriority.NORMAL,
  
  input: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Search query for file names and content',
      },
      fileTypes: {
        type: 'array',
        items: { type: 'string' },
        description: 'Specific file types to search for',
      },
      folderId: {
        type: 'string',
        description: 'Specific folder ID to search within',
      },
      includeSubfolders: {
        type: 'boolean',
        default: true,
        description: 'Include subfolders in search',
      },
      dateRange: {
        type: 'object',
        properties: {
          from: { type: 'string', format: 'date-time' },
          to: { type: 'string', format: 'date-time' },
        },
        description: 'Date range filter',
      },
      sizeRange: {
        type: 'object',
        properties: {
          min: { type: 'number' },
          max: { type: 'number' },
        },
        description: 'File size range filter in bytes',
      },
      limit: {
        type: 'number',
        default: 50,
        description: 'Maximum number of results to return',
      },
    },
    required: ['query'],
  },
  
  output: {
    type: 'object',
    properties: {
      files: {
        type: 'array',
        items: { $ref: '#/definitions/OneDriveFile' },
        description: 'Found files matching the search criteria',
      },
      folders: {
        type: 'array',
        items: { $ref: '#/definitions/OneDriveFolder' },
        description: 'Found folders matching the search criteria',
      },
      totalCount: {
        type: 'number',
        description: 'Total number of items found',
      },
      searchQuery: {
        type: 'string',
        description: 'The search query that was executed',
      },
      searchTime: {
        type: 'number',
        description: 'Time taken to search in milliseconds',
      },
    },
  },
  
  definitions: {
    OneDriveFile: {
      type: 'object',
      properties: {
        id: { type: 'string' },
        name: { type: 'string' },
        size: { type: 'number' },
        mimeType: { type: 'string' },
        webUrl: { type: 'string' },
        createdDateTime: { type: 'string' },
        lastModifiedDateTime: { type: 'string' },
        '@microsoft.graph.downloadUrl': { type: 'string' },
      },
    },
    OneDriveFolder: {
      type: 'object',
      properties: {
        id: { type: 'string' },
        name: { type: 'string' },
        webUrl: { type: 'string' },
        folder: {
          type: 'object',
          properties: {
            childCount: { type: 'number' },
          },
        },
      },
    },
  },
  
  execute: async (input: any, context: OneDriveSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.graphClient) {
        throw new Error('OneDrive Graph client not available');
      }

      // Build search query
      let searchQuery = input.query || '';
      const queryParams: string[] = [];

      // Add file type filter
      if (input.fileTypes && input.fileTypes.length > 0) {
        const fileFilter = input.fileTypes.map((type: string) => `fileType:${type}`).join(' OR ');
        searchQuery += ` ${fileFilter}`;
      }

      // Add date range filter
      if (input.dateRange) {
        if (input.dateRange.from) {
          queryParams.push(`lastModifiedDateTime ge ${input.dateRange.from}`);
        }
        if (input.dateRange.to) {
          queryParams.push(`lastModifiedDateTime le ${input.dateRange.to}`);
        }
      }

      // Add size range filter
      if (input.sizeRange) {
        if (input.sizeRange.min) {
          queryParams.push(`size ge ${input.sizeRange.min}`);
        }
        if (input.sizeRange.max) {
          queryParams.push(`size le ${input.sizeRange.max}`);
        }
      }

      // Construct search endpoint
      let searchEndpoint = `/me/drive/search(q='${encodeURIComponent(searchQuery)}')`;
      
      if (queryParams.length > 0) {
        searchEndpoint += `?$filter=${encodeURIComponent(queryParams.join(' and '))}`;
      }
      
      if (input.limit) {
        searchEndpoint += `&$top=${input.limit}`;
      }

      // Execute search
      const searchResults = await context.graphClient.get(searchEndpoint);
      const searchTime = Date.now() - startTime;

      // Separate files and folders
      const files = searchResults.value.filter((item: any) => !item.folder);
      const folders = searchResults.value.filter((item: any) => item.folder);

      return {
        success: true,
        data: {
          files,
          folders,
          totalCount: searchResults['@odata.count'] || searchResults.value.length,
          searchQuery: input.query,
          searchTime,
        },
        metadata: {
          executionTime: searchTime,
          resultCount: searchResults.value.length,
          searchEndpoint,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to search OneDrive files',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

/**
 * Upload File to OneDrive Skill
 * Upload files to OneDrive with progress tracking
 */
export const UploadFileToOneDriveSkill: AtomSkill = {
  id: 'onedrive_upload_file',
  name: 'Upload File to OneDrive',
  description: 'Upload files to OneDrive with optional folder destination and metadata',
  category: SkillCategory.FILE_MANAGEMENT,
  priority: SkillPriority.NORMAL,
  
  input: {
    type: 'object',
    properties: {
      fileContent: {
        type: 'string',
        description: 'Base64 encoded file content or file data',
      },
      fileName: {
        type: 'string',
        description: 'Name of the file to upload',
      },
      mimeType: {
        type: 'string',
        description: 'MIME type of the file',
      },
      folderId: {
        type: 'string',
        description: 'Optional folder ID where to upload the file',
      },
      overwrite: {
        type: 'boolean',
        default: false,
        description: 'Whether to overwrite existing file',
      },
      metadata: {
        type: 'object',
        description: 'Additional metadata for the file',
      },
    },
    required: ['fileContent', 'fileName', 'mimeType'],
  },
  
  output: {
    type: 'object',
    properties: {
      file: {
        $ref: '#/definitions/OneDriveFile',
        description: 'Uploaded file information',
      },
      uploadTime: {
        type: 'number',
        description: 'Time taken to upload in milliseconds',
      },
      fileSize: {
        type: 'number',
        description: 'Size of the uploaded file in bytes',
      },
      uploadUrl: {
        type: 'string',
        description: 'Direct URL to download the uploaded file',
      },
    },
  },
  
  execute: async (input: any, context: OneDriveSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.graphClient) {
        throw new Error('OneDrive Graph client not available');
      }

      // Determine upload endpoint
      let uploadEndpoint = '/me/drive/root:/' + encodeURIComponent(input.fileName) + ':/content';
      
      if (input.folderId) {
        uploadEndpoint = `/me/drive/items/${input.folderId}:/${encodeURIComponent(input.fileName)}:/content`;
      }

      // Prepare file content
      let fileData: Blob;
      if (typeof input.fileContent === 'string') {
        // Assume base64 encoded
        const binaryString = atob(input.fileContent);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        fileData = new Blob([bytes], { type: input.mimeType });
      } else {
        fileData = input.fileContent;
      }

      // Upload file
      const response = await fetch(`https://graph.microsoft.com/v1.0${uploadEndpoint}`, {
        method: 'PUT',
        headers: {
          'Content-Type': input.mimeType,
          // Note: Authorization header would be added by the Graph client
        },
        body: fileData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
      }

      const uploadedFile = await response.json();
      const uploadTime = Date.now() - startTime;

      // Optionally process through ATOM ingestion pipeline
      let atomResult = null;
      if (context.atomIngestionPipeline && input.processWithAtom) {
        try {
          atomResult = await context.atomIngestionPipeline.processDocument({
            content: fileData,
            metadata: {
              source: 'onedrive',
              fileId: uploadedFile.id,
              fileName: uploadedFile.name,
              mimeType: uploadedFile.mimeType,
              size: uploadedFile.size,
              uploadedAt: uploadedFile.createdDateTime,
              ...input.metadata,
            },
          });
        } catch (atomError) {
          console.warn('Failed to process with ATOM pipeline:', atomError);
        }
      }

      return {
        success: true,
        data: {
          file: uploadedFile,
          uploadTime,
          fileSize: uploadedFile.size,
          uploadUrl: uploadedFile['@microsoft.graph.downloadUrl'],
          atomResult,
        },
        metadata: {
          executionTime: uploadTime,
          uploadEndpoint,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to upload file to OneDrive',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

/**
 * Create Folder in OneDrive Skill
 * Create new folders in OneDrive with optional parent folder
 */
export const CreateOneDriveFolderSkill: AtomSkill = {
  id: 'onedrive_create_folder',
  name: 'Create OneDrive Folder',
  description: 'Create new folders in OneDrive with optional parent folder and metadata',
  category: SkillCategory.FILE_MANAGEMENT,
  priority: SkillPriority.NORMAL,
  
  input: {
    type: 'object',
    properties: {
      folderName: {
        type: 'string',
        description: 'Name of the folder to create',
      },
      parentFolderId: {
        type: 'string',
        description: 'Optional parent folder ID where to create the folder',
      },
      description: {
        type: 'string',
        description: 'Optional description for the folder',
      },
      metadata: {
        type: 'object',
        description: 'Additional metadata for the folder',
      },
    },
    required: ['folderName'],
  },
  
  output: {
    type: 'object',
    properties: {
      folder: {
        $ref: '#/definitions/OneDriveFolder',
        description: 'Created folder information',
      },
      creationTime: {
        type: 'number',
        description: 'Time taken to create the folder in milliseconds',
      },
      folderUrl: {
        type: 'string',
        description: 'URL to access the created folder',
      },
    },
  },
  
  execute: async (input: any, context: OneDriveSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.graphClient) {
        throw new Error('OneDrive Graph client not available');
      }

      // Determine creation endpoint
      let creationEndpoint = '/me/drive/root/children';
      
      if (input.parentFolderId) {
        creationEndpoint = `/me/drive/items/${input.parentFolderId}/children`;
      }

      // Prepare folder data
      const folderData = {
        name: input.folderName,
        folder: {},
        description: input.description || '',
        ...input.metadata,
      };

      // Create folder
      const createdFolder = await context.graphClient.post(creationEndpoint, folderData);
      const creationTime = Date.now() - startTime;

      return {
        success: true,
        data: {
          folder: createdFolder,
          creationTime,
          folderUrl: createdFolder.webUrl,
        },
        metadata: {
          executionTime: creationTime,
          creationEndpoint,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to create OneDrive folder',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

/**
 * Sync OneDrive with ATOM Memory Skill
 * Synchronize OneDrive files with ATOM's memory system (LanceDB)
 */
export const SyncOneDriveWithAtomMemorySkill: AtomSkill = {
  id: 'onedrive_sync_with_atom_memory',
  name: 'Sync OneDrive with ATOM Memory',
  description: 'Synchronize OneDrive files with ATOM memory system for intelligent search and retrieval',
  category: SkillCategory.DATA_SYNCHRONIZATION,
  priority: SkillPriority.HIGH,
  
  input: {
    type: 'object',
    properties: {
      folderId: {
        type: 'string',
        description: 'Optional folder ID to sync (defaults to root)',
      },
      includeSubfolders: {
        type: 'boolean',
        default: true,
        description: 'Include subfolders in synchronization',
      },
      fileTypes: {
        type: 'array',
        items: { type: 'string' },
        description: 'Specific file types to sync',
      },
      maxFileSize: {
        type: 'number',
        description: 'Maximum file size to process (bytes)',
      },
      batchSize: {
        type: 'number',
        default: 50,
        description: 'Number of files to process in each batch',
      },
      incrementalSync: {
        type: 'boolean',
        default: true,
        description: 'Only sync files modified since last sync',
      },
      lastSyncTime: {
        type: 'string',
        format: 'date-time',
        description: 'Last synchronization time for incremental sync',
      },
    },
  },
  
  output: {
    type: 'object',
    properties: {
      syncedFiles: {
        type: 'array',
        items: { $ref: '#/definitions/OneDriveFile' },
        description: 'Files successfully synced with ATOM memory',
      },
      skippedFiles: {
        type: 'array',
        items: { $ref: '#/definitions/OneDriveFile' },
        description: 'Files skipped during synchronization',
      },
      failedFiles: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file: { $ref: '#/definitions/OneDriveFile' },
            error: { type: 'string' },
          },
        },
        description: 'Files that failed to sync with error details',
      },
      syncStats: {
        type: 'object',
        properties: {
          totalFiles: { type: 'number' },
          syncedFiles: { type: 'number' },
          skippedFiles: { type: 'number' },
          failedFiles: { type: 'number' },
          syncTime: { type: 'number' },
          totalBytesProcessed: { type: 'number' },
        },
      },
    },
  },
  
  execute: async (input: any, context: OneDriveSkillContext): Promise<AtomSkillResult> => {
    const startTime = Date.now();
    
    try {
      if (!context.graphClient || !context.atomIngestionPipeline) {
        throw new Error('OneDrive Graph client and ATOM ingestion pipeline are required');
      }

      // Get files to sync
      let searchEndpoint = `/me/drive/root/children`;
      if (input.folderId) {
        searchEndpoint = `/me/drive/items/${input.folderId}/children`;
      }

      const allItems = [];
      let currentEndpoint = searchEndpoint;
      
      // Paginate through all items
      do {
        const response = await context.graphClient.get(currentEndpoint);
        allItems.push(...response.value);
        currentEndpoint = response['@odata.nextLink'];
      } while (currentEndpoint);

      // Filter files based on criteria
      let filesToProcess = allItems.filter((item: any) => !item.folder);

      if (input.fileTypes && input.fileTypes.length > 0) {
        filesToProcess = filesToProcess.filter((file: any) => 
          input.fileTypes.includes(file.mimeType)
        );
      }

      if (input.maxFileSize) {
        filesToProcess = filesToProcess.filter((file: any) => 
          file.size <= input.maxFileSize
        );
      }

      if (input.incrementalSync && input.lastSyncTime) {
        filesToProcess = filesToProcess.filter((file: any) => 
          new Date(file.lastModifiedDateTime) > new Date(input.lastSyncTime)
        );
      }

      // Process files in batches
      const batchSize = input.batchSize || 50;
      const syncedFiles = [];
      const skippedFiles = [];
      const failedFiles = [];

      for (let i = 0; i < filesToProcess.length; i += batchSize) {
        const batch = filesToProcess.slice(i, i + batchSize);
        
        for (const file of batch) {
          try {
            // Download file content
            const fileContent = await context.graphClient.get(`/me/drive/items/${file.id}/content`);
            
            // Process through ATOM pipeline
            const atomResult = await context.atomIngestionPipeline.processDocument({
              content: fileContent,
              metadata: {
                source: 'onedrive',
                fileId: file.id,
                fileName: file.name,
                mimeType: file.mimeType,
                size: file.size,
                lastModified: file.lastModifiedDateTime,
                createdAt: file.createdDateTime,
                webUrl: file.webUrl,
                syncTime: new Date().toISOString(),
              },
            });

            syncedFiles.push({
              ...file,
              atomProcessed: true,
              atomId: atomResult.id,
              atomTimestamp: atomResult.timestamp,
            });

          } catch (error) {
            failedFiles.push({
              file,
              error: error instanceof Error ? error.message : 'Unknown error',
            });
          }
        }
      }

      const syncTime = Date.now() - startTime;
      const totalBytesProcessed = syncedFiles.reduce((sum, file) => sum + file.size, 0);

      return {
        success: true,
        data: {
          syncedFiles,
          skippedFiles,
          failedFiles,
          syncStats: {
            totalFiles: filesToProcess.length,
            syncedFiles: syncedFiles.length,
            skippedFiles: skippedFiles.length,
            failedFiles: failedFiles.length,
            syncTime,
            totalBytesProcessed,
          },
        },
        metadata: {
          executionTime: syncTime,
          batchSize,
          itemsProcessed: filesToProcess.length,
        },
      };

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to sync OneDrive with ATOM memory',
        metadata: {
          executionTime: Date.now() - startTime,
        },
      };
    }
  },
};

/**
 * OneDrive File Management Skill Bundle
 * Collection of all OneDrive skills for easy registration
 */
export const OneDriveSkillsBundle = {
  skills: [
    SearchOneDriveFilesSkill,
    UploadFileToOneDriveSkill,
    CreateOneDriveFolderSkill,
    SyncOneDriveWithAtomMemorySkill,
  ],
  
  // Skill dependencies and relationships
  dependencies: {
    'microsoft_graph_auth': 'Required for OneDrive API access',
    'atom_ingestion_pipeline': 'Required for ATOM memory synchronization',
  },
  
  // Configuration recommendations
  recommendedConfig: {
    apiPermissions: [
      'Files.ReadWrite',
      'Sites.ReadWrite.All',
      'User.Read',
    ],
    rateLimit: {
      requestsPerMinute: 100,
      requestsPerHour: 6000,
    },
    batchSize: 50,
    retryAttempts: 3,
  },
  
  // Skill integration examples
  examples: {
    searchFiles: {
      description: 'Search for PDF files modified in the last week',
      input: {
        query: 'report',
        fileTypes: ['application/pdf'],
        dateRange: {
          from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
          to: new Date().toISOString(),
        },
        limit: 25,
      },
    },
    
    uploadAndSync: {
      description: 'Upload a document and sync with ATOM memory',
      input: {
        fileContent: 'base64-encoded-file-content',
        fileName: 'important-document.pdf',
        mimeType: 'application/pdf',
        folderId: 'folder-id-here',
        processWithAtom: true,
      },
    },
    
    syncFolder: {
      description: 'Sync entire folder with ATOM memory',
      input: {
        folderId: 'root-folder-id',
        includeSubfolders: true,
        fileTypes: [
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'text/plain',
        ],
        maxFileSize: 50 * 1024 * 1024, // 50MB
        batchSize: 25,
        incrementalSync: true,
      },
    },
  },
};

export default OneDriveSkillsBundle;