/**
 * OneDrive API Utilities
 * Helper functions for Microsoft Graph API interactions
 * File operations, authentication, and error handling
 */

import {
  OneDriveFile,
  OneDriveFolder,
  OneDriveSearchQuery,
  OneDriveAPIError,
  OneDriveUtils,
} from '../types';

export class OneDriveAPIError extends Error {
  constructor(
    message: string,
    public code: string,
    public requestPath?: string,
    public timestamp?: string,
    public requestId?: string,
    public clientRequestId?: string
  ) {
    super(message);
    this.name = 'OneDriveAPIError';
  }
}

export interface OneDriveAPIClient {
  get(endpoint: string, params?: Record<string, any>): Promise<any>;
  post(endpoint: string, data?: any): Promise<any>;
  put(endpoint: string, data?: any): Promise<any>;
  patch(endpoint: string, data?: any): Promise<any>;
  delete(endpoint: string): Promise<any>;
  uploadFile(file: File, folderId?: string, onProgress?: (progress: number) => void): Promise<OneDriveFile>;
  downloadFile(fileId: string): Promise<Blob>;
  createFolder(name: string, parentFolderId?: string): Promise<OneDriveFolder>;
  searchFiles(query: OneDriveSearchQuery): Promise<{ files: OneDriveFile[]; folders: OneDriveFolder[]; total?: number }>;
  getFileInfo(fileId: string): Promise<OneDriveFile>;
  getFolderContents(folderId: string): Promise<{ files: OneDriveFile[]; folders: OneDriveFolder[] }>;
}

export class OneDriveAPIClientImpl implements OneDriveAPIClient {
  private baseUrl = 'https://graph.microsoft.com/v1.0';
  private accessToken: string;
  private refreshToken?: string;
  private onTokenRefresh?: (newToken: string) => Promise<string>;

