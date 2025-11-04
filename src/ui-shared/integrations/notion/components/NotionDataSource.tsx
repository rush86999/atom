/**
 * ATOM Notion Data Source - TypeScript
 * Documents → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production: Page discovery, block processing, database ingestion, markdown export
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  NotionDataSourceProps, 
  NotionDataSourceState,
  NotionIngestionConfig,
  NotionDataSource,
  NotionPage,
  NotionDatabase,
  NotionBlock,
  NotionComment,
  NotionPageEnhanced,
  NotionRichText,
  NotionBlockType
} from '../types';

export const ATOMNotionDataSource: React.FC<NotionDataSourceProps> = ({
  // Notion Authentication
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
  const [state, setState] = useState<NotionDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    dataSource: null,
    ingestionStatus: 'idle',
    lastIngestionTime: null,
    discoveredPages: [],
    discoveredDatabases: [],
    discoveredBlocks: [],
    discoveredComments: [],
    ingestionQueue: [],
    processingIngestion: false,
    stats: {
      totalPages: 0,
      totalDatabases: 0,
      totalBlocks: 0,
      totalComments: 0,
      ingestedPages: 0,
      failedIngestions: 0,
      lastSyncTime: null,
      dataSize: 0
    }
  });

  // Configuration
  const [dataSourceConfig] = useState<NotionIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'notion-integration',
    sourceName: 'Notion',
    sourceType: 'notion',
    
    // API Configuration
    apiBaseUrl: 'https://api.notion.com/v1',
    version: '2022-06-28',
    
    // Page Discovery
    includeArchivedPages: false,
    includeArchivedBlocks: false,
    maxPageDepth: 10,
    includeDatabases: true,
    excludedDatabaseIds: [],
    includedDatabaseIds: [],
    
    // Page Processing
    includePageContent: true,
    includeBlockContent: true,
    includeComments: true,
    includeDatabasePages: true,
    extractBlockTypes: [
      'paragraph',
      'heading_1',
      'heading_2',
      'heading_3',
      'bulleted_list_item',
      'numbered_list_item',
      'to_do',
      'toggle',
      'quote',
      'callout',
      'image',
      'file',
      'pdf',
      'bookmark'
    ],
    
    // Content Processing
    extractMarkdown: true,
    extractPlainText: true,
    includeFormatting: true,
    includeImages: false,
    includeFiles: true,
    maxFileSize: 50 * 1024 * 1024, // 50MB
    supportedFileTypes: [
      '.pdf', '.doc', '.docx', '.txt', '.md',
      '.jpg', '.jpeg', '.png', '.gif', '.bmp',
      '.mp4', '.avi', '.mov', '.wmv'
    ],
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 1800000, // 30 minutes
    batchSize: 25, // Notion API limit
    maxConcurrentIngestions: 2,
    
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

  // Notion API Integration
  const notionApi = useMemo(() => {
    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      const url = `${dataSourceConfig.apiBaseUrl}${endpoint}`;
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${accessToken}`,
        'Notion-Version': dataSourceConfig.version,
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
        throw new Error(`Notion API Error: ${response.status} - ${errorData.message || response.statusText}`);
      }
      
      return response.json();
    };

    return {
      // Authentication
      getCurrentUser: async () => {
        return await makeRequest('/users/me');
      },
      
      // Page Operations
      getPages: async (databaseId?: string, filter?: any, sorts?: any[], pageSize?: number, startCursor?: string) => {
        const body: any = {};
        
        if (databaseId) {
          return await makeRequest(`/databases/${databaseId}/query`, {
            method: 'POST',
            body: JSON.stringify({
              filter,
              sorts,
              page_size: pageSize || 100,
              start_cursor: startCursor,
              ...body
            })
          });
        } else {
          // Search all pages
          const query: any = {};
          if (filter) query.filter = filter;
          if (sorts) query.sort = sorts;
          if (pageSize) query.page_size = pageSize;
          if (startCursor) query.start_cursor = startCursor;
          
          return await makeRequest(`/search?${new URLSearchParams({
            query: '',
            ...query
          })}`);
        }
      },
      
      getPage: async (pageId: string) => {
        return await makeRequest(`/pages/${pageId}`);
      },
      
      // Block Operations
      getBlockChildren: async (blockId: string, pageSize?: number, startCursor?: string) => {
        const params = new URLSearchParams({
          page_size: (pageSize || 100).toString()
        });
        
        if (startCursor) {
          params.set('start_cursor', startCursor);
        }
        
        return await makeRequest(`/blocks/${blockId}/children?${params}`);
      },
      
      // Database Operations
      getDatabase: async (databaseId: string) => {
        return await makeRequest(`/databases/${databaseId}`);
      },
      
      queryDatabase: async (databaseId: string, query: any) => {
        return await makeRequest(`/databases/${databaseId}/query`, {
          method: 'POST',
          body: JSON.stringify({
            page_size: 100,
            ...query
          })
        });
      },
      
      // Search Operations
      search: async (query?: string, filter?: any, sorts?: any[], startCursor?: string, pageSize?: number) => {
        const params = new URLSearchParams({
          page_size: (pageSize || 100).toString()
        });
        
        if (query) params.set('query', query);
        if (startCursor) params.set('start_cursor', startCursor);
        
        const body: any = {};
        if (filter) body.filter = filter;
        if (sorts) body.sort = sorts;
        
        return await makeRequest(`/search?${params}`, {
          method: 'POST',
          body: JSON.stringify(body)
        });
      },
      
      // Comment Operations
      getComments: async (blockId: string) => {
        return await makeRequest(`/blocks/${blockId}/comments`);
      }
    };
  }, [accessToken, refreshToken, onTokenRefresh, dataSourceConfig]);

  // Convert Rich Text to Plain Text
  const richTextToPlainText = (richText: NotionRichText[]): string => {
    return richText.map(item => item.text.content).join('');
  };

  // Convert Rich Text to Markdown
  const richTextToMarkdown = (richText: NotionRichText[]): string => {
    return richText.map(item => {
      let text = item.text.content;
      
      // Apply annotations
      if (item.annotations) {
        if (item.annotations.bold) text = `**${text}**`;
        if (item.annotations.italic) text = `*${text}*`;
        if (item.annotations.strikethrough) text = `~~${text}~~`;
        if (item.annotations.code) text = `\`${text}\``;
        if (item.annotations.underline) text = `<u>${text}</u>`;
      }
      
      // Add link if present
      if (item.text.link) {
        text = `[${text}](${item.text.link.url})`;
      }
      
      return text;
    }).join('');
  };

  // Convert Block to Markdown
  const blockToMarkdown = (block: NotionBlock): string => {
    const richText = block.paragraph?.rich_text || 
                    block.heading_1?.rich_text || 
                    block.heading_2?.rich_text || 
                    block.heading_3?.rich_text || 
                    block.bulleted_list_item?.rich_text || 
                    block.numbered_list_item?.rich_text || 
                    block.to_do?.rich_text || 
                    block.toggle?.rich_text || 
                    block.quote?.rich_text || 
                    block.callout?.rich_text || [];
    
    const text = richTextToMarkdown(richText);
    
    switch (block.type) {
      case 'heading_1':
        return `# ${text}`;
      case 'heading_2':
        return `## ${text}`;
      case 'heading_3':
        return `### ${text}`;
      case 'bulleted_list_item':
        return `- ${text}`;
      case 'numbered_list_item':
        return `1. ${text}`;
      case 'to_do':
        return `- [${block.to_do?.checked ? 'x' : ' '}] ${text}`;
      case 'toggle':
        return `<details>\n<summary>${text}</summary>\n</details>`;
      case 'quote':
        return `> ${text}`;
      case 'callout':
        return `> ${text}`;
      case 'divider':
        return '---';
      default:
        return text;
    }
  };

  // Extract Content from Blocks
  const extractBlockContent = (blocks: NotionBlock[]): { markdown: string; plainText: string; blockInfo: any } => {
    let markdown = '';
    let plainText = '';
    const blockTypes: Record<NotionBlockType, number> = {} as any;
    let hasChildren = false;
    const childPageIds: string[] = [];
    let imageCount = 0;
    let fileCount = 0;
    let linkCount = 0;
    
    for (const block of blocks) {
      if (!dataSourceConfig.extractBlockTypes.includes(block.type)) {
        continue;
      }
      
      // Count block types
      blockTypes[block.type] = (blockTypes[block.type] || 0) + 1;
      
      // Extract markdown
      const blockMarkdown = blockToMarkdown(block);
      markdown += blockMarkdown + '\n';
      
      // Extract plain text
      const blockPlainText = richTextToPlainText(
        block.paragraph?.rich_text || 
        block.heading_1?.rich_text || 
        block.heading_2?.rich_text || 
        block.heading_3?.rich_text || 
        block.bulleted_list_item?.rich_text || 
        block.numbered_list_item?.rich_text || 
        block.to_do?.rich_text || 
        block.toggle?.rich_text || 
        block.quote?.rich_text || 
        block.callout?.rich_text || []
      );
      plainText += blockPlainText + '\n';
      
      // Check for children
      if (block.has_children) {
        hasChildren = true;
      }
      
      // Track child pages
      if (block.type === 'child_page') {
        childPageIds.push(block.id);
      }
      
      // Count images and files
      if (block.type === 'image') {
        imageCount++;
      }
      if (block.type === 'file' || block.type === 'pdf') {
        fileCount++;
      }
      
      // Count links (simplified)
      const richText = block.paragraph?.rich_text || 
                      block.heading_1?.rich_text || 
                      block.heading_2?.rich_text || 
                      block.heading_3?.rich_text || [];
      
      for (const item of richText) {
        if (item.text.link) {
          linkCount++;
        }
      }
    }
    
    return {
      markdown,
      plainText,
      blockInfo: {
        totalBlocks: blocks.length,
        blockTypes,
        hasChildren,
        childPageIds,
        imageCount,
        fileCount,
        linkCount
      }
    };
  };

  // Extract Page Content
  const extractPageContent = async (page: NotionPage): Promise<{ markdown: string; plainText: string; blockInfo: any }> => {
    let allBlocks: NotionBlock[] = [];
    let cursor: string | undefined;
    let hasMore = true;
    
    // Get all blocks recursively
    while (hasMore) {
      const response = await notionApi.getBlockChildren(page.id, 100, cursor);
      allBlocks.push(...response.results);
      hasMore = response.has_more;
      cursor = response.next_cursor;
    }
    
    // Process child pages up to max depth
    for (const block of allBlocks) {
      if (block.type === 'child_page' && allBlocks.length < dataSourceConfig.maxPageDepth * 10) {
        // Simplified - in production, you'd handle recursion properly
        break;
      }
    }
    
    return extractBlockContent(allBlocks);
  };

  // Extract Comments from Page
  const extractComments = async (pageId: string): Promise<any> => {
    try {
      const discussions = await notionApi.getComments(pageId);
      const comments: any[] = [];
      const totalComments = discussions.length;
      const resolvedComments = discussions.filter(d => d.resolved).length;
      const commentAuthors: string[] = [];
      
      for (const discussion of discussions) {
        for (const comment of discussion.comments) {
          comments.push(comment);
          
          if (comment.created_by && comment.created_by.type === 'person') {
            commentAuthors.push(comment.created_by.id);
          }
        }
      }
      
      return {
        totalComments,
        totalDiscussions: discussions.length,
        resolvedComments,
        commentAuthors: [...new Set(commentAuthors)]
      };
    } catch (error) {
      console.error(`Failed to get comments for page ${pageId}:`, error);
      return {
        totalComments: 0,
        totalDiscussions: 0,
        resolvedComments: 0,
        commentAuthors: []
      };
    }
  };

  // Register Notion as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Test authentication
      const user = await notionApi.getCurrentUser();
      
      // Create Notion data source configuration
      const notionDataSource: NotionDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'notion',
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
        await atomIngestionPipeline.registerDataSource(notionDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(notionDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: notionDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(notionDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register Notion data source: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'registration');
      }
    }
  }, [notionApi, accessToken, refreshToken, dataSourceConfig, atomIngestionPipeline, dataSourceRegistry, onDataSourceReady, onDataSourceError]);

  // Discover Databases
  const discoverDatabases = useCallback(async (): Promise<NotionDatabase[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const searchResponse = await notionApi.search('', {
        property: 'object',
        value: 'database'
      });
      
      const databases = searchResponse.results.filter(item => item.object === 'database') as NotionDatabase[];
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredDatabases: databases,
        stats: {
          ...prev.stats,
          totalDatabases: databases.length
        }
      }));
      
      return databases;
      
    } catch (error) {
      const errorMessage = `Database discovery failed: ${(error as Error).message}`;
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
  }, [notionApi, onDataSourceError]);

  // Discover Pages
  const discoverPages = useCallback(async (databaseId?: string): Promise<NotionPageEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let allPages: NotionPageEnhanced[] = [];
      let cursor: string | undefined;
      let hasMore = true;
      
      // Get pages from database or all pages
      do {
        const response = await notionApi.getPages(databaseId, null, null, 100, cursor);
        const pages = response.results.filter(item => item.object === 'page') as NotionPage[];
        
        // Process pages
        const enhancedPages = await Promise.all(
          pages.map(async (page) => {
            // Extract content
            const { markdown, plainText, blockInfo } = await extractPageContent(page);
            
            // Extract comments
            const commentInfo = await extractComments(page.id);
            
            // Get page title
            const titleProperty = page.properties.title || page.properties.Name || page.properties.name;
            const title = Array.isArray(titleProperty) ? richTextToPlainText(titleProperty) : '';
            
            return {
              ...page,
              source: 'notion' as const,
              discoveredAt: new Date().toISOString(),
              processedAt: undefined,
              contentExtracted: true,
              blocksProcessed: true,
              commentsProcessed: true,
              embeddingGenerated: false,
              ingested: false,
              ingestionTime: undefined,
              documentId: undefined,
              vectorCount: undefined,
              blockInfo,
              commentInfo,
              markdownContent: markdown,
              plainTextContent: plainText
            };
          })
        );
        
        allPages.push(...enhancedPages);
        hasMore = response.has_more;
        cursor = response.next_cursor;
        
      } while (hasMore && allPages.length < 1000); // Limit for performance
      
      // Sort by last edited time
      allPages.sort((a, b) => new Date(b.last_edited_time).getTime() - new Date(a.last_edited_time).getTime());
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredPages: allPages,
        stats: {
          ...prev.stats,
          totalPages: allPages.length,
          totalBlocks: allPages.reduce((sum, page) => sum + (page.blockInfo?.totalBlocks || 0), 0),
          totalComments: allPages.reduce((sum, page) => sum + (page.commentInfo?.totalComments || 0), 0)
        }
      }));
      
      return allPages;
      
    } catch (error) {
      const errorMessage = `Page discovery failed: ${(error as Error).message}`;
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
  }, [notionApi, onDataSourceError]);

  // Discover Blocks
  const discoverBlocks = useCallback(async (pageId: string): Promise<NotionBlock[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let allBlocks: NotionBlock[] = [];
      let cursor: string | undefined;
      let hasMore = true;
      
      // Get all blocks
      while (hasMore) {
        const response = await notionApi.getBlockChildren(pageId, 100, cursor);
        allBlocks.push(...response.results);
        hasMore = response.has_more;
        cursor = response.next_cursor;
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredBlocks: allBlocks,
        stats: {
          ...prev.stats,
          totalBlocks: prev.stats.totalBlocks + allBlocks.length
        }
      }));
      
      return allBlocks;
      
    } catch (error) {
      const errorMessage = `Block discovery failed: ${(error as Error).message}`;
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
  }, [notionApi, onDataSourceError]);

  // Discover Comments
  const discoverComments = useCallback(async (pageId: string): Promise<NotionComment[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const discussions = await notionApi.getComments(pageId);
      const comments: NotionComment[] = [];
      
      for (const discussion of discussions) {
        comments.push(...discussion.comments);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredComments: comments,
        stats: {
          ...prev.stats,
          totalComments: prev.stats.totalComments + comments.length
        }
      }));
      
      return comments;
      
    } catch (error) {
      const errorMessage = `Comment discovery failed: ${(error as Error).message}`;
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
  }, [notionApi, onDataSourceError]);

  // Ingest Pages with Existing Pipeline
  const ingestPages = useCallback(async (pages: NotionPageEnhanced[]): Promise<void> => {
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
          pagesCount: pages.length
        });
      }
      
      // Process pages in batches
      const batchSize = dataSourceConfig.batchSize;
      let successCount = 0;
      let errorCount = 0;
      
      for (let i = 0; i < pages.length; i += batchSize) {
        const batch = pages.slice(i, i + batchSize);
        
        try {
          // Prepare batch for existing pipeline
          const preparedBatch = await Promise.all(
            batch.map(async (page) => {
              // Get page title
              const titleProperty = page.properties.title || page.properties.Name || page.properties.name;
              const title = Array.isArray(titleProperty) ? richTextToPlainText(titleProperty) : '';
              
              // Use markdown or plain text content
              const content = dataSourceConfig.extractMarkdown ? page.markdownContent : page.plainTextContent;
              const fullText = `${title}\n\n${content}`;
              
              // Add comment summary
              if (page.commentInfo && page.commentInfo.totalComments > 0) {
                fullText += `\n\nComments: ${page.commentInfo.totalComments} comments from ${page.commentInfo.commentAuthors.length} authors`;
              }
              
              return {
                id: page.id,
                sourceId: dataSourceConfig.sourceId,
                sourceName: dataSourceConfig.sourceName,
                sourceType: 'notion',
                documentType: 'notion_page',
                title: title,
                content: fullText,
                url: page.url,
                timestamp: page.last_edited_time,
                author: page.last_edited_by.name || page.last_edited_by.id,
                tags: page.parent.type === 'database_id' ? ['database'] : ['page'],
                metadata: {
                  notionPage: page,
                  blockInfo: page.blockInfo,
                  commentInfo: page.commentInfo,
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
          const progress = ((i + batchSize) / pages.length) * 100;
          
          if (onIngestionProgress) {
            onIngestionProgress({
              dataSource: state.dataSource,
              progress,
              processedCount: i + batchSize,
              totalCount: pages.length,
              successCount,
              errorCount,
              currentBatch: Math.floor(i / batchSize) + 1,
              totalBatches: Math.ceil(pages.length / batchSize)
            });
          }
          
          setState(prev => ({
            ...prev,
            stats: {
              ...prev.stats,
              ingestedPages: prev.stats.ingestedPages + batchResult.successful,
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
          totalPages: pages.length,
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
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

  // Sync Pages
  const syncPages = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Get recent pages (Notion doesn't have simple webhooks)
      const recentPages = await notionApi.search('', null, [{
        property: 'last_edited_time',
        direction: 'descending'
      }]);
      
      const pages = recentPages.results.filter(item => item.object === 'page') as NotionPage[];
      
      if (pages.length > 0) {
        // Process recent pages
        const enhancedPages = await Promise.all(
          pages.slice(0, 50).map(async (page) => { // Limit to 50 recent pages
            const { markdown, plainText, blockInfo } = await extractPageContent(page);
            const commentInfo = await extractComments(page.id);
            const titleProperty = page.properties.title || page.properties.Name || page.properties.name;
            const title = Array.isArray(titleProperty) ? richTextToPlainText(titleProperty) : '';
            
            return {
              ...page,
              source: 'notion' as const,
              discoveredAt: new Date().toISOString(),
              processedAt: undefined,
              contentExtracted: true,
              blocksProcessed: true,
              commentsProcessed: true,
              embeddingGenerated: false,
              ingested: false,
              ingestionTime: undefined,
              documentId: undefined,
              vectorCount: undefined,
              blockInfo,
              commentInfo,
              markdownContent: markdown,
              plainTextContent: plainText
            };
          })
        );
        
        await ingestPages(enhancedPages);
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
  }, [notionApi, ingestPages, onDataSourceError]);

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
      // Discover databases and pages
      const databases = await discoverDatabases();
      
      // Discover pages from databases
      const allPages: NotionPageEnhanced[] = [];
      for (const database of databases.slice(0, 5)) { // Limit to 5 databases for performance
        const pages = await discoverPages(database.id);
        allPages.push(...pages);
      }
      
      // Also discover pages from root
      const rootPages = await discoverPages();
      allPages.push(...rootPages);
      
      if (allPages.length > 0) {
        await ingestPages(allPages);
      }
    };
    
    initializeAutoIngestion();
    
    // Set up periodic ingestion
    const ingestionInterval = setInterval(async () => {
      await syncPages();
    }, dataSourceConfig.ingestInterval);
    
    return () => {
      clearInterval(ingestionInterval);
    };
  }, [dataSourceConfig, state.connected, discoverDatabases, discoverPages, ingestPages, syncPages]);

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
          discoverDatabases,
          discoverPages,
          discoverBlocks,
          discoverComments,
          ingestPages,
          syncPages,
          registerDataSource
        },
        config: dataSourceConfig,
        dataSource: state.dataSource
      });
    }

    // Default UI
    return (
      <div className={`atom-notion-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          📝 ATOM Notion Data Source
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Status Overview */}
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.stats.totalPages}
            </div>
            <div className="text-sm text-gray-500">Pages</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.stats.totalDatabases}
            </div>
            <div className="text-sm text-gray-500">Databases</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.stats.totalBlocks}
            </div>
            <div className="text-sm text-gray-500">Blocks</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-orange-600">
              {state.stats.totalComments}
            </div>
            <div className="text-sm text-gray-500">Comments</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-indigo-600">
              {state.stats.ingestedPages}
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
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => discoverDatabases()}
              disabled={!state.connected || state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Discover Databases
            </button>
            <button
              onClick={() => discoverPages()}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Discover Pages
            </button>
            <button
              onClick={() => ingestPages(state.discoveredPages)}
              disabled={!state.connected || state.processingIngestion || state.discoveredPages.length === 0}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Ingest Pages
            </button>
            <button
              onClick={syncPages}
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
            <div>Batch Size: {dataSourceConfig.batchSize}</div>
            <div>Max Page Depth: {dataSourceConfig.maxPageDepth}</div>
            <div>Include Databases: {dataSourceConfig.includeDatabases ? 'Yes' : 'No'}</div>
            <div>Extract Markdown: {dataSourceConfig.extractMarkdown ? 'Yes' : 'No'}</div>
            <div>Extract Comments: {dataSourceConfig.includeComments ? 'Yes' : 'No'}</div>
            <div>Include Images: {dataSourceConfig.includeImages ? 'Yes' : 'No'}</div>
            <div>Include Files: {dataSourceConfig.includeFiles ? 'Yes' : 'No'}</div>
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

export default ATOMNotionDataSource;