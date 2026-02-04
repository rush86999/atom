/**
 * Box Integration Service
 *
 * This service provides TypeScript integration for Box operations
 * including file listing, search, authentication, and folder management.
 */

import { apiService } from '../utils/api-service';

export interface BoxFile {
  id: string;
  name: string;
  type: string;
  size?: number;
  created_at?: string;
  modified_at?: string;
  shared_link?: {
    url: string;
    download_url: string;
  };
  path_collection?: {
    total_count: number;
    entries: Array<{
      id: string;
      name: string;
    }>;
  };
}

export interface BoxFolder {
  id: string;
  name: string;
  type: string;
  created_at?: string;
  modified_at?: string;
  item_collection?: {
    total_count: number;
    entries: Array<BoxFile | BoxFolder>;
  };
}

export interface BoxFileList {
  entries: BoxFile[];
  total_count: number;
  offset: number;
  limit: number;
  next_marker?: string;
}

export interface BoxSearchRequest {
  query: string;
  limit?: number;
  offset?: number;
}

export interface BoxAuthResponse {
  auth_url: string;
  state: string;
}

export interface BoxServiceResponse<T> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
}

class BoxService {
  private basePath = '/box';

  /**
   * Initiate Box OAuth authentication
   */
  async authenticate(userId: string): Promise<BoxServiceResponse<BoxAuthResponse>> {
    try {
      const response = await apiService.get(`${this.basePath}/auth`, {
        params: { user_id: userId }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box authentication failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Authentication failed'
      };
    }
  }

  /**
   * List files from Box
   */
  async listFiles(
    accessToken: string,
    folderId: string = '0',
    limit: number = 100,
    offset: number = 0
  ): Promise<BoxServiceResponse<BoxFileList>> {
    try {
      const response = await apiService.get(`${this.basePath}/files`, {
        params: {
          access_token: accessToken,
          folder_id: folderId,
          limit: limit,
          offset: offset
        }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box list files failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to list files'
      };
    }
  }

  /**
   * Search files in Box
   */
  async searchFiles(
    accessToken: string,
    request: BoxSearchRequest
  ): Promise<BoxServiceResponse<BoxFileList>> {
    try {
      const response = await apiService.post(`${this.basePath}/search`, request, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box search failed:', error);
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
  ): Promise<BoxServiceResponse<BoxFile>> {
    try {
      const response = await apiService.get(`${this.basePath}/files/${fileId}`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box get file metadata failed:', error);
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
  ): Promise<BoxServiceResponse<{ downloadUrl: string; expires_at: string }>> {
    try {
      const response = await apiService.get(`${this.basePath}/files/${fileId}/download`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box download file failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Download failed'
      };
    }
  }

  /**
   * Create a new folder in Box
   */
  async createFolder(
    accessToken: string,
    parentFolderId: string,
    folderName: string
  ): Promise<BoxServiceResponse<BoxFolder>> {
    try {
      const response = await apiService.post(`${this.basePath}/folders`, null, {
        params: {
          access_token: accessToken,
          parent_folder_id: parentFolderId,
          folder_name: folderName
        }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box create folder failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to create folder'
      };
    }
  }

  /**
   * Health check for Box service
   */
  async healthCheck(): Promise<BoxServiceResponse<{ status: string; service: string; timestamp: string }>> {
    try {
      const response = await apiService.get(`${this.basePath}/health`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box health check failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Health check failed'
      };
    }
  }

  /**
   * Get service capabilities
   */
  async getCapabilities(): Promise<BoxServiceResponse<{
    service: string;
    capabilities: string[];
    supportedFileTypes: string[];
    integrationFeatures: string[];
  }>> {
    try {
      const response = await apiService.get(`${this.basePath}/capabilities`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Box get capabilities failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get capabilities'
      };
    }
  }
}

// Export singleton instance
export const boxService = new BoxService();

// Export for use in React components
export default boxService;
