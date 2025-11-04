/**
 * ATOM Gmail Data Source - TypeScript
 * Email → ATOM Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production: Real-time sync, attachment processing, contact extraction
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  AtomGmailDataSourceProps, 
  AtomGmailDataSourceState,
  AtomGmailIngestionConfig,
  AtomGmailDataSource,
  GmailMessage,
  GmailThread,
  GmailLabel,
  GmailAttachment,
  GmailMessageEnhanced,
  GmailContact
} from '../types';

export const ATOMGmailDataSource: React.FC<AtomGmailDataSourceProps> = ({
  // Gmail Authentication
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
  const [state, setState] = useState<AtomGmailDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    dataSource: null,
    ingestionStatus: 'idle',
    lastIngestionTime: null,
    discoveredMessages: [],
    discoveredThreads: [],
    discoveredLabels: [],
    discoveredAttachments: [],
    discoveredContacts: [],
    ingestionQueue: [],
    processingIngestion: false,
    stats: {
      totalMessages: 0,
      totalThreads: 0,
      totalLabels: 0,
      totalAttachments: 0,
      totalContacts: 0,
      ingestedMessages: 0,
      failedIngestions: 0,
      lastSyncTime: null,
      dataSize: 0
    }
  });

  // Configuration
  const [dataSourceConfig] = useState<AtomGmailIngestionConfig>(() => ({
    // Data Source Identity
    sourceId: 'gmail-integration',
    sourceName: 'Gmail',
    sourceType: 'gmail',
    
    // API Configuration
    apiBaseUrl: 'https://gmail.googleapis.com/gmail/v1',
    scopes: [
      'https://www.googleapis.com/auth/gmail.readonly',
      'https://www.googleapis.com/auth/gmail.labels',
      'https://www.googleapis.com/auth/gmail.modify'
    ],
    userId: 'me',
    
    // Message Discovery
    folders: ['INBOX', 'SENT'],
    dateRange: {
      start: new Date(Date.now() - 30 * 24 * 3600 * 1000), // 30 days ago
      end: new Date()
    },
    includeSpam: false,
    includeTrash: false,
    includeDrafts: false,
    
    // Label Filtering
    includedLabels: ['INBOX', 'SENT'],
    excludedLabels: ['SPAM', 'TRASH'],
    
    // Search Filtering
    searchQuery: '',
    maxResults: 1000,
    
    // Ingestion Settings
    autoIngest: true,
    ingestInterval: 900000, // 15 minutes
    batchSize: 50,
    maxConcurrentIngestions: 3,
    
    // Processing
    extractHeaders: true,
    extractBody: true,
    extractAttachments: true,
    parseHtml: true,
    extractCalendar: false,
    extractContacts: true,
    maxAttachmentSize: 25 * 1024 * 1024, // 25MB (Gmail limit)
    supportedAttachmentTypes: [
      'text/plain',
      'text/html',
      'text/csv',
      'application/json',
      'application/xml',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'image/jpeg',
      'image/png',
      'image/gif',
      'application/zip',
      'application/x-rar-compressed'
    ],
    
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

  // Gmail API Integration
  const gmailApi = useMemo(() => {
    const makeRequest = async (endpoint: string, options: RequestInit = {}) => {
      const url = `${dataSourceConfig.apiBaseUrl}/users/${dataSourceConfig.userId}${endpoint}`;
      const params = new URLSearchParams({ access_token: accessToken });
      
      const response = await fetch(`${url}?${params}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        if (data.error?.code === 401) {
          if (refreshToken && onTokenRefresh) {
            const newTokens = await onTokenRefresh(refreshToken);
            if (newTokens.success) {
              // Retry with new token
              const newParams = new URLSearchParams({ access_token: newTokens.accessToken });
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
        throw new Error(`Gmail API Error: ${data.error?.message || response.statusText}`);
      }
      
      return data;
    };

    return {
      // Authentication
      getProfile: async () => {
        return await makeRequest('/profile');
      },
      
      // Message Operations
      getMessages: async (labelIds?: string[], pageToken?: string, maxResults?: number) => {
        const query: string[] = [];
        
        // Build search query
        if (labelIds && labelIds.length > 0) {
          query.push(`label:${labelIds.join(' OR label:')}`);
        }
        
        if (!dataSourceConfig.includeSpam) {
          query.push('-in:spam');
        }
        
        if (!dataSourceConfig.includeTrash) {
          query.push('-in:trash');
        }
        
        if (dataSourceConfig.searchQuery) {
          query.push(dataSourceConfig.searchQuery);
        }
        
        // Add date range
        const after = Math.floor(dataSourceConfig.dateRange.start.getTime() / 1000);
        const before = Math.floor(dataSourceConfig.dateRange.end.getTime() / 1000);
        query.push(`after:${after}`);
        query.push(`before:${before}`);
        
        const params = new URLSearchParams({
          q: query.join(' '),
          maxResults: (maxResults || dataSourceConfig.maxResults).toString()
        });
        
        if (pageToken) {
          params.set('pageToken', pageToken);
        }
        
        return await makeRequest(`/messages/search?${params}`);
      },
      
      getMessage: async (messageId: string, format: 'full' | 'raw' | 'metadata' | 'minimal' = 'full') => {
        const params = new URLSearchParams({
          format
        });
        
        return await makeRequest(`/messages/${messageId}?${params}`);
      },
      
      getThread: async (threadId: string) => {
        const params = new URLSearchParams({
          format: 'full'
        });
        
        return await makeRequest(`/threads/${threadId}?${params}`);
      },
      
      // Label Operations
      getLabels: async () => {
        return await makeRequest('/labels');
      },
      
      // Attachment Operations
      getAttachment: async (messageId: string, attachmentId: string) => {
        const params = new URLSearchParams();
        
        return await makeRequest(`/messages/${messageId}/attachments/${attachmentId}?${params}`);
      },
      
      downloadAttachment: async (messageId: string, attachmentId: string, filename: string): Promise<Blob> => {
        const attachment = await gmailApi.getAttachment(messageId, attachmentId);
        
        // Decode base64 data
        const binaryString = atob(attachment.data);
        const bytes = new Uint8Array(binaryString.length);
        
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        
        const mimeType = attachment.mimeType || 'application/octet-stream';
        return new Blob([bytes], { type: mimeType });
      },
      
      // History Operations
      getHistory: async (historyId?: string, labelIds?: string[]) => {
        const params = new URLSearchParams({
          historyTypes: 'messageAdded,messageDeleted,labelAdded,labelRemoved'
        });
        
        if (historyId) {
          params.set('startHistoryId', historyId);
        }
        
        if (labelIds && labelIds.length > 0) {
          params.set('labelIds', labelIds.join(','));
        }
        
        return await makeRequest(`/history?${params}`);
      },
      
      // Batch Operations
      batchGet: async (messageIds: string[]) => {
        // For simplicity, make multiple requests
        const messages = await Promise.all(
          messageIds.map(id => gmailApi.getMessage(id))
        );
        
        return { messages };
      }
    };
  }, [accessToken, refreshToken, onTokenRefresh, dataSourceConfig]);

  // Extract Headers from Message
  const extractHeaders = (message: GmailMessage): any => {
    const headers: Record<string, string> = {};
    
    if (message.payload.headers) {
      for (const header of message.payload.headers) {
        headers[header.name.toLowerCase()] = header.value;
      }
    }
    
    return {
      from: headers['from'] || '',
      to: headers['to'] ? headers['to'].split(',').map(s => s.trim()) : [],
      cc: headers['cc'] ? headers['cc'].split(',').map(s => s.trim()) : [],
      bcc: headers['bcc'] ? headers['bcc'].split(',').map(s => s.trim()) : [],
      subject: headers['subject'] || '',
      date: headers['date'] || '',
      messageId: headers['message-id'] || '',
      inReplyTo: headers['in-reply-to'] || '',
      references: headers['references'] ? headers['references'].split(',').map(s => s.trim()) : [],
      listId: headers['list-id'] || '',
      priority: headers['x-priority'] || headers['priority'] || '',
      importance: headers['importance'] || ''
    };
  };

  // Extract Body from Message
  const extractBody = (payload: any): { text: string; html: string } => {
    let text = '';
    let html = '';
    
    const extractParts = (parts: any[]) => {
      for (const part of parts) {
        if (part.mimeType === 'text/plain' && part.body.data) {
          text += Buffer.from(part.body.data, 'base64').toString('utf-8');
        } else if (part.mimeType === 'text/html' && part.body.data) {
          html += Buffer.from(part.body.data, 'base64').toString('utf-8');
        } else if (part.parts) {
          extractParts(part.parts);
        }
      }
    };
    
    if (payload.mimeType === 'text/plain' && payload.body.data) {
      text = Buffer.from(payload.body.data, 'base64').toString('utf-8');
    } else if (payload.mimeType === 'text/html' && payload.body.data) {
      html = Buffer.from(payload.body.data, 'base64').toString('utf-8');
    } else if (payload.parts) {
      extractParts(payload.parts);
    }
    
    return { text, html };
  };

  // Extract Attachments from Message
  const extractAttachments = async (message: GmailMessage): Promise<GmailAttachmentInfo> => {
    const attachments: GmailAttachment[] = [];
    let totalSize = 0;
    const fileTypes = new Set<string>();
    let hasImages = false;
    let hasDocuments = false;
    let hasArchives = false;
    
    const extractParts = async (parts: any[], messageId: string) => {
      for (const part of parts) {
        if (part.filename && part.body.attachmentId) {
          const isSupported = dataSourceConfig.supportedAttachmentTypes.includes(part.mimeType);
          const isSizeValid = part.body.size <= dataSourceConfig.maxAttachmentSize;
          
          if (isSupported && isSizeValid) {
            const attachment: GmailAttachment = {
              messageId,
              attachmentId: part.body.attachmentId,
              filename: part.filename,
              mimeType: part.mimeType,
              size: part.body.size
            };
            
            attachments.push(attachment);
            totalSize += part.body.size;
            
            // Track file types
            const fileExtension = part.filename.split('.').pop()?.toLowerCase();
            fileTypes.add(part.mimeType);
            
            if (part.mimeType.startsWith('image/')) hasImages = true;
            if (isDocumentType(part.mimeType)) hasDocuments = true;
            if (isArchiveType(part.mimeType)) hasArchives = true;
          }
        } else if (part.parts) {
          await extractParts(part.parts, messageId);
        }
      }
    };
    
    if (message.payload.parts) {
      await extractParts(message.payload.parts, message.id);
    }
    
    return {
      totalAttachments: attachments.length,
      totalSize,
      processedAttachments: attachments,
      fileTypes: Array.from(fileTypes),
      hasImages,
      hasDocuments,
      hasArchives
    };
  };

  // Check if MIME type is a document
  const isDocumentType = (mimeType: string): boolean => {
    return [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'text/plain',
      'text/csv',
      'application/json',
      'application/xml'
    ].includes(mimeType);
  };

  // Check if MIME type is an archive
  const isArchiveType = (mimeType: string): boolean => {
    return [
      'application/zip',
      'application/x-rar-compressed',
      'application/x-7z-compressed',
      'application/gzip',
      'application/x-tar'
    ].includes(mimeType);
  };

  // Extract Contacts from Message
  const extractContacts = (message: GmailMessage): GmailContact[] => {
    const contacts: Map<string, GmailContact> = new Map();
    
    // Extract from headers
    const headers = extractHeaders(message);
    
    // From address
    if (headers.from) {
      const fromEmail = extractEmail(headers.from);
      if (fromEmail) {
        contacts.set(fromEmail.email, {
          email: fromEmail.email,
          name: fromEmail.name,
          frequency: 1,
          lastContact: new Date(parseInt(message.internalDate)).toISOString()
        });
      }
    }
    
    // To addresses
    headers.to.forEach((recipient: string) => {
      const toEmail = extractEmail(recipient);
      if (toEmail) {
        const existing = contacts.get(toEmail.email);
        if (existing) {
          existing.frequency++;
        } else {
          contacts.set(toEmail.email, {
            email: toEmail.email,
            name: toEmail.name,
            frequency: 1,
            lastContact: new Date(parseInt(message.internalDate)).toISOString()
          });
        }
      }
    });
    
    // CC addresses
    headers.cc.forEach((recipient: string) => {
      const ccEmail = extractEmail(recipient);
      if (ccEmail) {
        const existing = contacts.get(ccEmail.email);
        if (existing) {
          existing.frequency++;
        } else {
          contacts.set(ccEmail.email, {
            email: ccEmail.email,
            name: ccEmail.name,
            frequency: 1,
            lastContact: new Date(parseInt(message.internalDate)).toISOString()
          });
        }
      }
    });
    
    return Array.from(contacts.values());
  };

  // Extract email address from string
  const extractEmail = (emailString: string): { email: string; name?: string } | null => {
    const match = emailString.match(/^(.+?)\s*<(.+?)>$/) || emailString.match(/^(.+?)$/);
    if (!match) return null;
    
    if (match[2]) {
      return {
        name: match[1].trim().replace(/['"]/g, ''),
        email: match[2].trim()
      };
    } else {
      return {
        email: match[1].trim()
      };
    }
  };

  // Register Gmail as Data Source
  const registerDataSource = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Test authentication
      const profile = await gmailApi.getProfile();
      
      // Create Gmail data source configuration
      const gmailDataSource: AtomGmailDataSource = {
        id: dataSourceConfig.sourceId,
        name: dataSourceConfig.sourceName,
        type: dataSourceConfig.sourceType,
        platform: 'gmail',
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
        await atomIngestionPipeline.registerDataSource(gmailDataSource);
      }
      
      // Register with data source registry
      if (dataSourceRegistry && dataSourceRegistry.register) {
        await dataSourceRegistry.register(gmailDataSource);
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        connected: true,
        dataSource: gmailDataSource,
        initialized: true
      }));
      
      if (onDataSourceReady) {
        onDataSourceReady(gmailDataSource);
      }
      
    } catch (error) {
      const errorMessage = `Failed to register Gmail data source: ${(error as Error).message}`;
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
      
      if (onDataSourceError) {
        onDataSourceError(errorMessage, 'registration');
      }
    }
  }, [gmailApi, accessToken, refreshToken, dataSourceConfig, atomIngestionPipeline, dataSourceRegistry, onDataSourceReady, onDataSourceError]);

  // Discover Labels
  const discoverLabels = useCallback(async (): Promise<GmailLabel[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const response = await gmailApi.getLabels();
      const labels = response.labels || [];
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredLabels: labels,
        stats: {
          ...prev.stats,
          totalLabels: labels.length
        }
      }));
      
      return labels;
      
    } catch (error) {
      const errorMessage = `Label discovery failed: ${(error as Error).message}`;
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
  }, [gmailApi, onDataSourceError]);

  // Discover Messages
  const discoverMessages = useCallback(async (labelIds?: string[], dateRange?: { start: Date; end: Date }): Promise<GmailMessageEnhanced[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const labels = labelIds || dataSourceConfig.includedLabels;
      const range = dateRange || dataSourceConfig.dateRange;
      const allMessages: GmailMessageEnhanced[] = [];
      
      // Get messages in batches
      let pageToken: string | undefined;
      let totalFetched = 0;
      
      do {
        const response = await gmailApi.getMessages(labels, pageToken, 100);
        
        if (response.messages) {
          // Fetch full message details
          const fullMessages = await Promise.all(
            response.messages.map(async (msg: any) => {
              const message = await gmailApi.getMessage(msg.id, 'full');
              
              // Extract message components
              const headers = extractHeaders(message);
              const body = extractBody(message.payload);
              const attachments = await extractAttachments(message);
              const contacts = extractContacts(message);
              
              return {
                ...message,
                source: 'gmail' as const,
                discoveredAt: new Date().toISOString(),
                processedAt: undefined,
                headersExtracted: true,
                bodyExtracted: true,
                attachmentsProcessed: false,
                embeddingGenerated: false,
                ingested: false,
                ingestionTime: undefined,
                documentId: undefined,
                vectorCount: undefined,
                headerInfo: headers,
                attachmentInfo: attachments,
                contactInfo: contacts
              };
            })
          );
          
          allMessages.push(...fullMessages);
          totalFetched += fullMessages.length;
        }
        
        pageToken = response.nextPageToken;
        
        // Limit to max results
        if (totalFetched >= dataSourceConfig.maxResults) {
          break;
        }
        
      } while (pageToken);
      
      // Sort by date
      allMessages.sort((a, b) => parseInt(b.internalDate) - parseInt(a.internalDate));
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredMessages: allMessages,
        stats: {
          ...prev.stats,
          totalMessages: allMessages.length,
          totalAttachments: allMessages.reduce((sum, msg) => sum + (msg.attachmentInfo?.totalAttachments || 0), 0)
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
  }, [gmailApi, dataSourceConfig, onDataSourceError]);

  // Discover Threads
  const discoverThreads = useCallback(async (): Promise<GmailThread[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // For simplicity, we'll extract threads from discovered messages
      const threadIds = new Set(state.discoveredMessages.map(msg => msg.threadId));
      const threads: GmailThread[] = [];
      
      for (const threadId of threadIds) {
        try {
          const thread = await gmailApi.getThread(threadId);
          threads.push(thread);
        } catch (error) {
          console.error(`Failed to get thread ${threadId}:`, error);
        }
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredThreads: threads,
        stats: {
          ...prev.stats,
          totalThreads: threads.length
        }
      }));
      
      return threads;
      
    } catch (error) {
      const errorMessage = `Thread discovery failed: ${(error as Error).message}`;
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
  }, [gmailApi, state.discoveredMessages, onDataSourceError]);

  // Discover Attachments
  const discoverAttachments = useCallback(async (): Promise<GmailAttachment[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const attachments: GmailAttachment[] = [];
      
      for (const message of state.discoveredMessages) {
        if (message.attachmentInfo && message.attachmentInfo.processedAttachments) {
          attachments.push(...message.attachmentInfo.processedAttachments);
        }
      }
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredAttachments: attachments
      }));
      
      return attachments;
      
    } catch (error) {
      const errorMessage = `Attachment discovery failed: ${(error as Error).message}`;
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
  }, [state.discoveredMessages, onDataSourceError]);

  // Discover Contacts
  const discoverContacts = useCallback(async (): Promise<GmailContact[]> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const contactsMap = new Map<string, GmailContact>();
      
      // Aggregate contacts from all messages
      for (const message of state.discoveredMessages) {
        if (message.contactInfo) {
          for (const contact of message.contactInfo) {
            const existing = contactsMap.get(contact.email);
            if (existing) {
              existing.frequency += contact.frequency;
              // Update last contact if this message is more recent
              if (new Date(parseInt(message.internalDate)) > new Date(existing.lastContact)) {
                existing.lastContact = new Date(parseInt(message.internalDate)).toISOString();
              }
            } else {
              contactsMap.set(contact.email, { ...contact });
            }
          }
        }
      }
      
      const contacts = Array.from(contactsMap.values())
        .sort((a, b) => b.frequency - a.frequency); // Sort by frequency
      
      setState(prev => ({
        ...prev,
        loading: false,
        discoveredContacts: contacts,
        stats: {
          ...prev.stats,
          totalContacts: contacts.length
        }
      }));
      
      return contacts;
      
    } catch (error) {
      const errorMessage = `Contact discovery failed: ${(error as Error).message}`;
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
  }, [state.discoveredMessages, onDataSourceError]);

  // Ingest Messages with Existing Pipeline
  const ingestMessages = useCallback(async (messages: GmailMessageEnhanced[]): Promise<void> => {
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
              // Download attachments if enabled
              let processedAttachments: any[] = [];
              
              if (dataSourceConfig.extractAttachments && message.attachmentInfo && message.attachmentInfo.processedAttachments) {
                processedAttachments = await Promise.all(
                  message.attachmentInfo.processedAttachments.slice(0, 3).map(async (attachment) => {
                    let content = '';
                    let downloadSuccessful = false;
                    
                    try {
                      const attachmentBlob = await gmailApi.downloadAttachment(attachment.messageId, attachment.attachmentId, attachment.filename);
                      content = await extractTextFromAttachment(attachmentBlob, attachment.filename, attachment.mimeType);
                      downloadSuccessful = !!content;
                    } catch (error) {
                      console.error(`Failed to download attachment ${attachment.id}:`, error);
                    }
                    
                    return {
                      id: attachment.attachmentId,
                      name: attachment.filename,
                      mimetype: attachment.mimeType,
                      size: attachment.size,
                      content: content,
                      download_successful: downloadSuccessful
                    };
                  })
                );
              }
              
              // Extract body content
              const body = extractBody(message.payload);
              const textContent = dataSourceConfig.parseHtml ? stripHtml(body.html) : body.text;
              const fullText = `${message.headerInfo.subject}\n\nFrom: ${message.headerInfo.from}\nTo: ${message.headerInfo.to.join(', ')}\n\n${textContent}`;
              
              // Add attachment content to text
              if (processedAttachments.length > 0) {
                fullText += '\n\nAttachments:\n' + processedAttachments
                  .filter(a => a.download_successful)
                  .map(a => `${a.name} (${a.mimetype})`)
                  .join(', ');
              }
              
              return {
                id: message.id,
                sourceId: dataSourceConfig.sourceId,
                sourceName: dataSourceConfig.sourceName,
                sourceType: 'gmail',
                messageType: 'email',
                messageId: message.headerInfo.messageId,
                threadId: message.threadId,
                from: message.headerInfo.from,
                to: message.headerInfo.to.join(', '),
                cc: message.headerInfo.cc.join(', '),
                subject: message.headerInfo.subject,
                message: fullText,
                timestamp: new Date(parseInt(message.internalDate)).toISOString(),
                labels: message.labelIds,
                attachments: processedAttachments,
                metadata: {
                  gmailMessage: message,
                  headerInfo: message.headerInfo,
                  attachmentInfo: message.attachmentInfo,
                  contactInfo: message.contactInfo,
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
  }, [atomIngestionPipeline, state.dataSource, dataSourceConfig, gmailApi, onIngestionStart, onIngestionProgress, onIngestionComplete, onDataSourceError]);

  // Extract Text from Attachment
  const extractTextFromAttachment = async (blob: Blob, fileName: string, mimeType: string): Promise<string> => {
    try {
      switch (mimeType) {
        case 'text/plain':
        case 'text/html':
        case 'text/csv':
        case 'application/json':
        case 'application/xml':
          return await blob.text();
          
        case 'application/pdf':
          // Would integrate with PDF.js
          return `[PDF text extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'application/msword':
        case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
          // Would integrate with docx.js
          return `[Word document text extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'application/vnd.ms-excel':
        case 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
          // Would integrate with xlsx.js
          const text = await blob.text();
          const lines = text.split('\n').slice(0, 100); // Limit to 100 lines
          return lines.join('\n');
          
        case 'application/vnd.ms-powerpoint':
        case 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
          // Would integrate with pptx.js
          return `[PowerPoint text extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'image/jpeg':
        case 'image/png':
        case 'image/gif':
          // Would integrate with OCR or image analysis
          return `[Image content extraction not implemented - Size: ${blob.size} bytes]`;
          
        case 'application/zip':
        case 'application/x-rar-compressed':
          // Would integrate with archive extraction
          return `[Archive content extraction not implemented - Size: ${blob.size} bytes]`;
          
        default:
          console.warn(`Text extraction not supported for MIME type: ${mimeType}`);
          return '';
      }
    } catch (error) {
      console.error(`Error extracting text from ${fileName}:`, error);
      return '';
    }
  };

  // Strip HTML tags
  const stripHtml = (html: string): string => {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
  };

  // Sync Messages
  const syncMessages = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      // Get history (Gmail doesn't have real-time webhooks without Pub/Sub)
      const profile = await gmailApi.getProfile();
      const history = await gmailApi.getHistory(profile.historyId);
      
      if (history.history && history.history.length > 0) {
        // Process history changes
        const messagesToIngest = history.history
          .filter(h => h.messagesAdded)
          .flatMap(h => h.messagesAdded || [])
          .map(m => m.message)
          .filter(Boolean);
        
        if (messagesToIngest.length > 0) {
          // Get full message details
          const enhancedMessages: GmailMessageEnhanced[] = await Promise.all(
            messagesToIngest.map(async (msg: any) => {
              const message = await gmailApi.getMessage(msg.id, 'full');
              
              const headers = extractHeaders(message);
              const body = extractBody(message.payload);
              const attachments = await extractAttachments(message);
              const contacts = extractContacts(message);
              
              return {
                ...message,
                source: 'gmail' as const,
                discoveredAt: new Date().toISOString(),
                processedAt: undefined,
                headersExtracted: true,
                bodyExtracted: true,
                attachmentsProcessed: false,
                embeddingGenerated: false,
                ingested: false,
                ingestionTime: undefined,
                documentId: undefined,
                vectorCount: undefined,
                headerInfo: headers,
                attachmentInfo: attachments,
                contactInfo: contacts
              };
            })
          );
          
          await ingestMessages(enhancedMessages);
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
  }, [gmailApi, ingestMessages, onDataSourceError]);

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
      // Discover labels, messages, threads, contacts
      await discoverLabels();
      const messages = await discoverMessages();
      await discoverThreads();
      await discoverContacts();
      await discoverAttachments();
      
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
  }, [dataSourceConfig, state.connected, discoverLabels, discoverMessages, discoverThreads, discoverContacts, discoverAttachments, ingestMessages, syncMessages]);

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
          discoverLabels,
          discoverMessages,
          discoverThreads,
          discoverAttachments,
          discoverContacts,
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
      <div className={`atom-gmail-data-source ${themeClasses[resolvedTheme]} rounded-lg border p-6`}>
        <h2 className="text-xl font-bold mb-4">
          📧 ATOM Gmail Data Source
          <span className="text-xs ml-2 text-gray-500">
            ({currentPlatform})
          </span>
        </h2>

        {/* Status Overview */}
        <div className="grid grid-cols-6 gap-4 mb-6">
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-blue-600">
              {state.stats.totalMessages}
            </div>
            <div className="text-sm text-gray-500">Messages</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-green-600">
              {state.stats.totalThreads}
            </div>
            <div className="text-sm text-gray-500">Threads</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-purple-600">
              {state.stats.totalLabels}
            </div>
            <div className="text-sm text-gray-500">Labels</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-orange-600">
              {state.stats.totalAttachments}
            </div>
            <div className="text-sm text-gray-500">Attachments</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-indigo-600">
              {state.stats.totalContacts}
            </div>
            <div className="text-sm text-gray-500">Contacts</div>
          </div>
          <div className="text-center p-4 border rounded">
            <div className="text-2xl font-bold text-teal-600">
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
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => discoverLabels()}
              disabled={!state.connected || state.loading}
              className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
            >
              Discover Labels
            </button>
            <button
              onClick={() => discoverMessages()}
              disabled={!state.connected || state.loading}
              className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-green-300"
            >
              Discover Messages
            </button>
            <button
              onClick={() => discoverThreads()}
              disabled={!state.connected || state.loading}
              className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-purple-300"
            >
              Discover Threads
            </button>
            <button
              onClick={() => discoverContacts()}
              disabled={!state.connected || state.loading}
              className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-orange-300"
            >
              Discover Contacts
            </button>
            <button
              onClick={() => ingestMessages(state.discoveredMessages)}
              disabled={!state.connected || state.processingIngestion || state.discoveredMessages.length === 0}
              className="bg-indigo-500 text-white px-4 py-2 rounded hover:bg-indigo-600 disabled:bg-indigo-300"
            >
              Ingest Messages
            </button>
            <button
              onClick={syncMessages}
              disabled={!state.connected || state.loading}
              className="bg-teal-500 text-white px-4 py-2 rounded hover:bg-teal-600 disabled:bg-teal-300"
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
            <div>Included Labels: {dataSourceConfig.includedLabels.join(', ')}</div>
            <div>Excluded Labels: {dataSourceConfig.excludedLabels.join(', ')}</div>
            <div>Extract Headers: {dataSourceConfig.extractHeaders ? 'Yes' : 'No'}</div>
            <div>Extract Body: {dataSourceConfig.extractBody ? 'Yes' : 'No'}</div>
            <div>Extract Attachments: {dataSourceConfig.extractAttachments ? 'Yes' : 'No'}</div>
            <div>Parse HTML: {dataSourceConfig.parseHtml ? 'Yes' : 'No'}</div>
            <div>Extract Contacts: {dataSourceConfig.extractContacts ? 'Yes' : 'No'}</div>
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

export default ATOMGmailDataSource;