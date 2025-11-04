// Google Batch Operations Service
import { invoke } from '@tauri-apps/api/tauri';
import type { 
  GoogleEmail, 
  GoogleCalendarEvent, 
  GoogleDriveFile,
  GmailSendAction,
  GmailMarkAction,
  GmailDeleteAction,
  GoogleCalendarUpdateAction,
  GoogleCalendarDeleteAction,
  GoogleDriveDeleteAction,
  GoogleDriveShareAction
} from '../types/googleTypes';

interface BatchRequest {
  id: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  body?: any;
  headers?: Record<string, string>;
}

interface BatchResponse {
  id: string;
  status: number;
  statusText: string;
  headers: Record<string, string>;
  body?: any;
  error?: string;
}

interface BatchResult<T> {
  success: boolean;
  results: T[];
  errors: Array<{ id: string; error: string }>;
  total: number;
  processed: number;
}

export class GoogleBatchService {
  private static instance: GoogleBatchService;
  private userId: string = '';
  private maxBatchSize: number = 100; // Google API limit

  private constructor() {}

  static getInstance(): GoogleBatchService {
    if (!GoogleBatchService.instance) {
      GoogleBatchService.instance = new GoogleBatchService();
    }
    return GoogleBatchService.instance;
  }

  // Initialize with user context
  initialize(userId: string): void {
    this.userId = userId;
  }

  // Create batch requests for Gmail operations
  async batchGmailOperations(
    operations: Array<{
      type: 'send' | 'mark' | 'delete';
      data: any;
    }>
  ): Promise<BatchResult<GoogleEmail>> {
    const requests: BatchRequest[] = operations.map((op, index) => {
      const requestId = `gmail_${index}`;
      
      switch (op.type) {
        case 'send':
          return this.createGmailSendRequest(requestId, op.data);
        case 'mark':
          return this.createGmailMarkRequest(requestId, op.data);
        case 'delete':
          return this.createGmailDeleteRequest(requestId, op.data);
        default:
          throw new Error(`Unknown Gmail operation type: ${op.type}`);
      }
    });

    return await this.executeBatch(requests);
  }

  // Create batch requests for Calendar operations
  async batchCalendarOperations(
    operations: Array<{
      type: 'update' | 'delete';
      data: any;
    }>
  ): Promise<BatchResult<GoogleCalendarEvent>> {
    const requests: BatchRequest[] = operations.map((op, index) => {
      const requestId = `calendar_${index}`;
      
      switch (op.type) {
        case 'update':
          return this.createCalendarUpdateRequest(requestId, op.data);
        case 'delete':
          return this.createCalendarDeleteRequest(requestId, op.data);
        default:
          throw new Error(`Unknown Calendar operation type: ${op.type}`);
      }
    });

    return await this.executeBatch(requests);
  }

  // Create batch requests for Drive operations
  async batchDriveOperations(
    operations: Array<{
      type: 'delete' | 'share';
      data: any;
    }>
  ): Promise<BatchResult<GoogleDriveFile>> {
    const requests: BatchRequest[] = operations.map((op, index) => {
      const requestId = `drive_${index}`;
      
      switch (op.type) {
        case 'delete':
          return this.createDriveDeleteRequest(requestId, op.data);
        case 'share':
          return this.createDriveShareRequest(requestId, op.data);
        default:
          throw new Error(`Unknown Drive operation type: ${op.type}`);
      }
    });

    return await this.executeBatch(requests);
  }

  // Execute batch request
  private async executeBatch<T>(
    requests: BatchRequest[]
  ): Promise<BatchResult<T>> {
    try {
      // Split large batches into smaller chunks
      const chunks = this.chunkRequests(requests);
      const allResults: T[] = [];
      const allErrors: Array<{ id: string; error: string }> = [];
      let totalProcessed = 0;

      for (const chunk of chunks) {
        const chunkResult = await this.executeBatchChunk(chunk);
        
        allResults.push(...chunkResult.results as T[]);
        allErrors.push(...chunkResult.errors);
        totalProcessed += chunkResult.processed;

        // Add delay between chunks to avoid rate limiting
        if (chunks.indexOf(chunk) < chunks.length - 1) {
          await this.delay(100); // 100ms between chunks
        }
      }

      return {
        success: allErrors.length === 0,
        results: allResults,
        errors: allErrors,
        total: requests.length,
        processed: totalProcessed
      };
    } catch (error) {
      return {
        success: false,
        results: [],
        errors: [{ id: 'batch', error: error instanceof Error ? error.message : 'Unknown error' }],
        total: requests.length,
        processed: 0
      };
    }
  }

