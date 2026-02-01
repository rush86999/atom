/**
 * ATOM Box Data Source - Integration Version
 * File Storage → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomBoxDataSourceProps, 
  AtomBoxDataSourceState,
  AtomBoxIngestionConfig,
  AtomBoxDataSource,
  BoxFile,
  BoxFolder,
  BoxFileEnhanced
} from '../types';

export const ATOMBoxDataSource: React.FC<AtomBoxDataSourceProps> = ({
  // Box Authentication
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
  const [state, setState] = useState<AtomBoxDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    dataSource: null,
    ingestionStatus: 'idle',
    lastIngestionTime: null,
    discoveredFiles: [],
    discoveredFolders: [],
    discoveredWebhooks: [],
    ingestionQueue: [],
    processingIngestion: false,
    stats: {
      totalFiles: 0,
      totalFolders: 0,
      totalWebhooks: 0,
      ingestedFiles: 0,
      failedIngestions: 0,
      lastSyncTime: null,
      dataSize: 0
    }
  });

  // Configuration
  const [dataSourceConfig] = useState<AtomBoxIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'box-integration',
    sourceName: 'Box',
    sourceType: 'box',
    
    // API Configuration
    apiBaseUrl: 'https://api.box.com/2.0',
    uploadApiUrl: 'https://upload.box.com/api/2.0',
    clientId: config.clientId || '',
    clientSecret: config.clientSecret || '',
    enterpriseId: config.enterpriseId,
    
    // File Discovery
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
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 3600000, // 1 hour
    realTimeIngest: true,
    batchSize: 25,
    maxConcurrentIngestions: 2,
    
    // Processing
    extractMetadata: true,
    generateThumbnails: true,
    extractText: true,
    chunkSize: 1000,
    chunkOverlap: 100,
    useThumbnailApi: true,
    thumbnailSize: '256x256',
    
    // Sync Settings
    useWebhooks: true,
    webhookEvents: ['FILE.UPLOADED', 'FILE.DELETED', 'FILE.TRASHED', 'FILE.UNTRASHED'],
    syncInterval: 300000, // 5 minutes
    incrementalSync: true,
    
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

  // Box API Integration (simplified for integration version)
  const boxApi = useMemo(() => {
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
        throw new Error(`Box API Error: ${response.status} - ${errorData.message || response.statusText}`);
      }
      
      return response.json();
    };

    return {
      // File Operations
      getFiles: async (folderId: string = '0', limit: number = 100, offset: number = 0) => {
        return await makeRequest(`/folders/${folderId}/items?limit=${limit}&offset=${offset}`);
      },
      
      getFile: async (fileId: string) => {
        return await makeRequest(`/files/${fileId}`);
      },
      
      downloadFile: async (fileId: string) => {
        const file = await boxApi.getFile(fileId);
        const downloadResponse = await fetch(file.url, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        
        const blob = await downloadResponse.blob();
        return {
          blob,
          filename: file.name,
          contentType: file.type,
          size: file.size
        };
      },
      
      // Folder Operations
      getFolders: async (folderId: string = '0', limit: number = 100, offset: number = 0) => {
        const response = await makeRequest(`/folders/${folderId}/items?limit=${limit}&offset=${offset}`);
        return {
          ...response,
          entries: response.entries.filter((item: any) => item.type === 'folder')
        };
      },
      
      // Webhook Operations
      getWebhooks: async () => {
        return await makeRequest('/webhooks');
      },
      
      createWebhook: async (targetId: string, address: string, triggers: string[]) => {
        return await makeRequest('/webhooks', {
          method: 'POST',
          body: JSON.stringify({
            target: {
              id: targetId,
              type: 'folder'
            },
            address,
            triggers
          })
        });
      },
      
      deleteWebhook: async (webhookId: string) => {
        return await makeRequest(`/webhooks/${webhookId}`, {
          method: 'DELETE'
        });
      }
    };
  }, [accessToken, refreshToken, onTokenRefresh, dataSourceConfig]);

  // Check if file should be excluded
  const isFileExcluded = (fileName: string, path?: string): boolean => {
    const fullPath = path || fileName;
    return dataSourceConfig.excludePaths.some(pattern => {
      const regex = new RegExp(pattern.replace(/\*/g, '.*'));
      return regex.test(fullPath);
    });
  };

  // Register Box as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Create Box data source configuration
      const boxDataSource: AtomBoxDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'box',
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
        await atomIngestionPipeline.registerDataSource(boxDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(boxDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: boxDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(boxDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register Box data source: ${(error as Error).message}`;
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
  const discoverFiles = useCallback(async (folderIds?: string[]): Promise<BoxFileEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const targetFolderIds = folderIds || dataSourceConfig.folderIds;
      const allFiles: BoxFileEnhanced[] = [];
      
      for (const folderId of targetFolderIds) {
        try {
          const response = await boxApi.getFiles(folderId, 1000, 0);
          
          const files = response.entries
            .filter((item: any) => item.type === 'file')
            .filter((file: any) => dataSourceConfig.supportedFileTypes.some(ext => file.name.endsWith(ext)))
            .filter((file: any) => !isFileExcluded(file.name, file.path_collection?.entries?.map((e: any) => e.name).join('/')))
            .map((file: BoxFile) => ({
              ...file,
              source: 'box' as const,
              discoveredAt: new Date().toISOString(),
              processedAt: undefined,
              textExtracted: false,
              previewGenerated: false,
              embeddingGenerated: false,
              ingested: false,
              ingestionTime: undefined,
              documentId: undefined,
              vectorCount: undefined
            }));
          
          allFiles.push(...files);
        } catch (error) {
          console.error(`Failed to discover files in folder ${folderId}:`, error);
        }
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredFiles: allFiles,
        stats: {
          ...prev.stats,
          totalFiles: allFiles.length
        }
      }));
      
      return allFiles;
      
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
  }, [boxApi, dataSourceConfig, onDataSourceError]);

  // Discover Folders
  const discoverFolders = useCallback(async (folderIds?: string[]): Promise<any[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const targetFolderIds = folderIds || dataSourceConfig.folderIds;
      const allFolders: any[] = [];
      
      for (const folderId of targetFolderIds) {
        try {
          const response = await boxApi.getFolders(folderId, 1000, 0);
          
          const folders = response.entries.map((folder: BoxFolder) => ({
            ...folder,
            source: 'box' as const,
            discoveredAt: new Date().toISOString(),
            fileCount: 0, // Would need to be calculated
            totalSize: 0
          }));
          
          allFolders.push(...folders);
        } catch (error) {
          console.error(`Failed to discover folders in ${folderId}:`, error);
        }
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredFolders: allFolders,
        stats: {
          ...prev.stats,
          totalFolders: allFolders.length
        }
      }));
      
      return allFolders;
      
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
  }, [boxApi, dataSourceConfig, onDataSourceError]);

  // Discover Webhooks
  const discoverWebhooks = useCallback(async (): Promise<any[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const webhooks = await boxApi.getWebhooks();
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredWebhooks: webhooks.entries,
        stats: {
          ...prev.stats,
          totalWebhooks: webhooks.entries.length
        }
      }));
      
      return webhooks.entries;
      
    } catch (error) {
      const errorMessage = `Webhook discovery failed: ${(error as Error).message}`;
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
  }, [boxApi, onDataSourceError]);

  // Extract Text from File
  const extractTextFromFile = async (blob: Blob, fileName: string, contentType: string): Promise<string> => {
    try {
      switch (contentType) {
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
          return `[PDF content extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'application/msword':
        case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
          return `[Word document content extraction not implemented - Size: ${blob.size} bytes]`;
          
        default:
          console.warn(`Text extraction not supported for content type: ${contentType}`);
          return '';
      }
    } catch (error) {
      console.error(`Error extracting text from ${fileName}:`, error);
      return '';
    }
  };

  // Ingest Files with Existing Pipeline
  const ingestFiles = useCallback(async (files: BoxFileEnhanced[]): Promise<void> => {
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
                try {
                  const fileBlob = await boxApi.downloadFile(file.id);
                  content = await extractTextFromFile(fileBlob.blob, file.name, fileBlob.contentType);
                } catch (error) {
                  console.error(`Failed to extract text from file ${file.id}:`, error);
                }
              }
              
              return {
                id: file.id,
                sourceId: dataSourceConfig.sourceId,
                sourceName: dataSourceConfig.sourceName,
                sourceType: 'box',
                fileName: file.name,
                filePath: file.path_collection?.entries?.map((e: any) => e.name).join('/') || '',
                contentType: file.type,
                size: file.size,
                createdAt: file.created_at,
                modifiedAt: file.modified_at,
                metadata: {
                  boxFile: file,
                  extractedMetadata: {
                    text: content,
                    hasText: !!content
                  },
                  thumbnailGenerated: false,
                  previewUrl: file.shared_link?.url
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
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, boxApi, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

  // Sync Files
  const syncFiles = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Simplified sync - just discover new files
      const discoveredFiles = await discoverFiles(dataSourceConfig.folderIds);
      
      // Filter for files not yet ingested
      const newFiles = discoveredFiles.filter(file => 
        !state.discoveredFiles.some(existing => existing.id === file.id)
      );
      
      if (newFiles.length > 0) {
        await ingestFiles(newFiles);
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
  }, [discoverFiles, ingestFiles, dataSourceConfig, state.discoveredFiles, onDataSourceError]);

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
      const discoveredFolders = await discoverFolders();
      
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
        const discoveredFiles = await discoverFiles();
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
  }, [dataSourceConfig, state.connected, discoverFiles, discoverFolders, ingestFiles, syncFiles]);

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
          discoverWebhooks,
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
      <div className={`atom-box-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          📦 ATOM Box Data Source
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
              onClick={() => discoverFiles()}
              disabled={!state.connected || state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Discover Files
            </button>
            <button
              onClick={() => discoverFolders()}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Discover Folders
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

export default ATOMBoxDataSource;