/**
 * Gmail Skills Complete
 * Complete Gmail email workflow automation with API integration
 */

import { atomApiClient } from '@atom/apiclient';
import { logger } from '@atom/logger';
import { format } from 'date-fns';

// Gmail Data Models
export interface GmailMessage {
  id: string;
  thread_id: string;
  subject: string;
  from_email: string;
  to_emails: string[];
  cc_emails: string[];
  bcc_emails: string[];
  date: string;
  body: string;
  body_html: string;
  snippet: string;
  labels: string[];
  is_read: boolean;
  is_starred: boolean;
  is_draft: boolean;
  is_sent: boolean;
  is_inbox: boolean;
  is_important: boolean;
  attachment_count: number;
  size: number;
  history_id: string;
  metadata: any;
}

export interface GmailThread {
  id: string;
  thread_id: string;
  subject: string;
  message_count: number;
  participant_emails: string[];
  first_message_date: string;
  last_message_date: string;
  is_unread: boolean;
  labels: string[];
  total_size: number;
  total_attachments: number;
  last_message_snippet: string;
  metadata: any;
}

export interface GmailLabel {
  id: string;
  name: string;
  type: string;
  message_list_visibility: string;
  label_list_visibility: string;
  color: any;
  total_messages: number;
  unread_messages: number;
  metadata: any;
}

export interface GmailAttachment {
  id: string;
  message_id: string;
  thread_id: string;
  filename: string;
  mime_type: string;
  size: number;
  attachment_id: string;
  content_hash: string;
  is_indexed: boolean;
  indexed_at: string;
  metadata: any;
}

export interface GmailContact {
  id: string;
  email: string;
  name: string;
  avatar_url: string;
  interaction_count: number;
  first_interaction: string;
  last_interaction: string;
  sent_count: number;
  received_count: number;
  common_subjects: string[];
  common_labels: string[];
  metadata: any;
}

export interface GmailMemorySettings {
  user_id: string;
  ingestion_enabled: boolean;
  sync_frequency: string;
  data_retention_days: number;
  include_labels: string[];
  exclude_labels: string[];
  include_threads: boolean;
  include_drafts: boolean;
  include_sent: boolean;
  include_received: boolean;
  max_messages_per_sync: number;
  max_attachment_size_mb: number;
  include_attachments: boolean;
  index_attachments: boolean;
  search_enabled: boolean;
  semantic_search_enabled: boolean;
  metadata_extraction_enabled: boolean;
  thread_tracking_enabled: boolean;
  contact_analysis_enabled: boolean;
  last_sync_timestamp?: string;
  next_sync_timestamp?: string;
  sync_in_progress: boolean;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
}

export interface GmailIngestionStats {
  user_id: string;
  total_messages_ingested: number;
  total_threads_ingested: number;
  total_attachments_ingested: number;
  total_contacts_processed: number;
  last_ingestion_timestamp?: string;
  total_size_mb: number;
  failed_ingestions: number;
  last_error_message?: string;
  avg_messages_per_sync: number;
  avg_processing_time_ms: number;
  created_at?: string;
  updated_at?: string;
}