  // Execute single batch chunk
  private async executeBatchChunk<T>(
    requests: BatchRequest[]
  ): Promise<BatchResult<T>> {
    try {
      const batchResponse: BatchResponse[] = await invoke('google_execute_batch', {
        userId: this.userId,
        requests
      });

      const results: T[] = [];
      const errors: Array<{ id: string; error: string }> = [];
      let processed = 0;

      for (const response of batchResponse) {
        if (response.status >= 200 && response.status < 300) {
          results.push(response.body as T);
          processed++;
        } else {
          errors.push({
            id: response.id,
            error: response.error || `HTTP ${response.status}: ${response.statusText}`
          });
        }
      }

      return {
        success: errors.length === 0,
        results,
        errors,
        total: requests.length,
        processed
      };
    } catch (error) {
      return {
        success: false,
        results: [],
        errors: [{ id: 'chunk', error: error instanceof Error ? error.message : 'Unknown error' }],
        total: requests.length,
        processed: 0
      };
    }
  }

  // Split requests into chunks
  private chunkRequests(requests: BatchRequest[]): BatchRequest[][] {
    const chunks: BatchRequest[][] = [];
    
    for (let i = 0; i < requests.length; i += this.maxBatchSize) {
      chunks.push(requests.slice(i, i + this.maxBatchSize));
    }

    return chunks;
  }

  // Delay helper
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Gmail request creators
  private createGmailSendRequest(id: string, data: GmailSendAction): BatchRequest {
    return {
      id,
      method: 'POST',
      url: 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
      body: {
        to: data.params.to,
        cc: data.params.cc,
        bcc: data.params.bcc,
        subject: data.params.subject,
        body: data.params.body,
        html_body: data.params.htmlBody,
        attachments: data.params.attachments
      },
      headers: {
        'Content-Type': 'application/json'
      }
    };
  }

  private createGmailMarkRequest(id: string, data: GmailMarkAction): BatchRequest {
    const addLabels: string[] = [];
    const removeLabels: string[] = [];

    switch (data.params.action) {
      case 'read':
        addLabels.push('INBOX');
        removeLabels.push('UNREAD');
        break;
      case 'unread':
        addLabels.push('UNREAD');
        removeLabels.push('INBOX');
        break;
      case 'starred':
        addLabels.push('STARRED');
        break;
      case 'unstarred':
        removeLabels.push('STARRED');
        break;
      case 'important':
        addLabels.push('IMPORTANT');
        break;
      case 'unimportant':
        removeLabels.push('IMPORTANT');
        break;
    }

    return {
      id,
      method: 'POST',
      url: `https://gmail.googleapis.com/gmail/v1/users/me/messages/${data.params.messageId}/modify`,
      body: {
        addLabelIds: addLabels,
        removeLabelIds: removeLabels
      },
      headers: {
        'Content-Type': 'application/json'
      }
    };
  }

  private createGmailDeleteRequest(id: string, data: GmailDeleteAction): BatchRequest {
    const url = data.params.permanently
      ? `https://gmail.googleapis.com/gmail/v1/users/me/messages/${data.params.messageId}`
      : `https://gmail.googleapis.com/gmail/v1/users/me/messages/${data.params.messageId}/trash`;

    return {
      id,
      method: 'DELETE',
      url,
      headers: {
        'Content-Type': 'application/json'
      }
    };
  }

  // Calendar request creators
  private createCalendarUpdateRequest(id: string, data: GoogleCalendarUpdateAction): BatchRequest {
    return {
      id,
      method: 'PUT',
      url: `https://www.googleapis.com/calendar/v3/calendars/${data.params.calendarId || 'primary'}/events/${data.params.eventId}`,
      body: {
        summary: data.params.summary,
        description: data.params.description,
        location: data.params.location,
        startTime: data.params.startTime,
        endTime: data.params.endTime,
        attendees: data.params.attendees,
        visibility: data.params.visibility,
        transparency: data.params.transparency
      },
      headers: {
        'Content-Type': 'application/json'
      }
    };
  }