  constructor(
    accessToken: string,
    refreshToken?: string,
    onTokenRefresh?: (newToken: string) => Promise<string>
  ) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    this.onTokenRefresh = onTokenRefresh;
  }

  private async makeRequest(
    method: string,
    endpoint: string,
    data?: any,
    headers: Record<string, string> = {}
  ): Promise<any> {
    const url = `${this.baseUrl}${endpoint}`;
    const defaultHeaders = {
      'Authorization': `Bearer ${this.accessToken}`,
      'Content-Type': 'application/json',
      ...headers,
    };

    try {
      const response = await fetch(url, {
        method,
        headers: defaultHeaders,
        body: data ? JSON.stringify(data) : undefined,
      });

      if (response.status === 401 && this.refreshToken && this.onTokenRefresh) {
        // Try to refresh the token
        try {
          const newToken = await this.onTokenRefresh(this.refreshToken);
          this.accessToken = newToken;
          
          // Retry with new token
          const retryHeaders = {
            ...defaultHeaders,
            'Authorization': `Bearer ${this.accessToken}`,
          };
          
          const retryResponse = await fetch(url, {
            method,
            headers: retryHeaders,
            body: data ? JSON.stringify(data) : undefined,
          });
          
          if (!retryResponse.ok) {
            throw await this.parseError(retryResponse);
          }
          
          return await retryResponse.json();
        } catch (tokenError) {
          throw new OneDriveAPIError(
            'Token refresh failed',
            'TOKEN_REFRESH_FAILED',
            endpoint
          );
        }
      }

      if (!response.ok) {
        throw await this.parseError(response);
      }

      // Handle different response types
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      } else {
        return await response.blob();
      }

    } catch (error) {
      if (error instanceof OneDriveAPIError) {
        throw error;
      }
      
      throw new OneDriveAPIError(
        error instanceof Error ? error.message : 'Unknown error',
        'NETWORK_ERROR',
        endpoint
      );
    }
  }

  private async parseError(response: Response): Promise<OneDriveAPIError> {
    try {
      const errorData = await response.json();
      const error = errorData.error;
      
      return new OneDriveAPIError(
        error.message || 'Unknown API error',
        error.code || 'UNKNOWN_ERROR',
        response.url,
        response.headers.get('date') || undefined,
        error.innerError?.['request-id'],
        error.innerError?.['client-request-id']
      );
    } catch {
      return new OneDriveAPIError(
        `HTTP ${response.status}: ${response.statusText}`,
        'HTTP_ERROR',
        response.url
      );
    }
  }

  async get(endpoint: string, params?: Record<string, any>): Promise<any> {
    let url = endpoint;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      });
      const queryString = searchParams.toString();
      if (queryString) {
        url += (endpoint.includes('?') ? '&' : '?') + queryString;
      }
    }

    return this.makeRequest('GET', url);
  }

  async post(endpoint: string, data?: any): Promise<any> {
    return this.makeRequest('POST', endpoint, data);
  }

  async put(endpoint: string, data?: any): Promise<any> {
    return this.makeRequest('PUT', endpoint, data);
  }

  async patch(endpoint: string, data?: any): Promise<any> {
    return this.makeRequest('PATCH', endpoint, data);
  }

  async delete(endpoint: string): Promise<any> {
    return this.makeRequest('DELETE', endpoint);
  }

  async uploadFile(
    file: File, 
    folderId?: string, 
    onProgress?: (progress: number) => void
  ): Promise<OneDriveFile> {
    // Determine upload endpoint
    let uploadEndpoint = `/me/drive/root:/${encodeURIComponent(file.name)}:/content`;
    
    if (folderId) {
      uploadEndpoint = `/me/drive/items/${folderId}:/${encodeURIComponent(file.name)}:/content`;
    }

    // For small files (< 4MB), use simple upload
    if (file.size < 4 * 1024 * 1024) {
      const response = await this.makeRequest('PUT', uploadEndpoint, file, {
        'Content-Type': file.type,
      });
      return response;
    }

    // For larger files, use resumable upload
    return this.uploadFileResumable(file, uploadEndpoint, onProgress);
  }

  private async uploadFileResumable(
    file: File,
    uploadEndpoint: string,
    onProgress?: (progress: number) => void
  ): Promise<OneDriveFile> {
    // Create upload session
    const uploadSessionEndpoint = uploadEndpoint.replace('/content', '/createUploadSession');
    const sessionResponse = await this.post(uploadSessionEndpoint, {
      item: {
        '@microsoft.graph.conflictBehavior': 'replace',
        name: file.name,
        file: {},
      },
    });

    const uploadUrl = sessionResponse.uploadUrl;
    const chunkSize = 320 * 1024; // 320KB chunks
    let uploadedBytes = 0;
    const totalBytes = file.size;

    while (uploadedBytes < totalBytes) {
      const chunk = file.slice(uploadedBytes, uploadedBytes + chunkSize);
      const contentRange = `bytes ${uploadedBytes}-${Math.min(uploadedBytes + chunkSize - 1, totalBytes - 1)}/${totalBytes}`;

      const response = await fetch(uploadUrl, {
        method: 'PUT',
        headers: {
          'Content-Length': chunk.size.toString(),
          'Content-Range': contentRange,
        },
        body: chunk,
      });

      if (!response.ok) {
        throw await this.parseError(response);
      }

      uploadedBytes += chunk.size;
      
      if (onProgress) {
        onProgress((uploadedBytes / totalBytes) * 100);
      }

      // If we get a final response, return it
      const responseJson = await response.json();
      if (responseJson.id) {
        return responseJson;
      }
    }

    throw new OneDriveAPIError('Upload failed', 'UPLOAD_FAILED');
  }

  async downloadFile(fileId: string): Promise<Blob> {
    const response = await this.get(`/me/drive/items/${fileId}/content`);
    return response;
  }

  async createFolder(name: string, parentFolderId?: string): Promise<OneDriveFolder> {
    let endpoint = '/me/drive/root/children';
    
    if (parentFolderId) {
      endpoint = `/me/drive/items/${parentFolderId}/children`;
    }

    const folderData = {
      name,
      folder: {},
      '@microsoft.graph.conflictBehavior': 'rename',
    };

    return this.post(endpoint, folderData);
  }

  async searchFiles(query: OneDriveSearchQuery): Promise<{ 
    files: OneDriveFile[]; 
    folders: OneDriveFolder[]; 
    total?: number 
  }> {
    const searchParams: Record<string, any> = {};

    // Build search query
    let searchQuery = query.query || '';
    
    // Add filters
    const filters: string[] = [];
    
    if (query.fileTypes && query.fileTypes.length > 0) {
      const fileFilter = query.fileTypes.map(type => `fileType:'${type}'`).join(' OR ');
      searchQuery += ` ${fileFilter}`;
    }

    if (query.dateRange) {
      if (query.dateRange.from) {
        filters.push(`lastModifiedDateTime ge ${query.dateRange.from}`);
      }
      if (query.dateRange.to) {
        filters.push(`lastModifiedDateTime le ${query.dateRange.to}`);
      }
    }

    if (query.sizeRange) {
      if (query.sizeRange.min !== undefined) {
        filters.push(`size ge ${query.sizeRange.min}`);
      }
      if (query.sizeRange.max !== undefined) {
        filters.push(`size le ${query.sizeRange.max}`);
      }
    }

    // Set search parameters
    searchParams.q = searchQuery.trim();
    
    if (filters.length > 0) {
      searchParams.$filter = filters.join(' and ');
    }

    if (query.sortBy) {
      searchParams.$orderby = `${query.sortBy} ${query.sortOrder || 'asc'}`;
    }

    if (query.limit) {
      searchParams.$top = query.limit;
    }

    if (query.offset) {
      searchParams.$skip = query.offset;
    }

    const response = await this.get('/me/drive/root/search', searchParams);
    
    const items = response.value || [];
    const files = items.filter((item: any) => !item.folder);
    const folders = items.filter((item: any) => item.folder);

    return {
      files,
      folders,
      total: response['@odata.count'],
    };
  }

  async getFileInfo(fileId: string): Promise<OneDriveFile> {
    return this.get(`/me/drive/items/${fileId}`);
  }

  async getFolderContents(folderId: string): Promise<{ 
    files: OneDriveFile[]; 
    folders: OneDriveFolder[] 
  }> {
    const response = await this.get(`/me/drive/items/${folderId}/children`);
    
    const items = response.value || [];
    const files = items.filter((item: any) => !item.folder);
    const folders = items.filter((item: any) => item.folder);

    return { files, folders };
  }

  // Advanced operations

  async moveItem(itemId: string, parentId: string, newName?: string): Promise<OneDriveFile> {
    const moveData: any = {
      parentReference: {
        id: parentId,
      },
    };

    if (newName) {
      moveData.name = newName;
    }

    return this.patch(`/me/drive/items/${itemId}`, moveData);
  }

  async copyItem(itemId: string, parentId: string, newName?: string): Promise<OneDriveFile> {
    const copyData: any = {
      parentReference: {
        id: parentId,
      },
    };

    if (newName) {
      copyData.name = newName;
    }

    return this.post(`/me/drive/items/${itemId}/copy`, copyData);
  }

  async deleteItem(itemId: string): Promise<void> {
    await this.delete(`/me/drive/items/${itemId}`);
  }

  async getPermissions(itemId: string): Promise<any[]> {
    const response = await this.get(`/me/drive/items/${itemId}/permissions`);
    return response.value || [];
  }

  async shareItem(
    itemId: string, 
    recipients: string[], 
    requireSignIn: boolean = true,
    sendInvitation: boolean = true
  ): Promise<any> {
    const shareData = {
      requireSignIn,
      sendInvitation,
      recipients: recipients.map(email => ({ email })),
    };

    return this.post(`/me/drive/items/${itemId}/invite`, shareData);
  }

  async getThumbnailUrl(itemId: string, size: 'small' | 'medium' | 'large' = 'medium'): Promise<string | null> {
    try {
      const response = await this.get(`/me/drive/items/${itemId}/thumbnails`, {
        select: `${size},url`,
        $top: 1,
      });

      if (response.value && response.value.length > 0) {
        return response.value[0][size]?.url || null;
      }
      
      return null;
    } catch {
      return null;
    }
  }

  async createShareLink(
    itemId: string, 
    type: 'view' | 'edit' = 'view',
    scope: 'anonymous' | 'organization' = 'anonymous'
  ): Promise<any> {
    const linkData = {
      type,
      scope,
    };

    return this.post(`/me/drive/items/${itemId}/createLink`, linkData);
  }

  async getRecentFiles(limit: number = 25): Promise<OneDriveFile[]> {
    const response = await this.get('/me/drive/recent', {
      $top: limit,
    });
    
    return response.value || [];
  }

  async getSharedWithMe(limit: number = 25): Promise<OneDriveFile[]> {
    const response = await this.get('/me/drive/sharedWithMe', {
      $top: limit,
    });
    
    return response.value || [];
  }
}

