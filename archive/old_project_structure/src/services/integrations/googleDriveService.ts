/**
 * Google Drive Integration Service
 *
 * This service provides TypeScript integration for Google Drive operations
 * including file listing, search, and authentication.
 */

import { apiService } from '../utils/api-service';

export interface GoogleDriveFile {
  id: string;
  name: string;
  mimeType: string;
  webViewLink?: string;
  createdTime?: string;
  modifiedTime?: string;
  size?: number;
}

export interface GoogleDriveFileList {
  files: GoogleDriveFile[];
  nextPageToken?: string;
}

export interface GoogleDriveSearchRequest {
  query: string;
  pageSize?: number;
  pageToken?: string;
}

export interface GoogleDriveAuthResponse {
  auth_url: string;
  state: string;
}

export interface GoogleDriveServiceResponse<T> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
}

class GoogleDriveService {
  private basePath = '/google_drive';

  /**
   * Initiate Google Drive OAuth authentication
   */
  async authenticate(userId: string): Promise<GoogleDriveServiceResponse<GoogleDriveAuthResponse>> {
    try {
      const response = await apiService.get(`${this.basePath}/auth`, {
        params: { user_id: userId }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Google Drive authentication failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Authentication failed'
      };
    }
  }

  /**
   * List files from Google Drive
   */
  async listFiles(
    accessToken: string,
    folderId?: string,
    pageSize: number = 100,
    pageToken?: string
  ): Promise<GoogleDriveServiceResponse<GoogleDriveFileList>> {
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
      console.error('Google Drive list files failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to list files'
      };
    }
  }

  /**
   * Search files in Google Drive
   */
  async searchFiles(
    accessToken: string,
    request: GoogleDriveSearchRequest
  ): Promise<GoogleDriveServiceResponse<GoogleDriveFileList>> {
    try {
      const response = await apiService.post(`${this.basePath}/search`, request, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Google Drive search failed:', error);
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
  ): Promise<GoogleDriveServiceResponse<GoogleDriveFile>> {
    try {
      const response = await apiService.get(`${this.basePath}/files/${fileId}`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Google Drive get file metadata failed:', error);
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
  ): Promise<GoogleDriveServiceResponse<{ downloadUrl: string; expiration: string }>> {
    try {
      const response = await apiService.get(`${this.basePath}/files/${fileId}/download`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Google Drive download file failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Download failed'
      };
    }
  }

  /**
   * Health check for Google Drive service
   */
  async healthCheck(): Promise<GoogleDriveServiceResponse<{ status: string; service: string; timestamp: string }>> {
    try {
      const response = await apiService.get(`${this.basePath}/health`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Google Drive health check failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Health check failed'
      };
    }
  }

  /**
   * Get service capabilities
   */
  async getCapabilities(): Promise<GoogleDriveServiceResponse<{
    service: string;
    capabilities: string[];
    supportedFileTypes: string[];
  }>> {
    try {
      const response = await apiService.get(`${this.basePath}/capabilities`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Google Drive get capabilities failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get capabilities'
      };
    }
  }
}

// Export singleton instance
export const googleDriveService = new GoogleDriveService();

// Export for use in React components
export default googleDriveService;
