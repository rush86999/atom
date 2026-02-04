/**
 * ATOM Jira Data Source - TypeScript
 * Project Management → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomJiraDataSourceProps, 
  AtomJiraDataSourceState,
  AtomJiraIngestionConfig,
  AtomJiraDataSource,
  JiraIssue,
  JiraProject,
  JiraBoard,
  JiraComment,
  JiraAttachment,
  JiraIssueEnhanced,
  JiraUser
} from '../types';

export const ATOMJiraDataSource: React.FC<AtomJiraDataSourceProps> = ({
  // Jira Authentication
  serverUrl,
  username,
  apiToken,
  oauthToken,
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
  const [state, setState] = useState<AtomJiraDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    dataSource: null,
    ingestionStatus: 'idle',
    lastIngestionTime: null,
    discoveredIssues: [],
    discoveredProjects: [],
    discoveredBoards: [],
    discoveredComments: [],
    discoveredAttachments: [],
    ingestionQueue: [],
    processingIngestion: false,
    stats: {
      totalIssues: 0,
      totalProjects: 0,
      totalBoards: 0,
      totalComments: 0,
      totalAttachments: 0,
      ingestedIssues: 0,
      failedIngestions: 0,
      lastSyncTime: null,
      dataSize: 0
    }
  });

  // Configuration
  const [dataSourceConfig] = useState<AtomJiraIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'jira-integration',
    sourceName: 'Jira',
    sourceType: 'jira',
    
    // API Configuration
    apiBaseUrl: '/rest/api/3',
    jqlApiUrl: '/rest/api/3/search',
    serverUrl: serverUrl || '',
    username: username,
    apiToken: apiToken,
    oauthToken: oauthToken,
    
    // Project Discovery
    includedProjects: config.includedProjects || [],
    excludedProjects: config.excludedProjects || [],
    projectTypes: config.projectTypes || ['software', 'service_desk', 'business'],
    
    // Issue Discovery
    jqlQuery: config.jqlQuery || 'status != "Done" ORDER BY created DESC',
    includeSubtasks: config.includeSubtasks ?? true,
    includeArchived: config.includeArchived ?? false,
    maxIssuesPerProject: config.maxIssuesPerProject ?? 1000,
    issueDateRange: config.issueDateRange,
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 1800000, // 30 minutes
    realTimeIngest: true,
    batchSize: 50,
    maxConcurrentIngestions: 2,
    
    // Processing
    includeComments: true,
    includeAttachments: true,
    includeHistory: true,
    includeLinkedIssues: true,
    maxAttachmentSize: 50 * 1024 * 1024, // 50MB
    extractMarkdown: true,
    
    // Sync Settings
    useWebhooks: true,
    webhookEvents: ['jira:issue_created', 'jira:issue_updated', 'jira:comment_added', 'jira:attachment_added'],
    syncInterval: 600000, // 10 minutes
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

  // Jira API Integration (simplified for data source)
  const jiraApi = useMemo(() => {
    const baseUrl = dataSourceConfig.serverUrl.replace(/\/$/, '');
    const authString = dataSourceConfig.username && dataSourceConfig.apiToken 
      ? 'Basic ' + btoa(`${dataSourceConfig.username}:${dataSourceConfig.apiToken}`)
      : `Bearer ${dataSourceConfig.oauthToken}`;

    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      const url = `${baseUrl}${endpoint}`;
      const headers: Record<string, string> = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': authString,
        ...options.headers as Record<string, string>
      };

      try {
        const response = await fetch(url, {
          ...options,
          headers
        });

        if (response.status === 401) {
          throw new Error('Authentication failed - please check your credentials');
        }

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(`Jira API Error: ${response.status} - ${errorData.message || response.statusText}`);
        }

        return response.json();
      } catch (error) {
        console.error('Jira API request failed:', error);
        throw error;
      }
    };

    return {
      // Authentication
      authenticate: async () => {
        return {
          accessToken: dataSourceConfig.oauthToken || 'basic_auth',
          tokenType: 'Bearer',
          expiresIn: 3600
        };
      },

      // Project Operations
      getProjects: async (startAt = 0, maxResults = 100) => {
        const response = await makeRequest(`${dataSourceConfig.apiBaseUrl}/project/search?startAt=${startAt}&maxResults=${maxResults}`);
        return response.values || [];
      },

      getProject: async (projectId: string) => {
        return await makeRequest(`${dataSourceConfig.apiBaseUrl}/project/${projectId}`);
      },

      // Issue Operations
      getIssues: async (jql: string, startAt = 0, maxResults = 100, fields?: string[]) => {
        const fieldString = fields ? fields.join(',') : 'summary,description,comment,status,priority,assignee,project,created,updated,reporter,labels,components,issuetype';
        return await makeRequest(`${dataSourceConfig.jqlApiUrl}?jql=${encodeURIComponent(jql)}&startAt=${startAt}&maxResults=${maxResults}&fields=${fieldString}`);
      },

      getIssue: async (issueId: string) => {
        return await makeRequest(`${dataSourceConfig.apiBaseUrl}/issue/${issueId}?expand=renderedFields,comments,attachments,history`);
      },

      // Comment Operations
      getComments: async (issueId: string) => {
        const response = await makeRequest(`${dataSourceConfig.apiBaseUrl}/issue/${issueId}/comment`);
        return response.comments || [];
      },

      // Attachment Operations
      getAttachment: async (attachmentId: string) => {
        return await makeRequest(`${dataSourceConfig.apiBaseUrl}/attachment/${attachmentId}`);
      },

      downloadAttachment: async (attachmentId: string) => {
        const attachment = await jiraApi.getAttachment(attachmentId);
        const response = await fetch(attachment.content);
        const blob = await response.blob();
        return {
          id: attachment.id,
          filename: attachment.filename,
          author: attachment.author,
          created: attachment.created,
          size: attachment.size,
          mimeType: attachment.mimeType,
          content: attachment.content,
          thumbnail: attachment.thumbnail,
          blob: blob
        };
      },

      // Board Operations
      getBoards: async (startAt = 0, maxResults = 100) => {
        const response = await makeRequest(`${dataSourceConfig.apiBaseUrl}/board?startAt=${startAt}&maxResults=${maxResults}`);
        return response.values || [];
      },

      getBoardIssues: async (boardId: string, startAt = 0, maxResults = 100) => {
        return await makeRequest(`${dataSourceConfig.apiBaseUrl}/board/${boardId}/issue?startAt=${startAt}&maxResults=${maxResults}`);
      },

      // User Operations
      getUsers: async (startAt = 0, maxResults = 100) => {
        const response = await makeRequest(`${dataSourceConfig.apiBaseUrl}/users/search?startAt=${startAt}&maxResults=${maxResults}`);
        return response.values || [];
      }
    };
  }, [dataSourceConfig]);

  // Extract Markdown from Jira Content
  const extractMarkdown = (content: string): string => {
    if (!content) return '';
    
    // Convert Jira markup to markdown
    return content
      // Headers
      .replace(/^h([1-6])\./gm, '#'.repeat(parseInt('$1')) + ' ')
      // Bold
      .replace(/\*([^*]+)\*/g, '**$1**')
      // Italic
      .replace(/\_([^_]+)\_/g, '*$1*')
      // Code
      .replace(/\{\{([^}]+)\}\}/g, '`$1`')
      // Code blocks
      .replace(/\{code:([^}]+)\}([\s\S]*?)\{code\}/g, '```$1\n$2\n```')
      // Links
      .replace(/\[([^|]+)\|([^\]]+)\]/g, '[$1]($2)')
      // Lists
      .replace(/^\- /gm, '- ')
      .replace(/^\# /gm, '1. ')
      // Blockquote
      .replace(/bq\. (.*)/g, '> $1')
      // Images
      .replace(/!([^|]+)\|([^\]]*)!/g, '![$1]($2)');
  };

  // Process Issue Content
  const processIssueContent = async (issue: JiraIssue): Promise<{
    markdownContent: string;
    plainTextContent: string;
    commentInfo: any;
    attachmentInfo: any;
    linkInfo: any;
  }> => {
    const summary = issue.fields.summary || '';
    const description = issue.fields.description || '';
    
    // Extract markdown and plain text
    const markdownDescription = extractMarkdown(description);
    const plainTextDescription = description
      .replace(/h[1-6]\./g, '')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/\_([^_]+)\_/g, '$1')
      .replace(/\{\{([^}]+)\}\}/g, '$1')
      .replace(/\{code:([^}]+)\}([\s\S]*?)\{code\}/g, '$2')
      .replace(/<[^>]*>/g, '');
    
    // Combine summary and description
    const markdownContent = `# ${summary}\n\n${markdownDescription}`;
    const plainTextContent = `${summary}\n\n${plainTextDescription}`;
    
    // Process comments
    let commentInfo = {
      totalComments: 0,
      processedComments: [],
      totalAuthors: [],
      lastCommentDate: null as string | null
    };
    
    if (dataSourceConfig.includeComments && issue.fields.comment?.comments) {
      const comments = issue.fields.comment.comments;
      commentInfo.totalComments = comments.length;
      commentInfo.processedComments = comments.map(comment => ({
        id: comment.id,
        author: comment.author.displayName,
        body: comment.body,
        markdown: extractMarkdown(comment.body),
        created: comment.created,
        updated: comment.updated
      }));
      
      commentInfo.totalAuthors = [...new Set(comments.map(c => c.author.displayName))];
      commentInfo.lastCommentDate = comments.length > 0 
        ? comments[comments.length - 1].created 
        : null;
      
      // Add comments to content
      if (comments.length > 0) {
        const commentsMarkdown = comments.map(comment => {
          const authorName = comment.author.displayName;
          const commentMarkdown = extractMarkdown(comment.body);
          return `## Comment by ${authorName}\n\n${commentMarkdown}`;
        }).join('\n\n---\n\n');
        
        markdownContent += `\n\n---\n\n## Comments\n\n${commentsMarkdown}`;
        plainTextContent += '\n\n' + comments.map(c => `Comment by ${c.author.displayName}: ${c.body}`).join('\n');
      }
    }
    
    // Process attachments
    let attachmentInfo = {
      totalAttachments: 0,
      totalSize: 0,
      processedAttachments: [],
      fileTypes: [],
      hasImages: false,
      hasDocuments: false
    };
    
    if (dataSourceConfig.includeAttachments && issue.fields.attachments) {
      const attachments = issue.fields.attachments.filter(att => 
        att.size <= dataSourceConfig.maxAttachmentSize
      );
      
      attachmentInfo.totalAttachments = attachments.length;
      attachmentInfo.totalSize = attachments.reduce((sum, att) => sum + att.size, 0);
      
      attachmentInfo.processedAttachments = attachments.map(attachment => ({
        id: attachment.id,
        filename: attachment.filename,
        mimeType: attachment.mimeType,
        size: attachment.size,
        url: attachment.content,
        thumbnail: attachment.thumbnail
      }));
      
      attachmentInfo.fileTypes = [...new Set(attachments.map(a => a.mimeType))];
      attachmentInfo.hasImages = attachments.some(a => a.mimeType.startsWith('image/'));
      attachmentInfo.hasDocuments = attachments.some(a => 
        a.mimeType.includes('document') || a.mimeType.includes('pdf') || a.mimeType.includes('text')
      );
      
      // Add attachment info to content
      if (attachments.length > 0) {
        const attachmentsList = attachments.map(att => `- ${att.filename} (${att.mimeType}, ${formatFileSize(att.size)})`).join('\n');
        markdownContent += `\n\n---\n\n## Attachments\n\n${attachmentsList}`;
        plainTextContent += `\n\nAttachments:\n${attachmentsList}`;
      }
    }
    
    // Process issue links
    let linkInfo = {
      linkedIssues: [],
      blockedBy: [],
      blocks: [],
      duplicates: [],
      isDuplicatedBy: []
    };
    
    if (dataSourceConfig.includeLinkedIssues && issue.fields.issuelinks) {
      linkInfo.linkedIssues = issue.fields.issuelinks.map(link => link.outwardIssue || link.inwardIssue).filter(Boolean);
      
      // Categorize links
      issue.fields.issuelinks.forEach(link => {
        const targetIssue = link.outwardIssue || link.inwardIssue;
        if (!targetIssue) return;
        
        switch (link.type?.outward) {
          case 'blocks':
            linkInfo.blocks.push(targetIssue);
            break;
          case 'is blocked by':
            linkInfo.blockedBy.push(targetIssue);
            break;
          case 'duplicates':
            linkInfo.duplicates.push(targetIssue);
            break;
          case 'is duplicated by':
            linkInfo.isDuplicatedBy.push(targetIssue);
            break;
        }
      });
    }
    
    return {
      markdownContent,
      plainTextContent,
      commentInfo,
      attachmentInfo,
      linkInfo
    };
  };

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Register Jira as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Create Jira data source configuration
      const jiraDataSource: AtomJiraDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'jira',
        config: dataSourceConfig,
        authentication: {
          type: dataSourceConfig.oauthToken ? 'oauth' : 'basic',
          accessToken: dataSourceConfig.oauthToken || dataSourceConfig.apiToken,
          username: dataSourceConfig.username,
          serverUrl: dataSourceConfig.serverUrl
        },
        capabilities: {
          fileDiscovery: false,
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
        await atomIngestionPipeline.registerDataSource(jiraDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(jiraDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: jiraDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(jiraDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register Jira data source: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'registration');
      }
    }
  }, [dataSourceConfig, atomIngestionPipeline, dataSourceRegistry, onDataSourceReady, onDataSourceError]);

  // Discover Projects
  const discoverProjects = useCallback(async (): Promise<JiraProject[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const projects = await jiraApi.getProjects();
      
      // Filter projects based on configuration
      const filteredProjects = projects.filter(project => {
        // Check if project is explicitly included
        if (dataSourceConfig.includedProjects.length > 0) {
          return dataSourceConfig.includedProjects.includes(project.key);
        }
        
        // Check if project is excluded
        if (dataSourceConfig.excludedProjects.includes(project.key)) {
          return false;
        }
        
        // Check project type
        if (dataSourceConfig.projectTypes.length > 0) {
          return dataSourceConfig.projectTypes.includes(project.projectTypeKey);
        }
        
        return true;
      });
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredProjects: filteredProjects,
        stats: {
          ...prev.stats,
          totalProjects: filteredProjects.length
        }
      }));
      
      return filteredProjects;
      
    } catch (error) {
      const errorMessage = `Project discovery failed: ${(error as Error).message}`;
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
  }, [jiraApi, dataSourceConfig, onDataSourceError]);

  // Discover Issues
  const discoverIssues = useCallback(async (projectIds?: string[]): Promise<JiraIssueEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      let allIssues: JiraIssueEnhanced[] = [];
      
      // Build JQL query based on configuration
      let jql = dataSourceConfig.jqlQuery || 'status != "Done" ORDER BY created DESC';
      
      if (projectIds && projectIds.length > 0) {
        const projectClause = projectIds.map(pid => `project = ${pid}`).join(' OR ');
        jql = `(${projectClause}) AND ${jql}`;
      }
      
      // Add date range if specified
      if (dataSourceConfig.issueDateRange) {
        const start = dataSourceConfig.issueDateRange.start.toISOString().split('T')[0];
        const end = dataSourceConfig.issueDateRange.end.toISOString().split('T')[0];
        jql = `${jql} AND created >= "${start}" AND created <= "${end}"`;
      }
      
      // Get issues in batches
      let startAt = 0;
      const maxResults = 100;
      let totalFound = 0;
      
      do {
        const response = await jiraApi.getIssues(jql, startAt, maxResults);
        const issues = response.issues || [];
        
        // Process issues
        const enhancedIssues = await Promise.all(
          issues.map(async (issue) => {
            // Process issue content
            const { markdownContent, plainTextContent, commentInfo, attachmentInfo, linkInfo } = await processIssueContent(issue);
            
            return {
              ...issue,
              source: 'jira' as const,
              discoveredAt: new Date().toISOString(),
              processedAt: undefined,
              commentsProcessed: true,
              attachmentsProcessed: true,
              embeddingGenerated: false,
              ingested: false,
              ingestionTime: undefined,
              documentId: undefined,
              vectorCount: undefined,
              linkInfo,
              attachmentInfo,
              commentInfo,
              markdownContent,
              plainTextContent
            };
          })
        );
        
        allIssues.push(...enhancedIssues);
        startAt += maxResults;
        totalFound = response.total || 0;
        
        // Stop if we've reached max issues per project
        if (allIssues.length >= dataSourceConfig.maxIssuesPerProject) {
          break;
        }
        
      } while (startAt < totalFound);
      
      // Sort by creation date
      allIssues.sort((a, b) => new Date(b.fields.created).getTime() - new Date(a.fields.created).getTime());
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredIssues: allIssues,
        stats: {
          ...prev.stats,
          totalIssues: allIssues.length,
          totalComments: allIssues.reduce((sum, issue) => sum + (issue.commentInfo?.totalComments || 0), 0),
          totalAttachments: allIssues.reduce((sum, issue) => sum + (issue.attachmentInfo?.totalAttachments || 0), 0)
        }
      }));
      
      return allIssues;
      
    } catch (error) {
      const errorMessage = `Issue discovery failed: ${(error as Error).message}`;
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
  }, [jiraApi, dataSourceConfig, onDataSourceError]);

  // Discover Boards
  const discoverBoards = useCallback(async (): Promise<JiraBoard[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const boards = await jiraApi.getBoards();
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredBoards: boards,
        stats: {
          ...prev.stats,
          totalBoards: boards.length
        }
      }));
      
      return boards;
      
    } catch (error) {
      const errorMessage = `Board discovery failed: ${(error as Error).message}`;
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
  }, [jiraApi, onDataSourceError]);

  // Ingest Issues with Existing Pipeline
  const ingestIssues = useCallback(async (issues: JiraIssueEnhanced[]): Promise<void> => {
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
          issuesCount: issues.length
        });
      }
      
      // Process issues in batches
      const batchSize = dataSourceConfig.batchSize;
      let successCount = 0;
      let errorCount = 0;
      
      for (let i = 0; i < issues.length; i += batchSize) {
        const batch = issues.slice(i, i + batchSize);
        
        try {
          // Prepare batch for existing pipeline
          const preparedBatch = batch.map((issue) => {
            const content = dataSourceConfig.extractMarkdown ? issue.markdownContent : issue.plainTextContent;
            
            return {
              id: issue.id,
              sourceId: dataSourceConfig.sourceId,
              sourceName: dataSourceConfig.sourceName,
              sourceType: 'jira',
              documentType: 'jira_issue',
              title: issue.fields.summary,
              content: content,
              url: issue.self,
              timestamp: issue.fields.created,
              author: issue.fields.reporter.displayName,
              tags: [
                'project:' + issue.fields.project.key,
                'type:' + issue.fields.issuetype.name,
                'status:' + issue.fields.status.name,
                ...(issue.fields.labels || [])
              ],
              metadata: {
                jiraIssue: issue,
                jiraKey: issue.key,
                issueType: issue.fields.issuetype.name,
                status: issue.fields.status.name,
                priority: issue.fields.priority?.name,
                assignee: issue.fields.assignee?.displayName,
                project: issue.fields.project.key,
                linkInfo: issue.linkInfo,
                commentInfo: issue.commentInfo,
                attachmentInfo: issue.attachmentInfo,
                extractedAt: new Date().toISOString()
              },
              content: content,
              chunkSize: 1000,
              chunkOverlap: 100
            };
          });
          
          // Send batch to existing ATOM ingestion pipeline
          const batchResult = await atomIngestionPipeline.ingestBatch({
            dataSourceId: dataSourceConfig.sourceId,
            items: preparedBatch,
            config: dataSourceConfig.pipelineConfig
          });
          
          successCount += batchResult.successful;
          errorCount += batchResult.failed;
          
          // Update progress
          const progress = ((i + batchSize) / issues.length) * 100;
          
          if (onIngestionProgress) {
            onIngestionProgress({
              dataSource: state.dataSource,
              progress,
              processedCount: i + batchSize,
              totalCount: issues.length,
              successCount,
              errorCount,
              currentBatch: Math.floor(i / batchSize) + 1,
              totalBatches: Math.ceil(issues.length / batchSize)
            });
          }
          
          setState(prev => ({
            ...prev,
            stats: {
              ...prev.stats,
              ingestedIssues: prev.stats.ingestedIssues + batchResult.successful,
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
          totalIssues: issues.length,
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

  // Sync Issues
  const syncIssues = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Get recent issues (simplified sync)
      const recentIssues = await discoverIssues(dataSourceConfig.includedProjects);
      
      if (recentIssues.length > 0) {
        await ingestIssues(recentIssues);
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
  }, [discoverIssues, dataSourceConfig.includedProjects, ingestIssues, onDataSourceError]);

  // Initialize Data Source
  useEffect(() => {
    if (dataSourceConfig.serverUrl && (dataSourceConfig.apiToken || dataSourceConfig.oauthToken) && atomIngestionPipeline) {
      registerDataSource();
    }
  }, [dataSourceConfig.serverUrl, dataSourceConfig.apiToken, dataSourceConfig.oauthToken, atomIngestionPipeline, registerDataSource]);

  // Start Auto Ingestion
  useEffect(() => {
    if (!dataSourceConfig.autoIngest || !state.connected) {
      return;
    }
    
    // Initial discovery and ingestion
    const initializeAutoIngestion = async () => {
      // Discover projects and issues
      const projects = await discoverProjects();
      const issues = await discoverIssues(projects.map(p => p.key));
      
      if (issues.length > 0) {
        await ingestIssues(issues);
      }
    };
    
    initializeAutoIngestion();
    
    // Set up periodic ingestion
    const ingestionInterval = setInterval(async () => {
      if (dataSourceConfig.incrementalSync) {
        await syncIssues();
      } else {
        const projects = await discoverProjects();
        const issues = await discoverIssues(projects.map(p => p.key));
        if (issues.length > 0) {
          await ingestIssues(issues);
        }
      }
    }, dataSourceConfig.ingestInterval);
    
    // Set up periodic sync
    const syncInterval = setInterval(() => {
      syncIssues();
    }, dataSourceConfig.syncInterval);
    
    return () => {
      clearInterval(ingestionInterval);
      clearInterval(syncInterval);
    };
  }, [dataSourceConfig, state.connected, discoverProjects, discoverIssues, ingestIssues, syncIssues]);

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
          discoverProjects,
          discoverIssues,
          discoverBoards,
          ingestIssues,
          syncIssues,
          registerDataSource
        },
        config: dataSourceConfig,
        dataSource: state.dataSource
      });
    }

    // Default UI
    return (
      <div className={`atom-jira-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          🎯 ATOM Jira Data Source
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Status Overview */}
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.stats.totalIssues}
            </div>
            <div className="text-sm text-gray-500">Issues</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.stats.totalProjects}
            </div>
            <div className="text-sm text-gray-500">Projects</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.stats.totalBoards}
            </div>
            <div className="text-sm text-gray-500">Boards</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-orange-600">
              {state.stats.totalComments}
            </div>
            <div className="text-sm text-gray-500">Comments</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-indigo-600">
              {state.stats.ingestedIssues}
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
              onClick={() => discoverProjects()}
              disabled={!state.connected || state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Discover Projects
            </button>
            <button
              onClick={() => discoverIssues()}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Discover Issues
            </button>
            <button
              onClick={() => discoverBoards()}
              disabled={!state.connected || state.loading}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Discover Boards
            </button>
            <button
              onClick={() => ingestIssues(state.discoveredIssues)}
              disabled={!state.connected || state.processingIngestion || state.discoveredIssues.length === 0}
              className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
            >
              Ingest Issues
            </button>
            <button
              onClick={syncIssues}
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
            <div>Server URL: {dataSourceConfig.serverUrl}</div>
            <div>Authentication: {dataSourceConfig.oauthToken ? 'OAuth' : 'Basic'}</div>
            <div>Auto Ingest: {dataSourceConfig.autoIngest ? 'Enabled' : 'Disabled'}</div>
            <div>Ingestion Interval: {(dataSourceConfig.ingestInterval / 60000).toFixed(0)} minutes</div>
            <div>Sync Interval: {(dataSourceConfig.syncInterval / 60000).toFixed(0)} minutes</div>
            <div>Batch Size: {dataSourceConfig.batchSize}</div>
            <div>Max Issues Per Project: {dataSourceConfig.maxIssuesPerProject}</div>
            <div>JQL Query: {dataSourceConfig.jqlQuery}</div>
            <div>Include Comments: {dataSourceConfig.includeComments ? 'Yes' : 'No'}</div>
            <div>Include Attachments: {dataSourceConfig.includeAttachments ? 'Yes' : 'No'}</div>
            <div>Include History: {dataSourceConfig.includeHistory ? 'Yes' : 'No'}</div>
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

export default ATOMJiraDataSource;