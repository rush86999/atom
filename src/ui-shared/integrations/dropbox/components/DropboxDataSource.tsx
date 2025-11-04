/**
 * ATOM Dropbox Data Source - TypeScript
 * File Storage → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production: Auto-discovery, batch processing, real-time sync
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomDropboxDataSourceProps, 
  AtomDropboxDataSourceState,
  AtomDropboxIngestionConfig,
  AtomDropboxDataSource,
  DropboxFile,
  DropboxFolder,
  DropboxFileEnhanced
} from '../types';

export const ATOMDropboxDataSource: React.FC<AtomDropboxDataSourceProps> = ({
  // Dropbox Authentication
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
  const [state, setState] = useState<AtomDropboxDataSourceState>({
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
  const [dataSourceConfig] = useState<AtomDropboxIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'dropbox-integration',
    sourceName: 'Dropbox',
    sourceType: 'dropbox',
    
    // API Configuration
    apiBaseUrl: 'https://api.dropboxapi.com/2',
    apiVersion: '2',
    businessAccount: false,
    
    // File Discovery
    supportedFileTypes: [
      '.txt', '.md', '.pdf', '.doc', '.docx', 
      '.rtf', '.odt', '.html', '.htm', '.csv',
      '.json', '.xml', '.yaml', '.yml', '.log',
      '.js', '.ts', '.jsx', '.tsx', '.py', '.java',
      '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'
    ],
    maxFileSize: 150 * 1024 * 1024, // 150MB (Dropbox limit)
    excludePatterns: [
      '*/node_modules/*',
      '*/.git/*',
      '*/dist/*',
      '*/build/*',
      '*/temp/*',
      '*/tmp/*'
    ],
    includeShared: true,
    includeDeleted: false,
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 3600000, // 1 hour
    realTimeIngest: true,
    batchSize: 25, // Dropbox API limit
    maxConcurrentIngestions: 2,
    
    // Sync Settings
    syncInterval: 300000, // 5 minutes
    incrementalSync: true,
    
    // Processing
    extractMetadata: true,
    generateThumbnails: true,
    extractText: true,
    chunkSize: 1000,
    chunkOverlap: 100,
    thumbnailSize: 'w128h128',
    
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

  // Dropbox API Integration
  const dropboxApi = useMemo(() => {
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
        throw new Error(`Dropbox API Error: ${response.status} - ${errorData.error_summary || response.statusText}`);
      }
      
      return response.json();
    };

    return {
      // File Discovery
      discoverFiles: async (path = '', recursive = true): Promise<DropboxFile[]> => {
        const discoveredFiles: DropboxFile[] = [];
        const pathsToProcess: string[] = [path];
        
        while (pathsToProcess.length > 0) {
          const currentPath = pathsToProcess.shift()!;
          
          const data = await makeRequest('/files/list_folder', {
            method: 'POST',
            body: JSON.stringify({
              path: currentPath || '',
              recursive: false
            })
          });
          
          for (const item of data.entries) {
            if (item['.tag'] === 'folder' && recursive) {
              pathsToProcess.push(item.path_lower);
            } else if (item['.tag'] === 'file') {
              // Check if file is supported
              const fileExtension = item.name?.split('.').pop()?.toLowerCase();
              const isSupported = fileExtension && 
                dataSourceConfig.supportedFileTypes.includes(`.${fileExtension}`);
              const isSizeValid = !item.size || item.size <= dataSourceConfig.maxFileSize;
              const isNotExcluded = !isFileExcluded(item.path_display);
              
              if (isSupported && isSizeValid && isNotExcluded) {
                discoveredFiles.push({
                  ...item,
                  source: 'dropbox',
                  discoveredAt: new Date().toISOString()
                });
              }
            }
          }
          
          // Handle pagination
          if (data.has_more && data.cursor) {
            let hasMore = true;
            let cursor = data.cursor;
            
            while (hasMore) {
              const moreData = await makeRequest('/files/list_folder/continue', {
                method: 'POST',
                body: JSON.stringify({ cursor })
              });
              
              for (const item of moreData.entries) {
                if (item['.tag'] === 'folder' && recursive) {
                  pathsToProcess.push(item.path_lower);
                } else if (item['.tag'] === 'file') {
                  const fileExtension = item.name?.split('.').pop()?.toLowerCase();
                  const isSupported = fileExtension && 
                    dataSourceConfig.supportedFileTypes.includes(`.${fileExtension}`);
                  const isSizeValid = !item.size || item.size <= dataSourceConfig.maxFileSize;
                  const isNotExcluded = !isFileExcluded(item.path_display);
                  
                  if (isSupported && isSizeValid && isNotExcluded) {
                    discoveredFiles.push({
                      ...item,
                      source: 'dropbox',
                      discoveredAt: new Date().toISOString()
                    });
                  }
                }
              }
              
              hasMore = moreData.has_more;
              cursor = moreData.cursor;
            }
          }
        }
        
        return discoveredFiles;
      },
      
      getFileMetadata: async (filePath: string): Promise<any> => {
        return await makeRequest('/files/get_metadata', {
          method: 'POST',
          body: JSON.stringify({
            path: filePath,
            include_media_info: true,
            include_deleted: false,
            include_has_explicit_shared_members: true
          })
        });
      },
      
      downloadFile: async (filePath: string): Promise<Blob> => {
        // Get temporary link first
        const linkData = await makeRequest('/files/get_temporary_link', {
          method: 'POST',
          body: JSON.stringify({ path: filePath })
        });
        
        const response = await fetch(linkData.link);
        return response.blob();
      },
      
      getThumbnail: async (filePath: string, size = dataSourceConfig.thumbnailSize): Promise<Blob> => {
        try {
          const thumbnailData = await makeRequest('/files/get_thumbnail_v2', {
            method: 'POST',
            body: JSON.stringify({
              path: filePath,
              format: 'png',
              size: size
            })
          });
          
          // Convert base64 to blob
          const base64Data = thumbnailData.replace(/^data:image\/png;base64,/, '');
          const binaryData = atob(base64Data);
          const array = new Uint8Array(binaryData.length);
          
          for (let i = 0; i < binaryData.length; i++) {
            array[i] = binaryData.charCodeAt(i);
          }
          
          return new Blob([array], { type: 'image/png' });
        } catch (error) {
          // Thumbnail not available, return empty blob
          return new Blob([], { type: 'image/png' });
        }
      },
      
      getRecentFiles: async (hours = 24): Promise<DropboxFile[]> => {
        const since = new Date(Date.now() - (hours * 3600 * 1000)).toISOString();
        
        return await makeRequest('/files/search_v2', {
          method: 'POST',
          body: JSON.stringify({
            query: '',
            options: {
              include_highlights: false,
              include_content: false,
              file_status: 'active',
              file_extensions: dataSourceConfig.supportedFileTypes.map(ext => ext.slice(1)),
              filename_only: true,
              max_results: 1000
            }
          })
        }).then(data => data.matches.map((match: any) => match.metadata).filter((file: any) => 
          file.server_modified >= since && file['.tag'] === 'file'
        ));
      },
      
      // File Watching
      getFileChanges: async (cursor?: string): Promise<any> => {
        const body: any = {};
        if (cursor) {
          body.cursor = cursor;
        } else {
          body.path = '';
          include_media_info = true;
          include_deleted = false;
        }
        
        return await makeRequest('/files/list_folder', {
          method: 'POST',
          body: JSON.stringify(body)
        });
      },
      
      // Account Info
      getAccountInfo: async (): Promise<any> => {
        return await makeRequest('/users/get_current_account');
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

  // Register Dropbox as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Create Dropbox data source configuration
      const dropboxDataSource: AtomDropboxDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'dropbox',
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
        await atomIngestionPipeline.registerDataSource(dropboxDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(dropboxDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: dropboxDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(dropboxDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register Dropbox data source: ${(error as Error).message}`;
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
  const discoverFiles = useCallback(async (fullDiscovery = false): Promise<DropboxFileEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let discoveredFiles: DropboxFileEnhanced[] = [];
      
      if (fullDiscovery) {
        // Full file discovery
        const rawFiles = await dropboxApi.discoverFiles('', true);
        discoveredFiles = await Promise.all(
          rawFiles.map(async (file) => {
            // Get file metadata
            const metadata = await dropboxApi.getFileMetadata(file.path_lower);
            
            // Generate thumbnail if enabled
            let thumbnailGenerated = false;
            if (dataSourceConfig.generateThumbnails) {
              try {
                await dropboxApi.getThumbnail(file.path_lower);
                thumbnailGenerated = true;
              } catch (error) {
                // Thumbnail generation failed, continue
              }
            }
            
            return {
              ...file,
              source: 'dropbox' as const,
              path_lower: file.path_lower,
              path_display: file.path_display,
              textExtracted: false,
              previewGenerated: thumbnailGenerated,
              embeddingGenerated: false,
              ingested: false,
              documentId: undefined,
              vectorCount: undefined,
              metadata: metadata
            };
          })
        );
      } else {
        // Incremental discovery (recent files)
        const rawFiles = await dropboxApi.getRecentFiles(24);
        discoveredFiles = rawFiles.map((file) => ({
          ...file,
          source: 'dropbox' as const,
          path_lower: file.path_lower,
          path_display: file.path_display,
          textExtracted: false,
          previewGenerated: false,
          embeddingGenerated: false,
          ingested: false,
          documentId: undefined,
          vectorCount: undefined
        }));
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
  }, [dropboxApi, dataSourceConfig, onDataSourceError]);

  // Discover Folders
  const discoverFolders = useCallback(async (fullDiscovery = false): Promise<DropboxFolderEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Simplified folder discovery
      const discoveredFolders: DropboxFolderEnhanced[] = [];
      
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
  const ingestFiles = useCallback(async (files: DropboxFileEnhanced[]): Promise<void> => {
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
                const fileBlob = await dropboxApi.downloadFile(file.path_lower);
                content = await extractTextFromFile(fileBlob, file.name || '');
              }
              
              return {
                id: file.id,
                sourceId: dataSourceConfig.sourceId,
                sourceName: dataSourceConfig.sourceName,
                sourceType: 'dropbox',
                fileName: file.name,
                filePath: file.path_display,
                contentType: file.media_info?.['.tag'],
                size: file.size,
                createdAt: file.client_modified,
                modifiedAt: file.server_modified,
                metadata: {
                  dropboxMetadata: file.metadata,
                  extractedMetadata: file.metadata,
                  content: content,
                  thumbnailGenerated: file.previewGenerated
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
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, dropboxApi, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

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
          // Would integrate with PDF.js for web, or PDF parsing library for desktop
          return `[PDF content extraction not implemented - Size: ${blob.size} bytes]`;
          
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
      
      // Get recent files (Dropbox doesn't have real-time webhooks for file changes without premium)
      const recentFiles = await dropboxApi.getRecentFiles(Math.floor(dataSourceConfig.syncInterval / 3600000));
      
      if (recentFiles.length > 0) {
        const enhancedFiles: DropboxFileEnhanced[] = recentFiles.map(file => ({
          ...file,
          source: 'dropbox',
          path_lower: file.path_lower,
          path_display: file.path_display,
          textExtracted: false,
          previewGenerated: false,
          embeddingGenerated: false,
          ingested: false,
          documentId: undefined,
          vectorCount: undefined
        }));
        
        await ingestFiles(enhancedFiles);
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
  }, [dropboxApi, dataSourceConfig, ingestFiles, onDataSourceError]);

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
      <div className={`atom-dropbox-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          💾 ATOM Dropbox Data Source
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
            <div>Generate Thumbnails: {dataSourceConfig.generateThumbnails ? 'Enabled' : 'Disabled'}</div>
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

export default ATOMDropboxDataSource;