// Gmail Utilities
export const gmailUtils = {
  /**
   * Format date time
   */
  formatDateTime: (dateString: string): string => {
    try {
      const date = new Date(dateString);
      return format(date, 'MMM d, yyyy h:mm a');
    } catch (error) {
      return dateString;
    }
  },

  /**
   * Format relative time
   */
  formatRelativeTime: (dateString: string): string => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      
      if (diffMins < 1) return 'just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      
      const diffDays = Math.floor(diffHours / 24);
      if (diffDays < 7) return `${diffDays}d ago`;
      
      return format(date, 'MMM d');
    } catch (error) {
      return dateString;
    }
  },

  /**
   * Format file size
   */
  formatFileSize: (bytes: number): string => {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  /**
   * Get label color
   */
  getLabelColor: (labelName: string): string => {
    const colorMap: Record<string, string> = {
      'INBOX': 'blue',
      'SENT': 'green',
      'DRAFT': 'gray',
      'SPAM': 'red',
      'TRASH': 'red',
      'STARRED': 'yellow',
      'IMPORTANT': 'orange',
      'UNREAD': 'blue',
      'PERSONAL': 'blue',
      'SOCIAL': 'purple',
      'PROMOTIONS': 'pink',
      'UPDATES': 'cyan',
      'FORUMS': 'green'
    };
    
    return colorMap[labelName] || 'gray';
  },

  /**
   * Get Gmail message URL
   */
  getMessageUrl: (messageId: string): string => {
    return `https://mail.google.com/mail/u/#inbox/${messageId}`;
  },

  /**
   * Get Gmail thread URL
   */
  getThreadUrl: (threadId: string): string => {
    return `https://mail.google.com/mail/u/#inbox/${threadId}`;
  },

  /**
   * Parse email addresses
   */
  parseEmailAddresses: (addresses: string[]): string[] => {
    return addresses.map(addr => {
      if (addr.includes('<')) {
        return addr.split('<')[1].split('>')[0];
      }
      return addr;
    });
  },

  /**
   * Create Gmail message from dict
   */
  createGmailMessage: (data: any): GmailMessage => {
    return {
      id: data.id || '',
      thread_id: data.thread_id || '',
      subject: data.subject || '',
      from_email: data.from_email || '',
      to_emails: data.to_emails || [],
      cc_emails: data.cc_emails || [],
      bcc_emails: data.bcc_emails || [],
      date: data.date || '',
      body: data.body || data.body_text || '',
      body_html: data.body_html || '',
      snippet: data.snippet || '',
      labels: data.labels || [],
      is_read: data.is_read || false,
      is_starred: data.is_starred || false,
      is_draft: data.is_draft || false,
      is_sent: data.is_sent || false,
      is_inbox: data.is_inbox || false,
      is_important: data.is_important || false,
      attachment_count: data.attachment_count || 0,
      size: data.size || 0,
      history_id: data.history_id || '',
      metadata: data.metadata || {}
    };
  },

  /**
   * Create Gmail thread from dict
   */
  createGmailThread: (data: any): GmailThread => {
    return {
      id: data.id || '',
      thread_id: data.thread_id || '',
      subject: data.subject || '',
      message_count: data.message_count || 0,
      participant_emails: data.participant_emails || [],
      first_message_date: data.first_message_date || '',
      last_message_date: data.last_message_date || '',
      is_unread: data.is_unread || false,
      labels: data.labels || [],
      total_size: data.total_size || 0,
      total_attachments: data.total_attachments || 0,
      last_message_snippet: data.last_message_snippet || '',
      metadata: data.metadata || {}
    };
  },

  /**
   * Create Gmail label from dict
   */
  createGmailLabel: (data: any): GmailLabel => {
    return {
      id: data.id || '',
      name: data.name || '',
      type: data.type || '',
      message_list_visibility: data.message_list_visibility || '',
      label_list_visibility: data.label_list_visibility || '',
      color: data.color || null,
      total_messages: data.total_messages || 0,
      unread_messages: data.unread_messages || 0,
      metadata: data.metadata || {}
    };
  },

  /**
   * Create Gmail contact from dict
   */
  createGmailContact: (data: any): GmailContact => {
    return {
      id: data.id || '',
      email: data.email || '',
      name: data.name || '',
      avatar_url: data.avatar_url || '',
      interaction_count: data.interaction_count || 0,
      first_interaction: data.first_interaction || '',
      last_interaction: data.last_interaction || '',
      sent_count: data.sent_count || 0,
      received_count: data.received_count || 0,
      common_subjects: data.common_subjects || [],
      common_labels: data.common_labels || [],
      metadata: data.metadata || {}
    };
  },

  /**
   * Create Gmail attachment from dict
   */
  createGmailAttachment: (data: any): GmailAttachment => {
    return {
      id: data.id || '',
      message_id: data.message_id || '',
      thread_id: data.thread_id || '',
      filename: data.filename || '',
      mime_type: data.mime_type || '',
      size: data.size || 0,
      attachment_id: data.attachment_id || '',
      content_hash: data.content_hash || '',
      is_indexed: data.is_indexed || false,
      indexed_at: data.indexed_at || '',
      metadata: data.metadata || {}
    };
  },

  /**
   * Validate Gmail query
   */
  validateGmailQuery: (query: string): boolean => {
    // Basic validation
    if (!query || query.trim() === '') {
      return false;
    }
    
    // Check for potentially dangerous queries
    const dangerousPatterns = [
      /\*{10,}/,  // Too many wildcards
      /or.*or.*or/i,  // Too many ORs
    ];
    
    return !dangerousPatterns.some(pattern => pattern.test(query));
  },

  /**
   * Validate email address
   */
  validateEmailAddress: (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  },

  /**
   * Sanitize HTML content
   */
  sanitizeHtml: (html: string): string => {
    // Basic HTML sanitization - in production, use a proper sanitizer
    return html
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
      .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
      .replace(/<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>/gi, '')
      .replace(/javascript:/gi, '')
      .replace(/on\w+\s*=/gi, '');
  },

  /**
   * Generate email preview text
   */
  generateEmailPreview: (content: string, maxLength: number = 150): string => {
    // Remove HTML tags
    const plainText = content.replace(/<[^>]*>/g, '');
    
    // Remove extra whitespace
    const cleanedText = plainText.replace(/\s+/g, ' ').trim();
    
    // Truncate and add ellipsis if needed
    if (cleanedText.length <= maxLength) {
      return cleanedText;
    }
    
    return cleanedText.substring(0, maxLength - 3) + '...';
  },

  /**
   * Get MIME type icon
   */
  getMimeTypeIcon: (mimeType: string): string => {
    const iconMap: Record<string, string> = {
      'image/jpeg': 'image',
      'image/png': 'image',
      'image/gif': 'image',
      'application/pdf': 'pdf',
      'application/msword': 'document',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'document',
      'application/vnd.ms-excel': 'spreadsheet',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'spreadsheet',
      'application/vnd.ms-powerpoint': 'presentation',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'presentation',
      'application/zip': 'archive',
      'text/plain': 'text',
      'text/html': 'html'
    };
    
    return iconMap[mimeType] || 'file';
  },

  /**
   * Check if message is from recent time
   */
  isRecentMessage: (dateString: string, daysAgo: number = 7): boolean => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
      return diffDays <= daysAgo;
    } catch (error) {
      return false;
    }
  },

  /**
   * Get message priority
   */
  getMessagePriority: (message: GmailMessage): 'high' | 'normal' | 'low' => {
    // Check for important label
    if (message.is_important || message.labels.includes('IMPORTANT')) {
      return 'high';
    }
    
    // Check for recent unread messages
    if (!message.is_read && gmailUtils.isRecentMessage(message.date, 1)) {
      return 'high';
    }
    
    // Check for starred messages
    if (message.is_starred) {
      return 'high';
    }
    
    // Check for old messages
    if (gmailUtils.isRecentMessage(message.date, 30)) {
      return 'normal';
    }
    
    return 'low';
  },

  /**
   * Format thread preview
   */
  formatThreadPreview: (thread: GmailThread): string => {
    if (thread.message_count === 1) {
      return thread.last_message_snippet || '';
    }
    
    return `${thread.message_count} messages • Last: ${thread.last_message_snippet || 'No preview'}`;
  },

  /**
   * Get contact avatar URL
   */
  getContactAvatarUrl: (email: string, name: string, size: number = 40): string => {
    // Use Gravatar or similar service
    const baseUrl = 'https://www.gravatar.com/avatar';
    const hash = require('crypto').createHash('md5').update(email.toLowerCase()).digest('hex');
    return `${baseUrl}/${hash}?s=${size}&d=identicon&r=pg`;
  },

  /**
   * Create Gmail draft URL
   */
  createDraftUrl: (to: string, subject: string, body: string): string => {
    const params = new URLSearchParams();
    if (to) params.append('to', to);
    if (subject) params.append('su', subject);
    if (body) params.append('body', body);
    
    return `https://mail.google.com/mail/u/#compose?${params.toString()}`;
  }
};

