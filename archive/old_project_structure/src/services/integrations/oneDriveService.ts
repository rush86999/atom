/**
 * OneDrive Integration Service
 *
 * This service provides TypeScript integration for OneDrive operations
 * including file listing, search, and authentication.
 */

import { apiService } from '../utils/api-service';

export interface OneDriveFile {
  id: string;
  name: string;
  webUrl?: string;
  createdDateTime?: string;
  lastModifiedDateTime?: string;
  size?: number;
  file?: {
    mimeType: string;
  };
  folder?: {
    childCount: number;
  };
}

export interface OneDriveFileList {
  value: OneDriveFile[];
  nextLink?: string;
}

export interface OneDriveSearchRequest {
  query: string;
  pageSize?: number;
  pageToken?: string;
}

export interface OneDriveAuthResponse {
  auth_url: string;
  state: string;
}

export interface OneDriveServiceResponse<T> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
}

class OneDriveService {
  private basePath = '/onedrive';

  /**
   * Initiate OneDrive OAuth authentication
   */
  async authenticate(userId: string): Promise<OneDriveServiceResponse<OneDriveAuthResponse>> {
    try {
      const response = await apiService.get(`${this.basePath}/auth`, {
        params: { user_id: userId }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('OneDrive authentication failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Authentication failed'
      };
    }
  }

  /**
   * List files from OneDrive
   */
  async listFiles(
    accessToken: string,
    folderId?: string,
    pageSize: number = 100,
    pageToken?: string
  ): Promise<OneDriveServiceResponse<OneDriveFileList>> {
    try {
      const response = await apiService.get(`${this.basePath}/files`, {
        params: {
          access_token: accessToken,
          folder_id: folderId,
          page_size: pageSize,
          page_token: pageToken
        }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('OneDrive list files failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to list files'
      };
    }
  }

  /**
   * Search files in OneDrive
   */
  async searchFiles(
    accessToken: string,
    request: OneDriveSearchRequest
  ): Promise<OneDriveServiceResponse<OneDriveFileList>> {
    try {
      const response = await apiService.post(`${this.basePath}/search`, request, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('OneDrive search failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Search failed'
      };
    }
  }

  /**
   * Get metadata for a specific file
   */
  async getFileMetadata(
    accessToken: string,
    fileId: string
  ): Promise<OneDriveServiceResponse<OneDriveFile>> {
    try {
      const response = await apiService.get(`${this.basePath}/files/${fileId}`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('OneDrive get file metadata failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get file metadata'
      };
    }
  }

  /**
   * Get download URL for a file
   */
  async downloadFile(
    accessToken: string,
    fileId: string
  ): Promise<OneDriveServiceResponse<{ downloadUrl: string; expiration: string }>> {
    try {
      const response = await apiService.get(`${this.basePath}/files/${fileId}/download`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('OneDrive download file failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Download failed'
      };
    }
  }

  /**
   * Health check for OneDrive service
   */
  async healthCheck(): Promise<OneDriveServiceResponse<{ status: string; service: string; timestamp: string }>> {
    try {
      const response = await apiService.get(`${this.basePath}/health`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('OneDrive health check failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Health check failed'
      };
    }
  }

  /**
   * Get service capabilities
   */
  async getCapabilities(): Promise<OneDriveServiceResponse<{
    service: string;
    capabilities: string[];
    supportedFileTypes: string[];
    integrationFeatures: string[];
  }>> {
    try {
      const response = await apiService.get(`${this.basePath}/capabilities`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('OneDrive get capabilities failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get capabilities'
      };
    }
  }
}

// Export singleton instance
export const oneDriveService = new OneDriveService();

// Export for use in React components
export default oneDriveService;
