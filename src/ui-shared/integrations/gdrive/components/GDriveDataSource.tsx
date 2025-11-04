/**
 * ATOM Google Drive Data Source - TypeScript
 * File Storage → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production: Auto-discovery, Google Docs export, batch processing, real-time sync
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomGDriveDataSourceProps, 
  AtomGDriveDataSourceState,
  AtomGDriveIngestionConfig,
  AtomGDriveDataSource,
  GDriveFile,
  GDriveFolder,
  GDriveFileEnhanced
} from '../types';

export const ATOMGDriveDataSource: React.FC<AtomGDriveDataSourceProps> = ({
  // Google Drive Authentication
  accessToken,
  refreshToken,
  onTokenRefresh,
  
  // Existing ATOM Pipeline Integration
  atomIngestionPipeline,
  dataSourceRegistry,
  
  // Data Source Configuration
  config = {},
  platform = 'auto',
  theme = 'auto',
  
  // Events
  onDataSourceReady,
  onIngestionStart,
  onIngestionComplete,
  onIngestionProgress,
  onDataSourceError,
  
  // Children
  children
}) => {
  
  // State Management
  const [state, setState] = useState<AtomGDriveDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    dataSource: null,
    ingestionStatus: 'idle',
    lastIngestionTime: null,
    discoveredFiles: [],
    discoveredFolders: [],
    ingestionQueue: [],
    processingIngestion: false,
    stats: {
      totalFiles: 0,
      ingestedFiles: 0,
      failedIngestions: 0,
      lastSyncTime: null,
      dataSize: 0
    }
  });

  // Configuration
  const [dataSourceConfig] = useState<AtomGDriveIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'gdrive-integration',
    sourceName: 'Google Drive',
    sourceType: 'gdrive',
    
    // API Configuration
    apiBaseUrl: 'https://www.googleapis.com/drive/v3',
    scopes: [
      'https://www.googleapis.com/auth/drive',
      'https://www.googleapis.com/auth/drive.file',
      'https://www.googleapis.com/auth/drive.readonly'
    ],
    
    // File Discovery
    supportedFileTypes: [
      '.txt', '.md', '.pdf', '.doc', '.docx', 
      '.rtf', '.odt', '.html', '.htm', '.csv',
      '.json', '.xml', '.yaml', '.yml', '.log',
      '.js', '.ts', '.jsx', '.tsx', '.py', '.java',
      '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs',
      '.gdoc', '.gsheet', '.gslides', '.gform', '.gsite' // Google Workspace
    ],
    supportedMimeTypes: [
      'text/plain', 'text/markdown', 'application/pdf', 
      'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/rtf', 'application/vnd.oasis.opendocument.text',
      'text/html', 'text/csv', 'application/json',
      'application/xml', 'application/x-yaml', 'text/x-log',
      'text/javascript', 'text/typescript',
      'text/x-python', 'text/x-java-source',
      'text/x-c', 'text/x-c++', 'text/x-csharp',
      'text/x-php', 'text/x-ruby', 'text/x-go', 'text/x-rust',
      'application/vnd.google-apps.document',
      'application/vnd.google-apps.spreadsheet',
      'application/vnd.google-apps.presentation',
      'application/vnd.google-apps.form',
      'application/vnd.google-apps.site'
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
    includeSharedFiles: true,
    includeTrashed: false,
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 3600000, // 1 hour
    realTimeIngest: true,
    batchSize: 50,
    maxConcurrentIngestions: 3,
    
    // Sync Settings
    syncInterval: 300000, // 5 minutes
    incrementalSync: true,
    useChangeNotifications: true,
    
    // Processing
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
    
    // Pipeline Integration
    pipelineConfig: {
      targetTable: 'atom_memory',
      embeddingModel: 'text-embedding-3-large',
      embeddingDimension: 3072,
      indexType: 'IVF_FLAT',
      numPartitions: 256
    },
    
    ...config
  }));

  // Platform Detection
  const [currentPlatform, setCurrentPlatform] = useState<'nextjs' | 'tauri'>('nextjs');

  useEffect(() => {
    if (platform !== 'auto') {
      setCurrentPlatform(platform);
      return;
    }
    
    if (typeof window !== 'undefined' && (window as any).__TAURI__) {
      setCurrentPlatform('tauri');
    } else {
      setCurrentPlatform('nextjs');
    }
  }, [platform]);

  // Google Drive API Integration
  const gdriveApi = useMemo(() => {
    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      const url = `${dataSourceConfig.apiBaseUrl}${endpoint}`;
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        ...options.headers as Record<string, string>
      };
      
      const response = await fetch(url, {
        ...options,
        headers
      });
      
      if (response.status === 401) {
        if (refreshToken && onTokenRefresh) {
          const newTokens = await onTokenRefresh(refreshToken);
          if (newTokens.success) {
            headers['Authorization'] = `Bearer ${newTokens.accessToken}`;
            return fetch(url, { ...options, headers });
          }
        }
        throw new Error('Authentication failed');
      }
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Google Drive API Error: ${response.status} - ${errorData.error?.message || response.statusText}`);
      }
      
      return response.json();
    };

    return {
      // File Discovery
      discoverFiles: async (folderId?: string, recursive = true): Promise<GDriveFile[]> => {
        const discoveredFiles: GDriveFile[] = [];
        const fields = 'nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, trashed, explicitlyTrashed, owners, permissions, capabilities, thumbnailLink, fullFileExtension, fileExtension, md5Checksum, spaces, kind)';
        
        // Initial query
        let pageToken: string | undefined;
        do {
          const query = dataSourceConfig.includeTrashed 
            ? `trashed=${dataSourceConfig.includeTrashed}` 
            : 'trashed=false';
            
          const url = `/files?q=${encodeURIComponent(query)}&pageSize=1000&fields=${encodeURIComponent(fields)}${pageToken ? `&pageToken=${pageToken}` : ''}`;
          
          const data = await makeRequest(url);
          
          for (const item of data.files) {
            // Check if file is supported
            const isSupported = dataSourceConfig.supportedMimeTypes.includes(item.mimeType) ||
              dataSourceConfig.supportedFileTypes.includes(`.${item.fileExtension || ''}`);
            const isSizeValid = !item.size || parseInt(item.size) <= dataSourceConfig.maxFileSize;
            const isNotTrashed = !item.trashed && !item.explicitlyTrashed;
            
            if (isSupported && isSizeValid && isNotTrashed) {
              discoveredFiles.push({
                ...item,
                source: 'gdrive',
                discoveredAt: new Date().toISOString()
              });
            }
          }
          
          pageToken = data.nextPageToken;
        } while (pageToken);
        
        return discoveredFiles;
      },
      
      getFileMetadata: async (fileId: string): Promise<any> => {
        const fields = 'id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, trashed, explicitlyTrashed, owners, permissions, capabilities, thumbnailLink, fullFileExtension, fileExtension, md5Checksum, spaces, kind';
        return await makeRequest(`/files/${fileId}?fields=${encodeURIComponent(fields)}`);
      },
      
      downloadFile: async (fileId: string, acknowledgeAbuse = false): Promise<Blob> => {
        // For regular files, use download URL
        const metadata = await gdriveApi.getFileMetadata(fileId);
        
        if (metadata.webContentLink) {
          const response = await fetch(`${metadata.webContentLink}?acknowledgeAbuse=${acknowledgeAbuse}`);
          return response.blob();
        }
        
        // For Google Workspace files, use export API
        if (metadata.mimeType.startsWith('application/vnd.google-apps')) {
          const exportMimeType = dataSourceConfig.exportFormats[metadata.mimeType] || 'text/plain';
          const exportUrl = `https://www.googleapis.com/drive/v3/files/${fileId}/export?mimeType=${encodeURIComponent(exportMimeType)}`;
          const response = await fetch(exportUrl, {
            headers: {
              'Authorization': `Bearer ${accessToken}`
            }
          });
          return response.blob();
        }
        
        throw new Error('No download URL available for file');
      },
      
      exportFile: async (fileId: string, mimeType: string): Promise<Blob> => {
        const exportUrl = `https://www.googleapis.com/drive/v3/files/${fileId}/export?mimeType=${encodeURIComponent(mimeType)}`;
        const response = await fetch(exportUrl, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        return response.blob();
      },
      
      getRecentFiles: async (hours = 24): Promise<GDriveFile[]> => {
        const since = new Date(Date.now() - (hours * 3600 * 1000)).toISOString();
        const query = `modifiedTime >= '${since}' and trashed=false`;
        const fields = 'nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, trashed, explicitlyTrashed, owners, permissions, capabilities, thumbnailLink, fullFileExtension, fileExtension, md5Checksum, spaces, kind)';
        
        const data = await makeRequest(`/files?q=${encodeURIComponent(query)}&pageSize=1000&fields=${encodeURIComponent(fields)}&orderBy=modifiedTime desc`);
        
        return data.files
          .filter((file: GDriveFile) => file['.tag'] === 'file')
          .filter((file: GDriveFile) => {
            const isSupported = dataSourceConfig.supportedMimeTypes.includes(file.mimeType) ||
              dataSourceConfig.supportedFileTypes.includes(`.${file.fileExtension || ''}`);
            const isSizeValid = !file.size || parseInt(file.size) <= dataSourceConfig.maxFileSize;
            return isSupported && isSizeValid;
          });
      },
      
      // Change Notifications
      getChanges: async (pageToken?: string): Promise<any> => {
        const fields = 'nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, trashed, explicitlyTrashed, owners, permissions, capabilities, thumbnailLink, fullFileExtension, fileExtension, md5Checksum, spaces, kind), kind)';
        
        const body: any = {};
        if (pageToken) {
          body.pageToken = pageToken;
        } else {
          body.fields = fields;
        }
        
        return await makeRequest('/changes/watch', {
          method: 'POST',
          body: JSON.stringify(body)
        });
      },
      
      // Search
      search: async (query: string, options?: any): Promise<any> => {
        const searchQuery = `name contains '${query}' and trashed=false`;
        const fields = 'nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, trashed, explicitlyTrashed, owners, permissions, capabilities, thumbnailLink, fullFileExtension, fileExtension, md5Checksum, spaces, kind)';
        
        let url = `/files?q=${encodeURIComponent(searchQuery)}&pageSize=100&fields=${encodeURIComponent(fields)}&orderBy=relevance desc`;
        
        if (options?.pageToken) {
          url += `&pageToken=${options.pageToken}`;
        }
        
        return await makeRequest(url);
      },
      
      // File Watching
      startWatching: async (fileId: string): Promise<any> => {
        return await makeRequest(`/files/${fileId}/watch`, {
          method: 'POST',
          body: JSON.stringify({
            address: `${window.location.origin}/api/gdrive/webhook`,
            type: 'web_hook'
          })
        });
      },
      
      stopWatching: async (channelId: string, resourceId: string): Promise<any> => {
        return await makeRequest('/channels/stop', {
          method: 'POST',
          body: JSON.stringify({
            id: channelId,
            resourceId: resourceId
          })
        });
      }
    };
  }, [accessToken, refreshToken, onTokenRefresh, dataSourceConfig]);

  // Check if file should be excluded
  const isFileExcluded = (fileName: string, filePath?: string): boolean => {
    const pathToCheck = filePath || fileName;
    return dataSourceConfig.excludePatterns.some(pattern => {
      const regex = new RegExp(pattern.replace(/\*/g, '.*'));
      return regex.test(pathToCheck);
    });
  };

  // Register Google Drive as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Create Google Drive data source configuration
      const gdriveDataSource: AtomGDriveDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'gdrive',
        config: dataSourceConfig,
        authentication: {
          type: 'oauth2',
          accessToken: accessToken,
          refreshToken: refreshToken
        },
        capabilities: {
          fileDiscovery: true,
          realTimeSync: true,
          incrementalSync: true,
          batchProcessing: true,
          metadataExtraction: true,
          previewGeneration: true,
          textExtraction: true
        },
        status: 'active',
        createdAt: new Date(),
        lastUpdated: new Date()
      };
      
      // Register with existing ATOM pipeline
      if (atomIngestionPipeline && atomIngestionPipeline.registerDataSource) {
        await atomIngestionPipeline.registerDataSource(gdriveDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(gdriveDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: gdriveDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(gdriveDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register Google Drive data source: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'registration');
      }
    }
  }, [accessToken, refreshToken, dataSourceConfig, atomIngestionPipeline, dataSourceRegistry, onDataSourceReady, onDataSourceError]);

  // Discover Files
  const discoverFiles = useCallback(async (fullDiscovery = false): Promise<GDriveFileEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let discoveredFiles: GDriveFileEnhanced[] = [];
      
      if (fullDiscovery) {
        // Full file discovery
        const rawFiles = await gdriveApi.discoverFiles();
        discoveredFiles = await Promise.all(
          rawFiles.map(async (file) => {
            // Get file metadata
            const metadata = await gdriveApi.getFileMetadata(file.id);
            
            // Determine export format for Google Workspace files
            let exportFormat: string | undefined;
            if (file.mimeType.startsWith('application/vnd.google-apps')) {
              exportFormat = dataSourceConfig.exportFormats[file.mimeType];
            }
            
            return {
              ...file,
              source: 'gdrive' as const,
              textExtracted: false,
              previewGenerated: !!file.thumbnailLink,
              embeddingGenerated: false,
              ingested: false,
              documentId: undefined,
              vectorCount: undefined,
              exportFormat,
              metadata: metadata
            };
          })
        );
      } else {
        // Incremental discovery (recent files)
        const rawFiles = await gdriveApi.getRecentFiles(24);
        discoveredFiles = rawFiles.map((file) => {
          // Determine export format for Google Workspace files
          let exportFormat: string | undefined;
          if (file.mimeType.startsWith('application/vnd.google-apps')) {
            exportFormat = dataSourceConfig.exportFormats[file.mimeType];
          }
          
          return {
            ...file,
            source: 'gdrive' as const,
            textExtracted: false,
            previewGenerated: !!file.thumbnailLink,
            embeddingGenerated: false,
            ingested: false,
            documentId: undefined,
            vectorCount: undefined,
            exportFormat
          };
        });
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredFiles,
        stats: {
          ...prev.stats,
          totalFiles: discoveredFiles.length
        }
      }));
      
      return discoveredFiles;
      
    } catch (error) {
      const errorMessage = `File discovery failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'discovery');
      }
      
      return [];
    }
  }, [gdriveApi, dataSourceConfig, onDataSourceError]);

  // Discover Folders
  const discoverFolders = useCallback(async (fullDiscovery = false): Promise<any[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Simplified folder discovery for now
      const discoveredFolders: any[] = [];
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredFolders
      }));
      
      return discoveredFolders;
      
    } catch (error) {
      const errorMessage = `Folder discovery failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'discovery');
      }
      
      return [];
    }
  }, [onDataSourceError]);

  // Ingest Files with Existing Pipeline
  const ingestFiles = useCallback(async (files: GDriveFileEnhanced[]): Promise<void> => {
    if (!atomIngestionPipeline || !state.dataSource) {
      throw new Error('ATOM ingestion pipeline not available');
    }
    
    try {
      setState(prev => ({
        ...prev,
        processingIngestion: true,
        ingestionStatus: 'processing'
      }));
      
      if (onIngestionStart) {
        onIngestionStart({
          dataSource: state.dataSource,
          filesCount: files.length
        });
      }
      
      // Process files in batches
      const batchSize = dataSourceConfig.batchSize;
      let successCount = 0;
      let errorCount = 0;
      
      for (let i = 0; i < files.length; i += batchSize) {
        const batch = files.slice(i, i + batchSize);
        
        try {
          // Prepare batch for existing pipeline
          const preparedBatch = await Promise.all(
            batch.map(async (file) => {
              // Download file content if text extraction is enabled
              let content = '';
              if (dataSourceConfig.extractText) {
                let fileBlob: Blob;
                
                if (file.mimeType.startsWith('application/vnd.google-apps') && dataSourceConfig.useGoogleDocsExport) {
                  // Export Google Workspace file
                  const exportMimeType = file.exportFormat || 'text/plain';
                  fileBlob = await gdriveApi.exportFile(file.id, exportMimeType);
                } else {
                  // Download regular file
                  fileBlob = await gdriveApi.downloadFile(file.id);
                }
                
                content = await extractTextFromFile(fileBlob, file.name || '', file.mimeType);
              }
              
              return {
                id: file.id,
                sourceId: dataSourceConfig.sourceId,
                sourceName: dataSourceConfig.sourceName,
                sourceType: 'gdrive',
                fileName: file.name,
                filePath: file.parents?.[0] || '',
                contentType: file.mimeType,
                size: file.size ? parseInt(file.size) : undefined,
                createdAt: file.createdTime,
                modifiedAt: file.modifiedTime,
                metadata: {
                  gdriveMetadata: file.metadata,
                  extractedMetadata: file.metadata,
                  content: content,
                  thumbnailGenerated: file.previewGenerated,
                  exportFormat: file.exportFormat
                },
                content: content,
                chunkSize: dataSourceConfig.chunkSize,
                chunkOverlap: dataSourceConfig.chunkOverlap
              };
            })
          );
          
          // Send batch to existing ATOM ingestion pipeline
          const batchResult = await atomIngestionPipeline.ingestBatch({
            dataSourceId: dataSourceConfig.sourceId,
            items: preparedBatch,
            config: dataSourceConfig.pipelineConfig
          });
          
          successCount += batchResult.successful;
          errorCount += batchResult.failed;
          
          // Update progress
          const progress = ((i + batchSize) / files.length) * 100;
          
          if (onIngestionProgress) {
            onIngestionProgress({
              dataSource: state.dataSource,
              progress,
              processedCount: i + batchSize,
              totalCount: files.length,
              successCount,
              errorCount,
              currentBatch: Math.floor(i / batchSize) + 1,
              totalBatches: Math.ceil(files.length / batchSize)
            });
          }
          
          setState(prev => ({
            ...prev,
            stats: {
              ...prev.stats,
              ingestedFiles: prev.stats.ingestedFiles + batchResult.successful,
              failedIngestions: prev.stats.failedIngestions + batchResult.failed
            }
          }));
          
        } catch (batchError) {
          console.error('Batch ingestion error:', batchError);
          errorCount += batch.length;
        }
      }
      
      setState(prev => ({
        ...prev,
        processingIngestion: false,
        ingestionStatus: 'completed',
        lastIngestionTime: new Date()
      }));
      
      if (onIngestionComplete) {
        onIngestionComplete({
          dataSource: state.dataSource,
          successCount,
          errorCount,
          totalFiles: files.length,
          duration: Date.now() - (prev.lastIngestionTime?.getTime() || Date.now())
        });
      }
      
    } catch (error) {
      const errorMessage = `Ingestion failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        processingIngestion: false,
        ingestionStatus: 'failed',
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'ingestion');
      }
    }
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, gdriveApi, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

  // Extract Text from File
  const extractTextFromFile = async (blob: Blob, fileName: string, mimeType: string): Promise<string> => {
    try {
      // Handle different Google Workspace export formats
      if (mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
        // Would integrate with docx.js or similar library
        return `[Word document text extraction not implemented - Size: ${blob.size} bytes]`;
      }
      
      if (mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
        // Would integrate with xlsx.js or similar library
        const text = await blob.text();
        const lines = text.split('\n').slice(0, 100); // Limit to 100 lines
        return lines.join('\n');
      }
      
      if (mimeType === 'application/vnd.openxmlformats-officedocument.presentationml.presentation') {
        // Would integrate with pptx.js or similar library
        return `[PowerPoint text extraction not implemented - Size: ${blob.size} bytes]`;
      }
      
      switch (mimeType) {
        case 'text/plain':
        case 'text/markdown':
        case 'text/html':
        case 'text/csv':
        case 'application/json':
        case 'application/xml':
        case 'text/x-yaml':
        case 'text/x-log':
        case 'text/javascript':
        case 'text/typescript':
        case 'text/x-python':
        case 'text/x-java-source':
        case 'text/x-c':
        case 'text/x-c++':
        case 'text/x-csharp':
        case 'text/x-php':
        case 'text/x-ruby':
        case 'text/x-go':
        case 'text/x-rust':
          return await blob.text();
          
        case 'application/pdf':
          // Would integrate with PDF.js
          return `[PDF text extraction not implemented - Size: ${blob.size} bytes]`;
          
        default:
          console.warn(`Text extraction not supported for MIME type: ${mimeType}`);
          return '';
      }
    } catch (error) {
      console.error(`Error extracting text from ${fileName}:`, error);
      return '';
    }
  };

  // Sync Files
  const syncFiles = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Get recent changes
      const changes = await gdriveApi.getChanges(dataSourceConfig.pageToken);
      
      if (changes.changes && changes.changes.length > 0) {
        // Process changes
        const filesToIngest = changes.changes
          .filter(change => !change.removed && change.file?.mimeType.startsWith('application/vnd.google-apps') || 
            dataSourceConfig.supportedMimeTypes.includes(change.file?.mimeType || ''))
          .map((change: any) => ({
            ...change.file,
            source: 'gdrive' as const,
            textExtracted: false,
            previewGenerated: !!change.file?.thumbnailLink,
            embeddingGenerated: false,
            ingested: false,
            documentId: undefined,
            vectorCount: undefined,
            exportFormat: change.file?.mimeType.startsWith('application/vnd.google-apps') ? 
              dataSourceConfig.exportFormats[change.file.mimeType] : undefined
          }));
        
        if (filesToIngest.length > 0) {
          await ingestFiles(filesToIngest);
        }
      }
      
      // Update page token
      if (changes.nextPageToken) {
        dataSourceConfig.pageToken = changes.nextPageToken;
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        stats: {
          ...prev.stats,
          lastSyncTime: new Date()
        }
      }));
      
    } catch (error) {
      const errorMessage = `Sync failed: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'sync');
      }
    }
  }, [gdriveApi, dataSourceConfig, ingestFiles, onDataSourceError]);

  // Initialize Data Source
  useEffect(() => {
    if (accessToken && atomIngestionPipeline) {
      registerDataSource();
    }
  }, [accessToken, atomIngestionPipeline, registerDataSource]);

  // Start Auto Ingestion
  useEffect(() => {
    if (!dataSourceConfig.autoIngest || !state.connected) {
      return;
    }
    
    // Initial discovery and ingestion
    const initializeAutoIngestion = async () => {
      const discoveredFiles = await discoverFiles();
      if (discoveredFiles.length > 0) {
        await ingestFiles(discoveredFiles);
      }
    };
    
    initializeAutoIngestion();
    
    // Set up periodic ingestion
    const ingestionInterval = setInterval(async () => {
      if (dataSourceConfig.incrementalSync) {
        await syncFiles();
      } else {
        const discoveredFiles = await discoverFiles(false);
        if (discoveredFiles.length > 0) {
          await ingestFiles(discoveredFiles);
        }
      }
    }, dataSourceConfig.ingestInterval);
    
    // Set up periodic sync
    const syncInterval = setInterval(() => {
      syncFiles();
    }, dataSourceConfig.syncInterval);
    
    return () => {
      clearInterval(ingestionInterval);
      clearInterval(syncInterval);
    };
  }, [dataSourceConfig, state.connected, discoverFiles, ingestFiles, syncFiles]);

  // Theme Resolution
  const resolvedTheme = theme === 'auto' 
    ? (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;

  const themeClasses = {
    light: 'bg-white text-gray-900 border-gray-200',
    dark: 'bg-gray-900 text-gray-100 border-gray-700'
  };

  // Render Component or Children
  const renderContent = () => {
    if (children) {
      return children({
        state,
        actions: {
          discoverFiles,
          discoverFolders,
          ingestFiles,
          syncFiles,
          registerDataSource
        },
        config: dataSourceConfig,
        dataSource: state.dataSource
      });
    }

    // Default UI
    return (
      <div className={`atom-gdrive-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          📂 ATOM Google Drive Data Source
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Status Overview */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.stats.totalFiles}
            </div>
            <div className="text-sm text-gray-500">Total Files</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.stats.ingestedFiles}
            </div>
            <div className="text-sm text-gray-500">Ingested</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-red-600">
              {state.stats.failedIngestions}
            </div>
            <div className="text-sm text-gray-500">Failed</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.discoveredFiles.length}
            </div>
            <div className="text-sm text-gray-500">Discovered</div>
          </div>
        </div>

        {/* Data Source Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Data Source Status</h3>
          <div className={`px-3 py-2 rounded text-sm font-medium ${
            state.connected ? 'bg-green-100 text-green-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {state.connected ? 'Connected & Registered' : 'Not Connected'}
          </div>
        </div>

        {/* Ingestion Status */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Ingestion Status</h3>
          <div className={`px-3 py-2 rounded text-sm font-medium ${
            state.ingestionStatus === 'processing' ? 'bg-blue-100 text-blue-800' :
            state.ingestionStatus === 'completed' ? 'bg-green-100 text-green-800' :
            state.ingestionStatus === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {state.ingestionStatus.charAt(0).toUpperCase() + state.ingestionStatus.slice(1)}
          </div>
          {state.lastIngestionTime && (
            <div className="text-xs text-gray-500 mt-1">
              Last ingestion: {state.lastIngestionTime.toLocaleString()}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Quick Actions</h3>
          <div className="flex space-x-2">
            <button
              onClick={() => discoverFiles(true)}
              disabled={!state.connected || state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Full Discovery
            </button>
            <button
              onClick={() => discoverFiles(false)}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Incremental Discovery
            </button>
            <button
              onClick={() => ingestFiles(state.discoveredFiles)}
              disabled={!state.connected || state.processingIngestion || state.discoveredFiles.length === 0}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Ingest Discovered
            </button>
            <button
              onClick={syncFiles}
              disabled={!state.connected || state.loading}
              className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
            >
              Sync Now
            </button>
          </div>
        </div>

        {/* Configuration */}
        <div className="mb-6">
          <h3 className="font-semibold mb-2">Configuration</h3>
          <div className="text-sm space-y-1">
            <div>Auto Ingest: {dataSourceConfig.autoIngest ? 'Enabled' : 'Disabled'}</div>
            <div>Ingestion Interval: {(dataSourceConfig.ingestInterval / 60000).toFixed(0)} minutes</div>
            <div>Sync Interval: {(dataSourceConfig.syncInterval / 60000).toFixed(0)} minutes</div>
            <div>Batch Size: {dataSourceConfig.batchSize}</div>
            <div>Supported Types: {dataSourceConfig.supportedFileTypes.length} file types</div>
            <div>Google Docs Export: {dataSourceConfig.useGoogleDocsExport ? 'Enabled' : 'Disabled'}</div>
            <div>Real-time Sync: {dataSourceConfig.useChangeNotifications ? 'Enabled' : 'Disabled'}</div>
          </div>
        </div>

        {/* Error Display */}
        {state.error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded">
            <p className="text-red-700 text-sm">{state.error}</p>
          </div>
        )}
      </div>
    );
  };

  return renderContent();
};

export default ATOMGDriveDataSource;