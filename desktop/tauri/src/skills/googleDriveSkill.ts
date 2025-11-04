import { Skill, SkillAction, SkillContext } from '../../types/skillTypes';
import { invoke } from '@tauri-apps/api/tauri';

// Re-export Google types from Gmail skill
export type {
  GoogleUser,
  GoogleDriveFile,
  GoogleDrivePermission,
  GoogleSearchResult
} from './googleGmailSkill';

// Google Drive Specific Types
export interface GoogleDriveFolder {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  createdTime: string;
  modifiedTime: string;
  parents?: string[];
  webViewLink?: string;
  iconLink: string;
  folderColorRgb?: string;
}

export interface GoogleDriveUploadResult {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  webViewLink?: string;
  webContentLink?: string;
}

export interface GoogleDriveFileList {
  files: GoogleDriveFile[];
  nextPageToken?: string;
  incompleteSearch: boolean;
  kind: string;
}

export interface GoogleDriveSearchResult {
  files: GoogleDriveFile[];
  nextPageToken?: string;
  totalResults?: number;
  incompleteSearch: boolean;
}

export interface GoogleDriveShareResult {
  success: boolean;
  fileId: string;
  link?: string;
  error?: string;
}

// Google Drive Skill Implementation
export class GoogleDriveSkill implements Skill {
  name = 'google_drive';
  displayName = 'Google Drive';
  description = 'Manage Google Drive files, folders, and sharing';
  icon = '📁';
  category = 'productivity';
  supportedActions = [
    'list_files',
    'search_files',
    'create_file',
    'create_folder',
    'delete_file',
    'share_file'
  ];