// Gmail Skills Implementation
export const gmailSkills = {
  /**
   * Get Gmail messages
   */
  gmailGetMessages: async (
    userId: string,
    accessToken: string,
    maxResults: number = 50,
    query: string = '',
    labelIds: string[] = ['INBOX'],
    includeSpamTrash: boolean = false,
    pageToken?: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Gmail messages for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/messages/list', {
        user_id: userId,
        access_token: accessToken,
        max_results: maxResults,
        query: query,
        label_ids: labelIds,
        include_spam_trash: includeSpamTrash,
        page_token: pageToken
      });
      
      const data = response.data;
      
      if (data.ok) {
        const messages = data.messages.map((msg: any) => gmailUtils.createGmailMessage(msg));
        logger.info(`Gmail messages retrieved: ${messages.length} results`);
        return {
          messages: messages,
          next_page_token: data.next_page_token,
          result_size_estimate: data.result_size_estimate,
          total_results: data.total_results
        };
      } else {
        throw new Error(data.error || 'Failed to get Gmail messages');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetMessages:', error);
      throw new Error(`Failed to get Gmail messages: ${error.message}`);
    }
  },

  /**
   * Get Gmail message
   */
  gmailGetMessage: async (
    userId: string,
    accessToken: string,
    messageId: string,
    format: string = 'full',
    includeAttachments: boolean = true
  ): Promise<GmailMessage> => {
    try {
      logger.info(`Getting Gmail message for user ${userId}: ${messageId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/messages/get', {
        user_id: userId,
        access_token: accessToken,
        message_id: messageId,
        format: format,
        include_attachments: includeAttachments
      });
      
      const data = response.data;
      
      if (data.ok) {
        const message = gmailUtils.createGmailMessage(data.message);
        logger.info(`Gmail message retrieved: ${message.subject}`);
        return message;
      } else {
        throw new Error(data.error || 'Failed to get Gmail message');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetMessage:', error);
      throw new Error(`Failed to get Gmail message: ${error.message}`);
    }
  },

  /**
   * Send Gmail message
   */
  gmailSendMessage: async (
    userId: string,
    accessToken: string,
    to: string,
    subject: string,
    body: string,
    cc?: string,
    bcc?: string,
    fromEmail?: string,
    replyToMessageId?: string,
    attachments?: any[],
    isHtml: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Sending Gmail message for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/messages/send', {
        user_id: userId,
        access_token: accessToken,
        to: to,
        subject: subject,
        body: body,
        cc: cc,
        bcc: bcc,
        from_email: fromEmail,
        reply_to_message_id: replyToMessageId,
        attachments: attachments,
        is_html: isHtml
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail message sent: ${data.message.id}`);
        return {
          message_id: data.message.id,
          thread_id: data.message.thread_id,
          label_ids: data.message.label_ids
        };
      } else {
        throw new Error(data.error || 'Failed to send Gmail message');
      }
    } catch (error: any) {
      logger.error('Error in gmailSendMessage:', error);
      throw new Error(`Failed to send Gmail message: ${error.message}`);
    }
  },

  /**
   * Search Gmail messages
   */
  gmailSearchMessages: async (
    userId: string,
    accessToken: string,
    query: string,
    maxResults: number = 50,
    pageToken?: string
  ): Promise<any> => {
    try {
      if (!gmailUtils.validateGmailQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      logger.info(`Searching Gmail messages for user ${userId}: ${query}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/messages/search', {
        user_id: userId,
        access_token: accessToken,
        query: query,
        max_results: maxResults,
        page_token: pageToken
      });
      
      const data = response.data;
      
      if (data.ok) {
        const messages = data.messages.map((msg: any) => gmailUtils.createGmailMessage(msg));
        logger.info(`Gmail messages search completed: ${messages.length} results`);
        return {
          messages: messages,
          next_page_token: data.next_page_token,
          result_size_estimate: data.result_size_estimate,
          total_results: data.total_results,
          query: query
        };
      } else {
        throw new Error(data.error || 'Failed to search Gmail messages');
      }
    } catch (error: any) {
      logger.error('Error in gmailSearchMessages:', error);
      throw new Error(`Failed to search Gmail messages: ${error.message}`);
    }
  },

  /**
   * Get Gmail threads
   */
  gmailGetThreads: async (
    userId: string,
    accessToken: string,
    maxResults: number = 50,
    query: string = '',
    labelIds: string[] = ['INBOX'],
    includeSpamTrash: boolean = false,
    pageToken?: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Gmail threads for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/threads/list', {
        user_id: userId,
        access_token: accessToken,
        max_results: maxResults,
        query: query,
        label_ids: labelIds,
        include_spam_trash: includeSpamTrash,
        page_token: pageToken
      });
      
      const data = response.data;
      
      if (data.ok) {
        const threads = data.threads.map((thread: any) => gmailUtils.createGmailThread(thread));
        logger.info(`Gmail threads retrieved: ${threads.length} results`);
        return {
          threads: threads,
          next_page_token: data.next_page_token,
          result_size_estimate: data.result_size_estimate,
          total_results: data.total_results
        };
      } else {
        throw new Error(data.error || 'Failed to get Gmail threads');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetThreads:', error);
      throw new Error(`Failed to get Gmail threads: ${error.message}`);
    }
  },

  /**
   * Get Gmail thread
   */
  gmailGetThread: async (
    userId: string,
    accessToken: string,
    threadId: string
  ): Promise<GmailThread> => {
    try {
      logger.info(`Getting Gmail thread for user ${userId}: ${threadId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/threads/get', {
        user_id: userId,
        access_token: accessToken,
        thread_id: threadId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const thread = gmailUtils.createGmailThread(data.thread);
        logger.info(`Gmail thread retrieved: ${thread.subject}`);
        return thread;
      } else {
        throw new Error(data.error || 'Failed to get Gmail thread');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetThread:', error);
      throw new Error(`Failed to get Gmail thread: ${error.message}`);
    }
  },

  /**
   * Get Gmail labels
   */
  gmailGetLabels: async (
    userId: string,
    accessToken: string
  ): Promise<GmailLabel[]> => {
    try {
      logger.info(`Getting Gmail labels for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/labels/list', {
        user_id: userId,
        access_token: accessToken
      });
      
      const data = response.data;
      
      if (data.ok) {
        const labels = data.labels.map((label: any) => gmailUtils.createGmailLabel(label));
        logger.info(`Gmail labels retrieved: ${labels.length} labels`);
        return labels;
      } else {
        throw new Error(data.error || 'Failed to get Gmail labels');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetLabels:', error);
      throw new Error(`Failed to get Gmail labels: ${error.message}`);
    }
  },

  /**
   * Create Gmail label
   */
  gmailCreateLabel: async (
    userId: string,
    accessToken: string,
    name: string,
    labelListVisibility: string = 'labelShow',
    messageListVisibility: string = 'show',
    color?: any
  ): Promise<GmailLabel> => {
    try {
      logger.info(`Creating Gmail label for user ${userId}: ${name}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/labels/create', {
        user_id: userId,
        access_token: accessToken,
        name: name,
        label_list_visibility: labelListVisibility,
        message_list_visibility: messageListVisibility,
        color: color
      });
      
      const data = response.data;
      
      if (data.ok) {
        const label = gmailUtils.createGmailLabel(data.label);
        logger.info(`Gmail label created: ${label.name}`);
        return label;
      } else {
        throw new Error(data.error || 'Failed to create Gmail label');
      }
    } catch (error: any) {
      logger.error('Error in gmailCreateLabel:', error);
      throw new Error(`Failed to create Gmail label: ${error.message}`);
    }
  },

  /**
   * Modify Gmail message labels
   */
  gmailModifyMessageLabels: async (
    userId: string,
    accessToken: string,
    messageId: string,
    addLabels?: string[],
    removeLabels?: string[]
  ): Promise<boolean> => {
    try {
      logger.info(`Modifying Gmail message labels for user ${userId}: ${messageId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/messages/modify-labels', {
        user_id: userId,
        access_token: accessToken,
        message_id: messageId,
        add_labels: addLabels,
        remove_labels: removeLabels
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail message labels modified: ${messageId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to modify Gmail message labels');
      }
    } catch (error: any) {
      logger.error('Error in gmailModifyMessageLabels:', error);
      throw new Error(`Failed to modify Gmail message labels: ${error.message}`);
    }
  },

  /**
   * Trash Gmail message
   */
  gmailTrashMessage: async (
    userId: string,
    accessToken: string,
    messageId: string
  ): Promise<boolean> => {
    try {
      logger.info(`Trashing Gmail message for user ${userId}: ${messageId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/messages/trash', {
        user_id: userId,
        access_token: accessToken,
        message_id: messageId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail message trashed: ${messageId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to trash Gmail message');
      }
    } catch (error: any) {
      logger.error('Error in gmailTrashMessage:', error);
      throw new Error(`Failed to trash Gmail message: ${error.message}`);
    }
  },

  /**
   * Delete Gmail message permanently
   */
  gmailDeleteMessage: async (
    userId: string,
    accessToken: string,
    messageId: string
  ): Promise<boolean> => {
    try {
      logger.info(`Deleting Gmail message for user ${userId}: ${messageId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/messages/delete', {
        user_id: userId,
        access_token: accessToken,
        message_id: messageId,
        confirm: true
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail message deleted: ${messageId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete Gmail message');
      }
    } catch (error: any) {
      logger.error('Error in gmailDeleteMessage:', error);
      throw new Error(`Failed to delete Gmail message: ${error.message}`);
    }
  },

  /**
   * Get Gmail attachment
   */
  gmailGetAttachment: async (
    userId: string,
    accessToken: string,
    messageId: string,
    attachmentId: string,
    download: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Getting Gmail attachment for user ${userId}: ${attachmentId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/attachments/get', {
        user_id: userId,
        access_token: accessToken,
        message_id: messageId,
        attachment_id: attachmentId,
        download: download
      });
      
      const data = response.data;
      
      if (data.ok) {
        const attachment = gmailUtils.createGmailAttachment(data.attachment);
        logger.info(`Gmail attachment retrieved: ${attachment.filename}`);
        return attachment;
      } else {
        throw new Error(data.error || 'Failed to get Gmail attachment');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetAttachment:', error);
      throw new Error(`Failed to get Gmail attachment: ${error.message}`);
    }
  },

  /**
   * List Gmail drafts
   */
  gmailGetDrafts: async (
    userId: string,
    accessToken: string
  ): Promise<any> => {
    try {
      logger.info(`Getting Gmail drafts for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/drafts/list', {
        user_id: userId,
        access_token: accessToken
      });
      
      const data = response.data;
      
      if (data.ok) {
        const drafts = data.drafts.map((draft: any) => ({
          id: draft.id,
          message: gmailUtils.createGmailMessage(draft.message),
          created_at: draft.created_at,
          updated_at: draft.updated_at
        }));
        logger.info(`Gmail drafts retrieved: ${drafts.length} drafts`);
        return {
          drafts: drafts,
          total_drafts: data.total_drafts
        };
      } else {
        throw new Error(data.error || 'Failed to get Gmail drafts');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetDrafts:', error);
      throw new Error(`Failed to get Gmail drafts: ${error.message}`);
    }
  },

  /**
   * Create Gmail draft
   */
  gmailCreateDraft: async (
    userId: string,
    accessToken: string,
    to: string,
    subject: string,
    body: string,
    cc?: string,
    bcc?: string,
    fromEmail?: string,
    attachments?: any[],
    isHtml: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Creating Gmail draft for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/drafts/create', {
        user_id: userId,
        access_token: accessToken,
        to: to,
        subject: subject,
        body: body,
        cc: cc,
        bcc: bcc,
        from_email: fromEmail,
        attachments: attachments,
        is_html: isHtml
      });
      
      const data = response.data;
      
      if (data.ok) {
        const draft = {
          id: data.draft.id,
          message: gmailUtils.createGmailMessage(data.draft.message),
          created_at: data.draft.created_at,
          updated_at: data.draft.updated_at
        };
        logger.info(`Gmail draft created: ${draft.id}`);
        return draft;
      } else {
        throw new Error(data.error || 'Failed to create Gmail draft');
      }
    } catch (error: any) {
      logger.error('Error in gmailCreateDraft:', error);
      throw new Error(`Failed to create Gmail draft: ${error.message}`);
    }
  },

  /**
   * Get Gmail memory settings
   */
  gmailGetMemorySettings: async (userId: string): Promise<GmailMemorySettings> => {
    try {
      logger.info(`Getting Gmail memory settings for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/settings', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail memory settings retrieved for user ${userId}`);
        return data.settings;
      } else {
        throw new Error(data.error || 'Failed to get Gmail memory settings');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetMemorySettings:', error);
      throw new Error(`Failed to get Gmail memory settings: ${error.message}`);
    }
  },

  /**
   * Update Gmail memory settings
   */
  gmailUpdateMemorySettings: async (
    userId: string,
    settings: Partial<GmailMemorySettings>
  ): Promise<boolean> => {
    try {
      logger.info(`Updating Gmail memory settings for user ${userId}`);
      
      const response = await atomApiClient.put('/api/gmail/email-workflow/memory/settings', {
        user_id: userId,
        ...settings
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail memory settings updated for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to update Gmail memory settings');
      }
    } catch (error: any) {
      logger.error('Error in gmailUpdateMemorySettings:', error);
      throw new Error(`Failed to update Gmail memory settings: ${error.message}`);
    }
  },

  /**
   * Start Gmail memory ingestion
   */
  gmailStartIngestion: async (
    userId: string,
    accessToken: string,
    query: string = '',
    maxMessages?: number,
    forceSync: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Starting Gmail ingestion for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/ingest', {
        user_id: userId,
        access_token: accessToken,
        query: query,
        max_messages: maxMessages,
        force_sync: forceSync
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail ingestion started: ${data.ingestion_result.messages_ingested} messages`);
        return data.ingestion_result;
      } else {
        throw new Error(data.error || 'Failed to start Gmail ingestion');
      }
    } catch (error: any) {
      logger.error('Error in gmailStartIngestion:', error);
      throw new Error(`Failed to start Gmail ingestion: ${error.message}`);
    }
  },

  /**
   * Get Gmail sync status
   */
  gmailGetSyncStatus: async (userId: string): Promise<any> => {
    try {
      logger.info(`Getting Gmail sync status for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/status', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail sync status retrieved for user ${userId}`);
        return data.memory_status;
      } else {
        throw new Error(data.error || 'Failed to get Gmail sync status');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetSyncStatus:', error);
      throw new Error(`Failed to get Gmail sync status: ${error.message}`);
    }
  },

  /**
   * Search Gmail messages in memory
   */
  gmailSearchMemory: async (
    userId: string,
    query: string,
    labelFilter?: string,
    dateFrom?: string,
    dateTo?: string,
    limit: number = 50
  ): Promise<any> => {
    try {
      if (!gmailUtils.validateGmailQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      logger.info(`Searching Gmail memory for user ${userId}: ${query}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/search', {
        user_id: userId,
        query: query,
        label_filter: labelFilter,
        date_from: dateFrom,
        date_to: dateTo,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail memory search completed: ${data.count} results`);
        return {
          messages: data.messages,
          count: data.count,
          search_filters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Gmail memory');
      }
    } catch (error: any) {
      logger.error('Error in gmailSearchMemory:', error);
      throw new Error(`Failed to search Gmail memory: ${error.message}`);
    }
  },

  /**
   * Search Gmail threads in memory
   */
  gmailSearchMemoryThreads: async (
    userId: string,
    query: string,
    labelFilter?: string,
    limit: number = 50
  ): Promise<any> => {
    try {
      if (!gmailUtils.validateGmailQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      logger.info(`Searching Gmail memory threads for user ${userId}: ${query}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/threads-search', {
        user_id: userId,
        query: query,
        label_filter: labelFilter,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail memory threads search completed: ${data.count} results`);
        return {
          threads: data.threads,
          count: data.count,
          search_filters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Gmail memory threads');
      }
    } catch (error: any) {
      logger.error('Error in gmailSearchMemoryThreads:', error);
      throw new Error(`Failed to search Gmail memory threads: ${error.message}`);
    }
  },

  /**
   * Search Gmail contacts in memory
   */
  gmailSearchMemoryContacts: async (
    userId: string,
    query: string,
    limit: number = 50
  ): Promise<any> => {
    try {
      logger.info(`Searching Gmail memory contacts for user ${userId}: ${query}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/contacts-search', {
        user_id: userId,
        query: query,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail memory contacts search completed: ${data.count} results`);
        return {
          contacts: data.contacts.map((contact: any) => gmailUtils.createGmailContact(contact)),
          count: data.count,
          search_filters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Gmail memory contacts');
      }
    } catch (error: any) {
      logger.error('Error in gmailSearchMemoryContacts:', error);
      throw new Error(`Failed to search Gmail memory contacts: ${error.message}`);
    }
  },

  /**
   * Get Gmail ingestion statistics
   */
  gmailGetIngestionStats: async (userId: string): Promise<GmailIngestionStats> => {
    try {
      logger.info(`Getting Gmail ingestion stats for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/ingestion-stats', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail ingestion stats retrieved for user ${userId}`);
        return data.ingestion_stats;
      } else {
        throw new Error(data.error || 'Failed to get Gmail ingestion stats');
      }
    } catch (error: any) {
      logger.error('Error in gmailGetIngestionStats:', error);
      throw new Error(`Failed to get Gmail ingestion stats: ${error.message}`);
    }
  },

  /**
   * Delete Gmail user data
   */
  gmailDeleteUserData: async (userId: string): Promise<boolean> => {
    try {
      logger.info(`Deleting Gmail user data for user ${userId}`);
      
      const response = await atomApiClient.post('/api/gmail/email-workflow/memory/delete', {
        user_id: userId,
        confirm: true
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Gmail user data deleted for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete Gmail user data');
      }
    } catch (error: any) {
      logger.error('Error in gmailDeleteUserData:', error);
      throw new Error(`Failed to delete Gmail user data: ${error.message}`);
    }
  }
};

// Export default
export default gmailSkills;