/**
 * ATOM Box Data Source - TypeScript
 * Integrates with existing ATOM ingestion pipeline
 * Cross-platform: Next.js & Tauri
 * Production: Auto-discovery, batch processing, real-time sync
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomBoxDataSourceProps, 
  AtomBoxDataSourceState,
  AtomBoxIngestionConfig,
  AtomBoxDataSource,
  BoxFile,
  BoxFolder
} from '../../../types/box';

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
  const [dataSourceConfig] = useState<AtomBoxIngestionConfig>(() => ({
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
    generatePreviews: true,
    extractText: true,
    chunkSize: 1000,
    chunkOverlap: 100,
    
    // Existing Pipeline Integration
    pipelineConfig: {
      targetTable: 'atom_memory',
      embeddingModel: 'text-embedding-3-large',
      embeddingDimension: 3072,
      indexType: 'IVF_FLAT',
      numPartitions: 256,
      ...config.pipelineConfig
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

  // Box API Integration
  const boxApi = useMemo(() => {
    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      const baseUrl = 'https://api.box.com/2.0';
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        ...options.headers as Record<string, string>
      };
      
      const response = await fetch(`${baseUrl}${endpoint}`, {
        ...options,
        headers
      });
      
      if (response.status === 401) {
        if (refreshToken && onTokenRefresh) {
          const newTokens = await onTokenRefresh(refreshToken);
          if (newTokens.success) {
            headers['Authorization'] = `Bearer ${newTokens.accessToken}`;
            return fetch(`${baseUrl}${endpoint}`, { ...options, headers });
          }
        }
        throw new Error('Authentication failed');
      }
      
      if (!response.ok) {
        throw new Error(`Box API Error: ${response.status}`);
      }
      
      return response.json();
    };

    return {
      // File Discovery
      discoverFiles: async (folderId = '0', recursive = true): Promise<BoxFile[]> => {
        const discoveredFiles: BoxFile[] = [];
        const foldersToProcess: string[] = [folderId];
        
        while (foldersToProcess.length > 0) {
          const currentFolderId = foldersToProcess.shift()!;
          
          const query = new URLSearchParams({
            limit: '1000',
            fields: 'id,name,size,created_at,modified_at,parent,description,extension,content_type'
          });
          
          const data = await makeRequest(`/folders/${currentFolderId}/items?${query}`);
          const items = data.entries || [];
          
          for (const item of items) {
            if (item.type === 'folder' && recursive) {
              foldersToProcess.push(item.id);
            } else if (item.type === 'file') {
              // Check if file is supported
              const fileExtension = item.name?.split('.').pop()?.toLowerCase();
              const isSupported = fileExtension && 
                dataSourceConfig.supportedFileTypes.includes(`.${fileExtension}`);
              const isSizeValid = !item.size || item.size <= dataSourceConfig.maxFileSize;
              const isNotExcluded = !isFileExcluded(item.path || item.name || '');
              
              if (isSupported && isSizeValid && isNotExcluded) {
                discoveredFiles.push({
                  ...item,
                  source: 'box',
                  discoveredAt: new Date().toISOString()
                });
              }
            }
          }
        }
        
        return discoveredFiles;
      },
      
      getFileMetadata: async (fileId: string): Promise<any> => {
        const fields = 'id,name,size,created_at,modified_at,parent,description,extension,content_type,metadata';
        return await makeRequest(`/files/${fileId}?fields=${fields}`);
      },
      
      downloadFile: async (fileId: string): Promise<Blob> => {
        const downloadInfo = await makeRequest(`/files/${fileId}/content`, {
          method: 'POST',
          body: JSON.stringify({ 'download_url': true })
        });
        
        const response = await fetch(downloadInfo.download_url);
        return response.blob();
      },
      
      getRecentFiles: async (hours = 24): Promise<BoxFile[]> => {
        const since = new Date(Date.now() - (hours * 3600 * 1000)).toISOString();
        const query = `modified_at >= "${since}"`;
        
        const searchParams = new URLSearchParams({
          query,
          limit: '1000',
          fields: 'id,name,size,created_at,modified_at,parent,description,extension,content_type'
        });
        
        const data = await makeRequest(`/search?${searchParams}`);
        return data.entries?.filter((item: any) => item.type === 'file') || [];
      },
      
      // File Watching
      getFileChanges: async (since?: Date): Promise<any[]> => {
        const sinceTime = since?.toISOString() || new Date(Date.now() - dataSourceConfig.syncInterval).toISOString();
        
        // Use Box events API if available, otherwise use search
        try {
          const eventsQuery = new URLSearchParams({
            limit: '1000',
            event_type: 'ITEM_UPLOAD,ITEM_UPDATE,ITEM_MOVE,ITEM_COPY,ITEM_TRASH',
            created_after: sinceTime
          });
          
          const data = await makeRequest(`/events?${eventsQuery}`);
          return data.entries || [];
        } catch (error) {
          // Fallback to search-based change detection
          return await boxApi.getRecentFiles(Math.floor(dataSourceConfig.syncInterval / 3600000));
        }
      }
    };
  }, [accessToken, refreshToken, onTokenRefresh, dataSourceConfig]);

  // Check if file should be excluded
  const isFileExcluded = (filePath: string): boolean => {
    return dataSourceConfig.excludePatterns.some(pattern => {
      const regex = new RegExp(pattern.replace(/\*/g, '.*'));
      return regex.test(filePath);
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
          previewGeneration: false,
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
  const discoverFiles = useCallback(async (fullDiscovery = false): Promise<BoxFile[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let discoveredFiles: BoxFile[] = [];
      
      if (fullDiscovery) {
        // Full file discovery
        discoveredFiles = await boxApi.discoverFiles('0', true);
      } else {
        // Incremental discovery (recent files)
        discoveredFiles = await boxApi.getRecentFiles(24);
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
  }, [boxApi, onDataSourceError]);

  // Ingest Files with Existing Pipeline
  const ingestFiles = useCallback(async (files: BoxFile[]): Promise<void> => {
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
              // Get file metadata
              const metadata = await boxApi.getFileMetadata(file.id);
              
              // Download file content if text extraction is enabled
              let content = '';
              if (dataSourceConfig.extractText) {
                const fileBlob = await boxApi.downloadFile(file.id);
                content = await extractTextFromFile(fileBlob, file.name || '');
              }
              
              return {
                id: file.id,
                sourceId: dataSourceConfig.sourceId,
                sourceName: dataSourceConfig.sourceName,
                sourceType: 'box',
                fileName: file.name,
                filePath: file.path || file.name,
                contentType: file.content_type,
                size: file.size,
                createdAt: file.created_at,
                modifiedAt: file.modified_at,
                metadata: {
                  boxMetadata: metadata,
                  extractedMetadata: dataSourceConfig.extractMetadata ? metadata : null,
                  content: content
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

  // Extract Text from File
  const extractTextFromFile = async (blob: Blob, fileName: string): Promise<string> => {
    const fileExtension = fileName.split('.').pop()?.toLowerCase();
    
    try {
      switch (fileExtension) {
        case 'txt':
        case 'md':
        case 'html':
        case 'htm':
        case 'json':
        case 'xml':
        case 'yaml':
        case 'yml':
        case 'js':
        case 'ts':
        case 'jsx':
        case 'tsx':
        case 'py':
        case 'java':
        case 'cpp':
        case 'c':
        case 'h':
        case 'cs':
        case 'php':
        case 'rb':
        case 'go':
        case 'rs':
        case 'log':
          return await blob.text();
          
        case 'pdf':
          // Would integrate with PDF.js
          return `[PDF text extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'csv':
          const csvText = await blob.text();
          const csvLines = csvText.split('\n').slice(0, 100); // Limit to 100 lines
          return csvLines.join('\n');
          
        default:
          console.warn(`Text extraction not supported for file type: ${fileExtension}`);
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
      const changes = await boxApi.getFileChanges(state.lastIngestionTime || undefined);
      
      if (changes.length > 0) {
        // Process changes (upload, update, delete)
        const filesToIngest = changes
          .filter(change => 
            change.event_type === 'ITEM_UPLOAD' || 
            change.event_type === 'ITEM_UPDATE'
          )
          .map(change => ({
            id: change.source.item_id,
            name: change.source.item_name,
            type: 'file' as const,
            // Add other required fields
            ...change.source
          } as BoxFile));
        
        if (filesToIngest.length > 0) {
          await ingestFiles(filesToIngest);
        }
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
  }, [boxApi, state.lastIngestionTime, ingestFiles, onDataSourceError]);

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