// Utility functions
export const OneDriveAPITools = {
  /**
   * Create a new API client instance
   */
  createClient: (
    accessToken: string,
    refreshToken?: string,
    onTokenRefresh?: (newToken: string) => Promise<string>
  ): OneDriveAPIClient => {
    return new OneDriveAPIClientImpl(accessToken, refreshToken, onTokenRefresh);
  },

  /**
   * Validate access token format
   */
  validateAccessToken: (token: string): boolean => {
    // Microsoft access tokens are JWT strings
    return typeof token === 'string' && token.split('.').length === 3;
  },

  /**
   * Extract token expiration time
   */
  getTokenExpiration: (token: string): number | null => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp ? payload.exp * 1000 : null;
    } catch {
      return null;
    }
  },

  /**
   * Check if token is expired or will expire soon
   */
  isTokenExpired: (token: string, bufferMs: number = 5 * 60 * 1000): boolean => {
    const expiration = OneDriveAPITools.getTokenExpiration(token);
    if (!expiration) return false;
    
    return Date.now() + bufferMs >= expiration;
  },

  /**
   * Handle common API errors with user-friendly messages
   */
  getErrorMessage: (error: OneDriveAPIError): string => {
    const errorMessages: Record<string, string> = {
      'TOKEN_REFRESH_FAILED': 'Authentication failed. Please sign in again.',
      'ACCESS_DENIED': 'You don\'t have permission to perform this action.',
      'ITEM_NOT_FOUND': 'The requested file or folder was not found.',
      'QUOTA_EXCEEDED': 'You have run out of storage space.',
      'RATE_LIMITED': 'Too many requests. Please try again later.',
      'FILE_TOO_LARGE': 'The file is too large to upload.',
      'UPLOAD_FAILED': 'File upload failed. Please try again.',
      'NETWORK_ERROR': 'Network connection failed. Please check your internet.',
      'UNKNOWN_ERROR': 'An unexpected error occurred.',
    };

    return errorMessages[error.code] || error.message;
  },

  /**
   * Determine if an error is retryable
   */
  isRetryableError: (error: OneDriveAPIError): boolean => {
    const retryableCodes = [
      'RATE_LIMITED',
      'NETWORK_ERROR',
      'TIMEOUT',
      'SERVICE_UNAVAILABLE',
    ];

    return retryableCodes.includes(error.code);
  },

  /**
   * Calculate retry delay with exponential backoff
   */
  calculateRetryDelay: (attempt: number, baseDelay: number = 1000): number => {
    return Math.min(baseDelay * Math.pow(2, attempt), 30000); // Max 30 seconds
  },
};

export default OneDriveAPITools;