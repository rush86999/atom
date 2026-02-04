/**
 * ATOM Slack Data Source - TypeScript
 * Messaging → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production: Real-time events, message threads, file attachments, user context
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomSlackDataSourceProps, 
  AtomSlackDataSourceState,
  AtomSlackIngestionConfig,
  AtomSlackDataSource,
  SlackMessage,
  SlackChannel,
  SlackUser,
  SlackMessageEnhanced,
  SlackFile
} from '../types';

export const ATOMSlackDataSource: React.FC<AtomSlackDataSourceProps> = ({
  // Slack Authentication
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
  const [state, setState] = useState<AtomSlackDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    dataSource: null,
    ingestionStatus: 'idle',
    lastIngestionTime: null,
    discoveredMessages: [],
    discoveredChannels: [],
    discoveredUsers: [],
    discoveredFiles: [],
    ingestionQueue: [],
    processingIngestion: false,
    stats: {
      totalMessages: 0,
      totalChannels: 0,
      totalUsers: 0,
      totalFiles: 0,
      ingestedMessages: 0,
      failedIngestions: 0,
      lastSyncTime: null,
      dataSize: 0
    }
  });

  // Configuration
  const [dataSourceConfig] = useState<AtomSlackIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'slack-integration',
    sourceName: 'Slack',
    sourceType: 'slack',
    
    // API Configuration
    apiBaseUrl: 'https://slack.com/api',
    scopes: [
      'channels:read',
      'channels:history',
      'users:read',
      'files:read',
      'search:read'
    ],
    
    // Message Discovery
    messageTypes: ['message', 'file_share', 'message_changed'],
    channels: [],
    users: [],
    dateRange: {
      start: new Date(Date.now() - 30 * 24 * 3600 * 1000), // 30 days ago
      end: new Date()
    },
    includeBotMessages: false,
    includeReplies: true,
    includeThreads: true,
    maxMessageAge: 365, // 1 year
    
    // Channel Filtering
    channelTypes: ['public_channel'],
    excludeArchivedChannels: true,
    includePrivateChannels: false,
    includeDMs: false,
    includeGroupDMs: false,
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 600000, // 10 minutes
    batchSize: 100,
    maxConcurrentIngestions: 5,
    
    // Processing
    extractMentions: true,
    extractLinks: true,
    extractAttachments: true,
    extractEmojis: false,
    parseMarkdown: true,
    includeUserContext: true,
    includeChannelContext: true,
    
    // File Processing
    includeFileAttachments: true,
    downloadFiles: true,
    maxFileSize: 50 * 1024 * 1024, // 50MB
    
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

  // Slack API Integration
  const slackApi = useMemo(() => {
    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      const url = `${dataSourceConfig.apiBaseUrl}${endpoint}`;
      const params = new URLSearchParams({ token: accessToken });
      
      const response = await fetch(`${url}?${params}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });
      
      const data = await response.json();
      
      if (!data.ok) {
        if (data.error === 'not_authed' || data.error === 'invalid_auth') {
          if (refreshToken && onTokenRefresh) {
            const newTokens = await onTokenRefresh(refreshToken);
            if (newTokens.success) {
              // Retry with new token
              const newParams = new URLSearchParams({ token: newTokens.accessToken });
              return fetch(`${url}?${newParams}`, {
                ...options,
                headers: {
                  'Content-Type': 'application/json',
                  ...options.headers
                }
              }).then(res => res.json());
            }
          }
        }
        throw new Error(`Slack API Error: ${data.error || 'Unknown error'}`);
      }
      
      return data;
    };

    return {
      // Authentication
      testAuth: async () => {
        return await makeRequest('/auth.test');
      },
      
      // User Operations
      getUsers: async (cursor?: string) => {
        const params = cursor ? `&cursor=${cursor}` : '';
        return await makeRequest(`/users.list?limit=1000${params}`);
      },
      
      getUser: async (userId: string) => {
        return await makeRequest(`/users.info?user=${userId}`);
      },
      
      // Channel Operations
      getChannels: async (cursor?: string) => {
        const params = cursor ? `&cursor=${cursor}` : '';
        const channelTypes = dataSourceConfig.channelTypes.includes('public_channel') ? 
          'public_channel' : 'private_channel';
        return await makeRequest(`/conversations.list?types=${channelTypes}&exclude_archived=${dataSourceConfig.excludeArchivedChannels}&limit=1000${params}`);
      },
      
      getChannel: async (channelId: string) => {
        return await makeRequest(`/conversations.info?channel=${channelId}`);
      },
      
      getChannelHistory: async (channelId: string, options = {}) => {
        const {
          latest = 'now',
          oldest = dataSourceConfig.dateRange.start.toISOString().split('T')[0],
          count = 100,
          inclusive = true
        } = options;
        
        const params = `&latest=${latest}&oldest=${oldest}&count=${count}&inclusive=${inclusive}`;
        return await makeRequest(`/conversations.history?channel=${channelId}${params}`);
      },
      
      // Message Operations
      getMessage: async (channelId: string, messageId: string) => {
        return await makeRequest(`/conversations.history?channel=${channelId}&latest=${messageId}&limit=1&inclusive=true`);
      },
      
      getThreadReplies: async (channelId: string, threadTs: string) => {
        return await makeRequest(`/conversations.replies?channel=${channelId}&ts=${threadTs}`);
      },
      
      searchMessages: async (query: string, options = {}) => {
        const {
          sort = 'timestamp',
          sort_dir = 'desc',
          count = 100,
          page = 1
        } = options;
        
        const dateRange = `from:${dataSourceConfig.dateRange.start.toISOString().split('T')[0]} to:${dataSourceConfig.dateRange.end.toISOString().split('T')[0]}`;
        const fullQuery = `${dateRange} ${query}`;
        
        const params = `&query=${encodeURIComponent(fullQuery)}&sort=${sort}&sort_dir=${sort_dir}&count=${count}&page=${page}`;
        return await makeRequest(`/search.messages${params}`);
      },
      
      // File Operations
      getFiles: async (options = {}) => {
        const {
          user,
          channel,
          ts_from,
          ts_to,
          types,
          count = 100,
          page = 1
        } = options;
        
        let params = `&count=${count}&page=${page}`;
        if (user) params += `&user=${user}`;
        if (channel) params += `&channel=${channel}`;
        if (ts_from) params += `&ts_from=${ts_from}`;
        if (ts_to) params += `&ts_to=${ts_to}`;
        if (types) params += `&types=${types.join(',')}`;
        
        return await makeRequest(`/files.list${params}`);
      },
      
      getFile: async (fileId: string) => {
        return await makeRequest(`/files.info?file=${fileId}`);
      },
      
      downloadFile: async (fileId: string) => {
        const fileInfo = await slackApi.getFile(fileId);
        const response = await fetch(fileInfo.url_private_download, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        return response.blob();
      },
      
      // Real-time Events (simulated with polling for now)
      getRecentMessages: async (minutes = 10) => {
        const since = new Date(Date.now() - (minutes * 60 * 1000)).toISOString();
        
        // Get channels
        const channels: SlackChannel[] = [];
        let cursor: string | undefined;
        let hasMore = true;
        
        while (hasMore) {
          const response = await slackApi.getChannels(cursor);
          channels.push(...response.channels);
          hasMore = response.response_metadata?.next_cursor ? true : false;
          cursor = response.response_metadata?.next_cursor;
        }
        
        // Get recent messages from all channels
        const allMessages: SlackMessage[] = [];
        
        for (const channel of channels.slice(0, 10)) { // Limit to 10 channels for performance
          try {
            const history = await slackApi.getChannelHistory(channel.id, {
              oldest: since.split('T')[0],
              count: 50
            });
            allMessages.push(...history.messages.map(msg => ({
              ...msg,
              channel: channel.id
            })));
          } catch (error) {
            console.error(`Failed to get history for channel ${channel.id}:`, error);
          }
        }
        
        return allMessages;
      }
    };
  }, [accessToken, refreshToken, onTokenRefresh, dataSourceConfig]);

  // Extract Message Components
  const extractMessageComponents = (message: SlackMessage): any => {
    const components = {
      mentions: [] as string[],
      channels: [] as string[],
      urls: [] as string[],
      hashtags: [] as string[],
      emojis: [] as string[],
      files: message.files || [],
      reactions: [] as any[]
    };
    
    // Extract mentions (<@U123456789>)
    const mentionMatches = message.text.match(/<@([UW][A-Z0-9]+)(?:\|[^>]+)?>/g);
    if (mentionMatches) {
      components.mentions = mentionMatches.map(match => match.slice(2, -1));
    }
    
    // Extract channel references (<#C123456789|channel-name>)
    const channelMatches = message.text.match(/<#([C][A-Z0-9]+)(?:\|[^>]+)?>/g);
    if (channelMatches) {
      components.channels = channelMatches.map(match => match.slice(2, -1).split('|')[0]);
    }
    
    // Extract URLs
    const urlMatches = message.text.match(/<https?:\/\/[^>]+>/g);
    if (urlMatches) {
      components.urls = urlMatches.map(match => match.slice(1, -1).split('|')[0]);
    }
    
    // Extract hashtags
    const hashtagMatches = message.text.match(/#\w+/g);
    if (hashtagMatches) {
      components.hashtags = hashtagMatches;
    }
    
    // Extract emojis (simple extraction)
    const emojiMatches = message.text.match(/:[\w-]+:/g);
    if (emojiMatches) {
      components.emojis = emojiMatches.map(match => match.slice(1, -1));
    }
    
    return components;
  };

  // Clean Message Text
  const cleanMessageText = (message: SlackMessage): string => {
    let text = message.text;
    
    // Replace Slack markup
    text = text.replace(/<@([UW][A-Z0-9]+)(?:\|[^>]+)?>/g, '@$1');
    text = text.replace(/<#([C][A-Z0-9]+)(?:\|[^>]+)?>/g, '#$1');
    text = text.replace(/<https?:\/\/[^>]+(?:\|[^>]+)?>/g, '$1'); // Keep URL, remove text
    text = text.replace(/<!here|!everyone|!channel>/g, '@$1');
    
    return text;
  };

  // Register Slack as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Test authentication
      const authResponse = await slackApi.testAuth();
      if (!authResponse.ok) {
        throw new Error('Authentication test failed');
      }
      
      // Create Slack data source configuration
      const slackDataSource: AtomSlackDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'slack',
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
        await atomIngestionPipeline.registerDataSource(slackDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(slackDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: slackDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(slackDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register Slack data source: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'registration');
      }
    }
  }, [slackApi, accessToken, refreshToken, dataSourceConfig, atomIngestionPipeline, dataSourceRegistry, onDataSourceReady, onDataSourceError]);

  // Discover Channels
  const discoverChannels = useCallback(async (): Promise<SlackChannel[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const channels: SlackChannel[] = [];
      let cursor: string | undefined;
      let hasMore = true;
      
      while (hasMore) {
        const response = await slackApi.getChannels(cursor);
        channels.push(...response.channels);
        hasMore = response.response_metadata?.next_cursor ? true : false;
        cursor = response.response_metadata?.next_cursor;
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredChannels: channels,
        stats: {
          ...prev.stats,
          totalChannels: channels.length
        }
      }));
      
      return channels;
      
    } catch (error) {
      const errorMessage = `Channel discovery failed: ${(error as Error).message}`;
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
  }, [slackApi, onDataSourceError]);

  // Discover Users
  const discoverUsers = useCallback(async (): Promise<SlackUser[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const users: SlackUser[] = [];
      let cursor: string | undefined;
      let hasMore = true;
      
      while (hasMore) {
        const response = await slackApi.getUsers(cursor);
        users.push(...response.members);
        hasMore = response.response_metadata?.next_cursor ? true : false;
        cursor = response.response_metadata?.next_cursor;
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredUsers: users,
        stats: {
          ...prev.stats,
          totalUsers: users.length
        }
      }));
      
      return users;
      
    } catch (error) {
      const errorMessage = `User discovery failed: ${(error as Error).message}`;
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
  }, [slackApi, onDataSourceError]);

  // Discover Messages
  const discoverMessages = useCallback(async (channelIds?: string[], dateRange?: { start: Date; end: Date }): Promise<SlackMessageEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const channels = channelIds || state.discoveredChannels.map(c => c.id);
      const range = dateRange || dataSourceConfig.dateRange;
      const allMessages: SlackMessageEnhanced[] = [];
      
      for (const channelId of channels.slice(0, 10)) { // Limit to 10 channels for performance
        try {
          let cursor: string | undefined;
          let hasMore = true;
          
          while (hasMore) {
            const history = await slackApi.getChannelHistory(channelId, {
              latest: range.end.toISOString(),
              oldest: range.start.toISOString(),
              count: 100
            });
            
            // Process messages
            const enhancedMessages: SlackMessageEnhanced[] = history.messages.map((message: SlackMessage) => {
              const components = extractMessageComponents(message);
              const cleanedText = cleanMessageText(message);
              
              return {
                ...message,
                source: 'slack' as const,
                discoveredAt: new Date().toISOString(),
                processedAt: undefined,
                textExtracted: true,
                filesProcessed: false,
                embeddingGenerated: false,
                ingested: false,
                ingestionTime: undefined,
                documentId: undefined,
                vectorCount: undefined,
                mention_info: {
                  users: components.mentions,
                  channels: components.channels,
                  everyone: cleanedText.includes('@everyone') || cleanedText.includes('@channel'),
                  here: cleanedText.includes('@here')
                },
                attachments_info: message.files || []
              };
            });
            
            allMessages.push(...enhancedMessages);
            hasMore = history.has_more && enhancedMessages.length > 0;
          }
          
        } catch (error) {
          console.error(`Failed to discover messages for channel ${channelId}:`, error);
        }
      }
      
      // Sort by timestamp
      allMessages.sort((a, b) => parseFloat(b.ts) - parseFloat(a.ts));
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredMessages: allMessages,
        stats: {
          ...prev.stats,
          totalMessages: allMessages.length
        }
      }));
      
      return allMessages;
      
    } catch (error) {
      const errorMessage = `Message discovery failed: ${(error as Error).message}`;
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
  }, [slackApi, state.discoveredChannels, dataSourceConfig, onDataSourceError]);

  // Discover Files
  const discoverFiles = useCallback(async (): Promise<SlackFile[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const dateFrom = Math.floor(dataSourceConfig.dateRange.start.getTime() / 1000);
      const dateTo = Math.floor(dataSourceConfig.dateRange.end.getTime() / 1000);
      
      const files: SlackFile[] = [];
      let page = 1;
      let hasMore = true;
      
      while (hasMore) {
        const response = await slackApi.getFiles({
          ts_from: dateFrom.toString(),
          ts_to: dateTo.toString(),
          count: 100,
          page
        });
        
        files.push(...response.files);
        hasMore = response.paging.page < response.paging.pages;
        page++;
        
        if (files.length > 1000) break; // Limit for performance
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredFiles: files,
        stats: {
          ...prev.stats,
          totalFiles: files.length
        }
      }));
      
      return files;
      
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
  }, [slackApi, dataSourceConfig, onDataSourceError]);

  // Ingest Messages with Existing Pipeline
  const ingestMessages = useCallback(async (messages: SlackMessageEnhanced[]): Promise<void> => {
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
          messagesCount: messages.length
        });
      }
      
      // Process messages in batches
      const batchSize = dataSourceConfig.batchSize;
      let successCount = 0;
      let errorCount = 0;
      
      for (let i = 0; i < messages.length; i += batchSize) {
        const batch = messages.slice(i, i + batchSize);
        
        try {
          // Prepare batch for existing pipeline
          const preparedBatch = await Promise.all(
            batch.map(async (message) => {
              // Get user and channel info if context is enabled
              let userInfo: SlackUser | undefined;
              let channelInfo: SlackChannel | undefined;
              
              if (dataSourceConfig.includeUserContext && message.user) {
                userInfo = await slackApi.getUser(message.user).catch(() => undefined);
              }
              
              if (dataSourceConfig.includeChannelContext && message.channel) {
                channelInfo = await slackApi.getChannel(message.channel).catch(() => undefined);
              }
              
              // Process file attachments
              let fileAttachments: any[] = [];
              if (dataSourceConfig.includeFileAttachments && message.attachments_info) {
                fileAttachments = await Promise.all(
                  message.attachments_info.slice(0, 3).map(async (file: SlackFile) => {
                    let content = '';
                    if (dataSourceConfig.downloadFiles && file.size && file.size <= dataSourceConfig.maxFileSize) {
                      try {
                        const fileBlob = await slackApi.downloadFile(file.id);
                        content = await extractTextFromFile(fileBlob, file.name || '', file.mimetype || '');
                      } catch (error) {
                        console.error(`Failed to download file ${file.id}:`, error);
                      }
                    }
                    
                    return {
                      id: file.id,
                      name: file.name,
                      mimetype: file.mimetype,
                      size: file.size,
                      url: file.url_private,
                      content: content,
                      download_successful: !!content
                    };
                  })
                );
              }
              
              // Construct the full text content
              let fullText = message.text;
              if (fileAttachments.length > 0) {
                fullText += '\n\nAttachments:\n' + fileAttachments
                  .map(f => `${f.name} (${f.mimetype})`)
                  .join(', ');
              }
              
              return {
                id: `${message.channel}_${message.ts}`,
                sourceId: dataSourceConfig.sourceId,
                sourceName: dataSourceConfig.sourceName,
                sourceType: 'slack',
                messageType: message.subtype || 'message',
                channelId: message.channel,
                channelName: channelInfo?.name || message.channel,
                userId: message.user,
                userName: userInfo?.name || userInfo?.real_name || message.user,
                message: fullText,
                timestamp: new Date(parseFloat(message.ts) * 1000).toISOString(),
                threadTs: message.thread_ts,
                replyCount: message.reply_count || 0,
                metadata: {
                  slackMessage: message,
                  userInfo: userInfo,
                  channelInfo: channelInfo,
                  mentionInfo: message.mention_info,
                  fileAttachments: fileAttachments,
                  extractedAt: new Date().toISOString()
                },
                content: fullText,
                chunkSize: 1000,
                chunkOverlap: 100
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
          const progress = ((i + batchSize) / messages.length) * 100;
          
          if (onIngestionProgress) {
            onIngestionProgress({
              dataSource: state.dataSource,
              progress,
              processedCount: i + batchSize,
              totalCount: messages.length,
              successCount,
              errorCount,
              currentBatch: Math.floor(i / batchSize) + 1,
              totalBatches: Math.ceil(messages.length / batchSize)
            });
          }
          
          setState(prev => ({
            ...prev,
            stats: {
              ...prev.stats,
              ingestedMessages: prev.stats.ingestedMessages + batchResult.successful,
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
          totalMessages: messages.length,
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
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, slackApi, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

  // Extract Text from File
  const extractTextFromFile = async (blob: Blob, fileName: string, mimeType: string): Promise<string> => {
    try {
      switch (mimeType) {
        case 'text/plain':
        case 'text/markdown':
        case 'text/csv':
        case 'application/json':
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
        case 'application/xml':
        case 'text/yaml':
          return await blob.text();
          
        case 'application/pdf':
          // Would integrate with PDF.js
          return `[PDF content extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'application/vnd.ms-excel':
        case 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
          const excelText = await blob.text();
          const lines = excelText.split('\n').slice(0, 100); // Limit to 100 lines
          return lines.join('\n');
          
        case 'application/msword':
        case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
          // Would integrate with docx.js
          return `[Word document content extraction not implemented - Size: ${blob.size} bytes]`;
          
        default:
          console.warn(`Text extraction not supported for MIME type: ${mimeType}`);
          return '';
      }
    } catch (error) {
      console.error(`Error extracting text from ${fileName}:`, error);
      return '';
    }
  };

  // Sync Messages
  const syncMessages = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Get recent messages (Slack doesn't have easy webhooks without paid plan)
      const recentMessages = await slackApi.getRecentMessages(10); // Last 10 minutes
      
      if (recentMessages.length > 0) {
        const enhancedMessages: SlackMessageEnhanced[] = recentMessages.map(message => {
          const components = extractMessageComponents(message);
          const cleanedText = cleanMessageText(message);
          
          return {
            ...message,
            source: 'slack' as const,
            discoveredAt: new Date().toISOString(),
            processedAt: undefined,
            textExtracted: true,
            filesProcessed: false,
            embeddingGenerated: false,
            ingested: false,
            ingestionTime: undefined,
            documentId: undefined,
            vectorCount: undefined,
            mention_info: {
              users: components.mentions,
              channels: components.channels,
              everyone: cleanedText.includes('@everyone') || cleanedText.includes('@channel'),
              here: cleanedText.includes('@here')
            },
            attachments_info: message.files || []
          };
        });
        
        await ingestMessages(enhancedMessages);
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
  }, [slackApi, ingestMessages, onDataSourceError]);

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
      // Discover channels, users, and messages
      const channels = await discoverChannels();
      const users = await discoverUsers();
      const messages = await discoverMessages(channels.map(c => c.id));
      
      if (messages.length > 0) {
        await ingestMessages(messages);
      }
    };
    
    initializeAutoIngestion();
    
    // Set up periodic ingestion
    const ingestionInterval = setInterval(async () => {
      await syncMessages();
    }, dataSourceConfig.ingestInterval);
    
    return () => {
      clearInterval(ingestionInterval);
    };
  }, [dataSourceConfig, state.connected, discoverChannels, discoverUsers, discoverMessages, ingestMessages, syncMessages]);

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
          discoverChannels,
          discoverUsers,
          discoverMessages,
          discoverFiles,
          ingestMessages,
          syncMessages,
          registerDataSource
        },
        config: dataSourceConfig,
        dataSource: state.dataSource
      });
    }

    // Default UI
    return (
      <div className={`atom-slack-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          💬 ATOM Slack Data Source
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Status Overview */}
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.stats.totalMessages}
            </div>
            <div className="text-sm text-gray-500">Messages</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.stats.totalChannels}
            </div>
            <div className="text-sm text-gray-500">Channels</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.stats.totalUsers}
            </div>
            <div className="text-sm text-gray-500">Users</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-orange-600">
              {state.stats.totalFiles}
            </div>
            <div className="text-sm text-gray-500">Files</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-indigo-600">
              {state.stats.ingestedMessages}
            </div>
            <div className="text-sm text-gray-500">Ingested</div>
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
              onClick={() => discoverChannels()}
              disabled={!state.connected || state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Discover Channels
            </button>
            <button
              onClick={() => discoverUsers()}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Discover Users
            </button>
            <button
              onClick={() => discoverMessages()}
              disabled={!state.connected || state.loading}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Discover Messages
            </button>
            <button
              onClick={() => ingestMessages(state.discoveredMessages)}
              disabled={!state.connected || state.processingIngestion || state.discoveredMessages.length === 0}
              className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
            >
              Ingest Messages
            </button>
            <button
              onClick={syncMessages}
              disabled={!state.connected || state.loading}
              className="bg-indigo-500 text-white px-4 py-2 rounded hover:bg-indigo-600 disabled:bg-indigo-300"
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
            <div>Batch Size: {dataSourceConfig.batchSize}</div>
            <div>Date Range: {dataSourceConfig.dateRange.start.toLocaleDateString()} - {dataSourceConfig.dateRange.end.toLocaleDateString()}</div>
            <div>Channel Types: {dataSourceConfig.channelTypes.join(', ')}</div>
            <div>Include Replies: {dataSourceConfig.includeReplies ? 'Yes' : 'No'}</div>
            <div>Include File Attachments: {dataSourceConfig.includeFileAttachments ? 'Yes' : 'No'}</div>
            <div>Download Files: {dataSourceConfig.downloadFiles ? 'Yes' : 'No'}</div>
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

export default ATOMSlackDataSource;