  private createCalendarDeleteRequest(id: string, data: GoogleCalendarDeleteAction): BatchRequest {
    const url = `https://www.googleapis.com/calendar/v3/calendars/${data.params.calendarId || 'primary'}/events/${data.params.eventId}`;
    
    const params = new URLSearchParams();
    if (data.params.sendUpdates) {
      params.append('sendUpdates', data.params.sendUpdates);
    }

    return {
      id,
      method: 'DELETE',
      url: `${url}?${params.toString()}`,
      headers: {
        'Content-Type': 'application/json'
      }
    };
  }

  // Drive request creators
  private createDriveDeleteRequest(id: string, data: GoogleDriveDeleteAction): BatchRequest {
    const url = `https://www.googleapis.com/drive/v3/files/${data.params.fileId}`;
    
    const params = new URLSearchParams();
    if (data.params.sendNotificationEmail !== undefined) {
      params.append('enforceSingleParent', 'true');
    }

    return {
      id,
      method: 'DELETE',
      url: `${url}?${params.toString()}`,
      headers: {
        'Content-Type': 'application/json'
      }
    };
  }

  private createDriveShareRequest(id: string, data: GoogleDriveShareAction): BatchRequest {
    const permission = {
      role: data.params.role,
      type: data.params.type,
      emailAddress: data.params.emailAddress,
      domain: data.params.domain,
      allowFileDiscovery: data.params.allowFileDiscovery
    };

    // Remove undefined fields
    Object.keys(permission).forEach(key => 
      (permission as any)[key] === undefined && delete (permission as any)[key]
    );

    return {
      id,
      method: 'POST',
      url: `https://www.googleapis.com/drive/v3/files/${data.params.fileId}/permissions`,
      body: permission,
      headers: {
        'Content-Type': 'application/json'
      }
    };
  }

  // Batch utility methods
  async markMultipleEmails(
    messageIds: string[],
    action: 'read' | 'unread' | 'starred' | 'unstarred' | 'important' | 'unimportant'
  ): Promise<BatchResult<GoogleEmail>> {
    const operations = messageIds.map(messageId => ({
      type: 'mark' as const,
      data: {
        action: 'mark_email',
        params: {
          messageId,
          action
        }
      }
    }));

    return await this.batchGmailOperations(operations);
  }

  async deleteMultipleEmails(
    messageIds: string[],
    permanently: boolean = false
  ): Promise<BatchResult<GoogleEmail>> {
    const operations = messageIds.map(messageId => ({
      type: 'delete' as const,
      data: {
        action: 'delete_email',
        params: {
          messageId,
          permanently
        }
      }
    }));

    return await this.batchGmailOperations(operations);
  }

  async deleteMultipleEvents(
    eventIds: string[],
    calendarId: string = 'primary',
    sendUpdates: string = 'all'
  ): Promise<BatchResult<GoogleCalendarEvent>> {
    const operations = eventIds.map(eventId => ({
      type: 'delete' as const,
      data: {
        action: 'delete_event',
        params: {
          eventId,
          calendarId,
          sendUpdates
        }
      }
    }));

    return await this.batchCalendarOperations(operations);
  }

  async shareMultipleFiles(
    fileIds: string[],
    permissions: Array<{
      role: string;
      type: string;
      emailAddress?: string;
      domain?: string;
    }>
  ): Promise<BatchResult<GoogleDriveFile>> {
    const operations: Array<{ type: 'share'; data: any }> = [];

    for (const fileId of fileIds) {
      for (const permission of permissions) {
        operations.push({
          type: 'share' as const,
          data: {
            action: 'share_file',
            params: {
              fileId,
              ...permission
            }
          }
        });
      }
    }

    return await this.batchDriveOperations(operations);
  }

  // Batch statistics
  async getBatchStatistics(): Promise<{
    totalBatches: number;
    successfulBatches: number;
    failedBatches: number;
    averageResponseTime: number;
  }> {
    try {
      const stats = await invoke('google_get_batch_statistics', {
        userId: this.userId
      });

      return stats as {
        totalBatches: number;
        successfulBatches: number;
        failedBatches: number;
        averageResponseTime: number;
      };
    } catch (error) {
      return {
        totalBatches: 0,
        successfulBatches: 0,
        failedBatches: 0,
        averageResponseTime: 0
      };
    }
  }

  // Configuration
  setMaxBatchSize(size: number): void {
    this.maxBatchSize = Math.min(size, 1000); // Max 1000 as safety limit
  }

  getMaxBatchSize(): number {
    return this.maxBatchSize;
  }
}

// Export singleton instance
export const googleBatch = GoogleBatchService.getInstance();

// Export types
export type { BatchRequest, BatchResponse, BatchResult };