  async execute(action: SkillAction, context: SkillContext): Promise<any> {
    try {
      switch (action.action) {
        case 'list_files':
          return await this.listFiles(action as GoogleDriveListAction, context);
        case 'search_files':
          return await this.searchFiles(action as GoogleDriveSearchAction, context);
        case 'create_file':
          return await this.createFile(action as GoogleDriveCreateAction, context);
        case 'create_folder':
          return await this.createFolder(action as GoogleDriveCreateFolderAction, context);
        case 'delete_file':
          return await this.deleteFile(action as GoogleDriveDeleteAction, context);
        case 'share_file':
          return await this.shareFile(action as GoogleDriveShareAction, context);
        default:
          throw new Error(`Unknown Google Drive action: ${action.action}`);
      }
    } catch (error) {
      console.error('Google Drive skill execution failed:', error);
      throw new Error(`Google Drive skill execution failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async listFiles(action: GoogleDriveListAction, context: SkillContext): Promise<GoogleDriveFileList> {
    const params = {
      userId: context.userId,
      pageSize: action.params.pageSize || 10,
      orderBy: action.params.orderBy || 'modifiedTime desc',
      spaces: action.params.spaces || 'drive',
      q: action.params.q,
      pageToken: action.params.pageToken,
      includeItemsFromAllDrives: false,
      includeRemoved: false,
      fields: 'nextPageToken, incompleteSearch, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, iconLink, thumbnailLink, ownedByMe, permissions, spaces, folderColorRgb)'
    };

    const result = await invoke('google_drive_list_files', params);
    return result as GoogleDriveFileList;
  }

  private async searchFiles(action: GoogleDriveSearchAction, context: SkillContext): Promise<GoogleDriveSearchResult> {
    if (!action.params.q) {
      throw new Error('Search query is required for Google Drive search');
    }

    const params = {
      userId: context.userId,
      q: action.params.q,
      pageSize: action.params.pageSize || 20,
      orderBy: action.params.orderBy || 'relevance desc',
      spaces: action.params.spaces || 'drive',
      pageToken: action.params.pageToken,
      includeItemsFromAllDrives: false,
      includeRemoved: false,
      fields: 'nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, iconLink, thumbnailLink, ownedByMe, permissions, spaces, folderColorRgb)'
    };

    const result = await invoke('google_drive_search_files', params);
    return result as GoogleDriveSearchResult;
  }

  private async createFile(action: GoogleDriveCreateAction, context: SkillContext): Promise<GoogleDriveUploadResult> {
    if (!action.params.name) {
      throw new Error('File name is required for creating Google Drive files');
    }

    const params = {
      userId: context.userId,
      name: action.params.name,
      content: action.params.content || '',
      mimeType: action.params.mimeType || 'text/plain',
      parents: action.params.parents || []
    };

    const result = await invoke('google_drive_create_file', params);
    return result as GoogleDriveUploadResult;
  }

  private async createFolder(action: GoogleDriveCreateFolderAction, context: SkillContext): Promise<GoogleDriveUploadResult> {
    if (!action.params.name) {
      throw new Error('Folder name is required for creating Google Drive folders');
    }

    const params = {
      userId: context.userId,
      name: action.params.name,
      mimeType: 'application/vnd.google-apps.folder',
      parents: action.params.parents || []
    };

    const result = await invoke('google_drive_create_folder', params);
    return result as GoogleDriveUploadResult;
  }

  private async deleteFile(action: GoogleDriveDeleteAction, context: SkillContext): Promise<{ success: boolean; error?: string }> {
    if (!action.params.fileId) {
      throw new Error('File ID is required for deleting Google Drive files');
    }

    const params = {
      userId: context.userId,
      fileId: action.params.fileId
    };

    const result = await invoke('google_drive_delete_file', params);
    return result as { success: boolean; error?: string };
  }

  private async shareFile(action: GoogleDriveShareAction, context: SkillContext): Promise<GoogleDriveShareResult> {
    if (!action.params.fileId) {
      throw new Error('File ID is required for sharing Google Drive files');
    }

    if (!action.params.type || !action.params.role) {
      throw new Error('Share type and role are required for Google Drive sharing');
    }

    const params = {
      userId: context.userId,
      fileId: action.params.fileId,
      role: action.params.role,
      type: action.params.type,
      emailAddress: action.params.emailAddress,
      domain: action.params.domain,
      sendNotificationEmail: action.params.sendNotificationEmail !== false
    };

    const result = await invoke('google_drive_share_file', params);
    return result as GoogleDriveShareResult;
  }

  // Helper methods for common operations
  private isValidFileName(name: string): boolean {
    // Google Drive has fewer restrictions, but still validate
    const invalidChars = /[<>:"|?*\x00-\x1F]/;
    return !invalidChars.test(name) && name.length > 0 && name.length <= 255;
  }

  private buildSearchQuery(query: string, filters?: {
    mimeType?: string;
    modifiedTime?: string;
    size?: string;
  }): string {
    let searchQuery = query;

    if (filters?.mimeType) {
      searchQuery += ` mimeType = '${filters.mimeType}'`;
    }

    if (filters?.modifiedTime) {
      searchQuery += ` modifiedTime > '${filters.modifiedTime}'`;
    }

    if (filters?.size) {
      searchQuery += ` size ${filters.size}`;
    }

    return searchQuery;
  }

  // Method to get file metadata
  async getFileMetadata(fileId: string, context: SkillContext): Promise<GoogleDriveFile> {
    const result = await invoke('google_drive_get_file_metadata', {
      userId: context.userId,
      fileId,
      fields: 'id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, webContentLink, iconLink, thumbnailLink, ownedByMe, permissions, spaces, folderColorRgb'
    });
    return result as GoogleDriveFile;
  }

  // Method to download file content
  async downloadFile(fileId: string, context: SkillContext): Promise<string> {
    const result = await invoke('google_drive_download_file', {
      userId: context.userId,
      fileId
    });
    return result as string;
  }

  // Method to update file content
  async updateFile(fileId: string, content: string, context: SkillContext): Promise<GoogleDriveUploadResult> {
    const result = await invoke('google_drive_update_file', {
      userId: context.userId,
      fileId,
      content
    });
    return result as GoogleDriveUploadResult;
  }
}

// Re-export Drive action types
export type {
  GoogleDriveListAction,
  GoogleDriveSearchAction,
  GoogleDriveCreateAction,
  GoogleDriveCreateFolderAction,
  GoogleDriveDeleteAction,
  GoogleDriveShareAction
} from './googleGmailSkill';