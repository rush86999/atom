/**
 * Enhanced Dropbox Integration
 * Complete Dropbox integration with advanced features
 */

import { 
  invoke, 
  TauriInvokeOptions 
} from '@tauri-apps/api/tauri';
import { SkillExecutionContext } from '../types/skillTypes';
import { EventBus } from '../utils/EventBus';
import { Logger } from '../utils/Logger';

// Enhanced Dropbox Types
export interface DropboxUser {
  account_id: string;
  name: {
    given_name: string;
    surname: string;
    familiar_name: string;
    display_name: string;
    abbreviated_name: string;
  };
  email: string;
  email_verified: boolean;
  profile_photo_url?: string;
  disabled: boolean;
  country?: string;
  locale: string;
  referral_link?: string;
  is_paired: boolean;
  account_type: {
    '.tag': string;
  };
  root_info: {
    '.tag': string;
    root_namespace_id?: string;
    home_namespace_id?: string;
  };
  team_id?: string;
  team_member_id?: string;
  has_folders?: boolean;
}

export interface DropboxFile {
  id: string;
  name: string;
  path_lower: string;
  path_display: string;
  id_mapping: {
    '.tag': string;
    content_hash?: string;
  };
  client_modified: string;
  server_modified: string;
  rev: string;
  size: number;
  is_downloadable: boolean;
  content_hash: string;
  file_lock_info?: {
    is_lockholder: boolean;
    lockholder_name?: string;
    created: string;
  };
  hash?: string;
  has_explicit_shared_members?: boolean;
  sharing_info?: {
    read_only: boolean;
    parent_shared_folder_id: string;
    modified_by: string;
  };
  is_file: boolean;
  is_folder: boolean;
  parent_shared_folder_id?: string;
  property_groups?: Array<{
    template_id: string;
    fields: Array<{
      name: string;
      value: string;
    }>;
  }>;
}

export interface DropboxFolder {
  id: string;
  name: string;
  path_lower: string;
  path_display: string;
  id_mapping: {
    '.tag': string;
  };
  sharing_info?: {
    read_only: boolean;
    parent_shared_folder_id: string;
    shared_folder_id: string;
    traverse_only: boolean;
    no_access: boolean;
  };
  property_groups?: Array<{
    template_id: string;
    fields: Array<{
      name: string;
      value: string;
    }>;
  }>;
  is_file: boolean;
  is_folder: true;
  parent_shared_folder_id?: string;
  shared_folder_id?: string;
}

export interface DropboxSharedLink {
  url: string;
  name: string;
  path_lower: string;
  id: string;
  expires?: string;
  link_permissions: {
    can_revoke: boolean;
    resolved_visibility?: {
      '.tag': string;
      requested_visibility?: {
        '.tag': string;
      };
    };
    require_password: boolean;
    allow_download: boolean;
    allow_uploads: boolean;
    effective_audience?: {
      '.tag': string;
    };
    link_access_level?: {
      '.tag': string;
    };
    expires?: string;
  };
  team_member_info?: {
    display_name: string;
    member_id: string;
  };
  content_owner_team_info?: {
    team_name: string;
    team_id: string;
  };
  content_owner_display_name?: string;
}

export interface DropboxUploadSession {
  session_id: string;
  expires: string;
}

export interface DropboxMetadata {
  size: number;
  is_dir: boolean;
  is_file: boolean;
  client_modified?: string;
  server_modified?: string;
  rev?: string;
  content_hash?: string;
  id?: string;
  name?: string;
  path_lower?: string;
  path_display?: string;
  parent_shared_folder_id?: string;
}

export interface DropboxFileVersion {
  id: string;
  name: string;
  server_modified: string;
  size: number;
  client_modified: string;
  rev: string;
  content_hash: string;
}

export interface DropboxSharingInfo {
  read_only: boolean;
  parent_shared_folder_id?: string;
  shared_folder_id?: string;
  modified_by?: string;
  traverse_only?: boolean;
  no_access?: boolean;
}

export interface DropboxPropertyGroup {
  template_id: string;
  fields: Array<{
    name: string;
    value: string;
  }>;
}

// Skill Parameters
export interface DropboxSkillParams {
  action: 'get_user_info' | 'list_files' | 'list_folders' | 'upload_file' |
          'download_file' | 'create_folder' | 'delete_item' | 'move_item' |
          'copy_item' | 'search_files' | 'create_shared_link' | 'get_file_metadata' |
          'list_file_versions' | 'restore_file_version' | 'get_file_preview' |
          'batch_operations' | 'sync_folder' | 'get_sharing_info' |
          'add_file_properties' | 'get_space_usage';
  path?: string;
  folder_path?: string;
  file_path?: string;
  destination_path?: string;
  file_content?: string;
  file_name?: string;
  query?: string;
  url?: string;
  link_settings?: {
    requested_visibility?: 'public' | 'team_only' | 'password' | 'team_and_password' | 'count';
    link_password?: string;
    expires?: string;
  };
  file_id?: string;
  rev?: string;
  preview_format?: string;
  batch_operations?: Array<{
    action: string;
    path: string;
    to_path?: string;
    autorename?: boolean;
  }>;
  property_groups?: Array<{
    template_id: string;
    fields: Array<{
      name: string;
      value: string;
    }>;
  }>;
  recursive?: boolean;
  include_deleted?: boolean;
  include_media_info?: boolean;
  include_has_explicit_shared_members?: boolean;
  include_mounted_folders?: boolean;
  limit?: number;
}

// Enhanced Dropbox Skill Class
export class DropboxEnhancedSkill {
  private logger = new Logger('DropboxEnhancedSkill');

  async execute(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Dropbox Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'get_user_info':
          return await this.getUserInfo(params, context);
        case 'list_files':
          return await this.listFiles(params, context);
        case 'list_folders':
          return await this.listFolders(params, context);
        case 'upload_file':
          return await this.uploadFile(params, context);
        case 'download_file':
          return await this.downloadFile(params, context);
        case 'create_folder':
          return await this.createFolder(params, context);
        case 'delete_item':
          return await this.deleteItem(params, context);
        case 'move_item':
          return await this.moveItem(params, context);
        case 'copy_item':
          return await this.copyItem(params, context);
        case 'search_files':
          return await this.searchFiles(params, context);
        case 'create_shared_link':
          return await this.createSharedLink(params, context);
        case 'get_file_metadata':
          return await this.getFileMetadata(params, context);
        case 'list_file_versions':
          return await this.listFileVersions(params, context);
        case 'restore_file_version':
          return await this.restoreFileVersion(params, context);
        case 'get_file_preview':
          return await this.getFilePreview(params, context);
        case 'get_sharing_info':
          return await this.getSharingInfo(params, context);
        case 'add_file_properties':
          return await this.addFileProperties(params, context);
        case 'get_space_usage':
          return await this.getSpaceUsage(params, context);
        default:
          throw new Error(`Unsupported Dropbox action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Dropbox Enhanced Skill failed', error);
      throw error;
    }
  }

  private async getUserInfo(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const user = await invoke<DropboxUser>('dropbox_get_user_info_enhanced', options.args);
    
    EventBus.emit('dropbox:user:retrieved', {
      accountId: user.account_id,
      email: user.email,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      user: user,
      timestamp: new Date().toISOString()
    };
  }

  private async listFiles(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path || '',
        recursive: params.recursive || false,
        include_media_info: params.include_media_info || false,
        include_deleted: params.include_deleted || false,
        limit: params.limit || 1000
      }
    };

    const files = await invoke<DropboxFile[]>('dropbox_list_files_enhanced', options.args);
    
    EventBus.emit('dropbox:files:listed', {
      path: params.path || '',
      count: files.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      files: files.filter(file => file.is_file),
      count: files.filter(file => file.is_file).length,
      timestamp: new Date().toISOString()
    };
  }

  private async listFolders(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path || '',
        recursive: params.recursive || false,
        limit: params.limit || 1000
      }
    };

    const items = await invoke<Array<DropboxFile | DropboxFolder>>('dropbox_list_files_enhanced', options.args);
    const folders = items.filter(item => item.is_folder) as DropboxFolder[];
    
    EventBus.emit('dropbox:folders:listed', {
      path: params.path || '',
      count: folders.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      folders: folders,
      count: folders.length,
      timestamp: new Date().toISOString()
    };
  }

  private async uploadFile(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.file_content || !params.file_name) {
      throw new Error('File content and file name are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        file_content: params.file_content,
        file_name: params.file_name,
        folder_path: params.folder_path || '',
        autorename: true
      }
    };

    const file = await invoke<DropboxFile>('dropbox_upload_file_enhanced', options.args);
    
    if (file) {
      EventBus.emit('dropbox:file:uploaded', {
        fileId: file.id,
        name: params.file_name,
        path: file.path_display,
        timestamp: new Date().toISOString()
      });

      this.logger.info('File uploaded successfully', {
        fileId: file.id,
        name: params.file_name,
        size: file.size
      });
    }

    return {
      success: true,
      file: file,
      timestamp: new Date().toISOString()
    };
  }

  private async downloadFile(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path) {
      throw new Error('File path is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path,
        rev: params.rev
      }
    };

    const result = await invoke<any>('dropbox_download_file_enhanced', options.args);
    
    EventBus.emit('dropbox:file:downloaded', {
      path: params.path,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      content: result.content,
      metadata: result.metadata,
      timestamp: new Date().toISOString()
    };
  }

  private async createFolder(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.folder_path && !params.file_name) {
      throw new Error('Folder path or name is required');
    }

    const folderPath = params.folder_path || params.file_name;

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: folderPath,
        autorename: false
      }
    };

    const folder = await invoke<DropboxFolder>('dropbox_create_folder_enhanced', options.args);
    
    if (folder) {
      EventBus.emit('dropbox:folder:created', {
        folderId: folder.id,
        path: folder.path_display,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Folder created successfully', {
        folderId: folder.id,
        path: folder.path_display
      });
    }

    return {
      success: true,
      folder: folder,
      timestamp: new Date().toISOString()
    };
  }

  private async deleteItem(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path) {
      throw new Error('Path is required for deletion');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path
      }
    };

    const result = await invoke<boolean>('dropbox_delete_item_enhanced', options.args);
    
    if (result) {
      EventBus.emit('dropbox:item:deleted', {
        path: params.path,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: result,
      timestamp: new Date().toISOString()
    };
  }

  private async moveItem(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path || !params.destination_path) {
      throw new Error('Source path and destination path are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        from_path: params.path,
        to_path: params.destination_path,
        autorename: false
      }
    };

    const item = await invoke<DropboxFile | DropboxFolder>('dropbox_move_item_enhanced', options.args);
    
    if (item) {
      EventBus.emit('dropbox:item:moved', {
        fromPath: params.path,
        toPath: params.destination_path,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      item: item,
      timestamp: new Date().toISOString()
    };
  }

  private async copyItem(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path || !params.destination_path) {
      throw new Error('Source path and destination path are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        from_path: params.path,
        to_path: params.destination_path,
        autorename: false
      }
    };

    const item = await invoke<DropboxFile | DropboxFolder>('dropbox_copy_item_enhanced', options.args);
    
    if (item) {
      EventBus.emit('dropbox:item:copied', {
        fromPath: params.path,
        toPath: params.destination_path,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      item: item,
      timestamp: new Date().toISOString()
    };
  }

  private async searchFiles(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.query) {
      throw new Error('Search query is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        query: params.query,
        path: params.path || '',
        start: 0,
        max_results: params.limit || 100,
        mode: 'filename'
      }
    };

    const results = await invoke<any>('dropbox_search_files_enhanced', options.args);
    
    EventBus.emit('dropbox:files:searched', {
      query: params.query,
      count: results.matches?.length || 0,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      results: results.matches || [],
      count: results.matches?.length || 0,
      has_more: results.has_more || false,
      cursor: results.cursor,
      timestamp: new Date().toISOString()
    };
  }

  private async createSharedLink(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path) {
      throw new Error('Path is required for shared link');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path,
        settings: params.link_settings || {
          requested_visibility: 'public'
        }
      }
    };

    const link = await invoke<DropboxSharedLink>('dropbox_create_shared_link_enhanced', options.args);
    
    if (link) {
      EventBus.emit('dropbox:shared_link:created', {
        path: params.path,
        url: link.url,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      link: link,
      timestamp: new Date().toISOString()
    };
  }

  private async getFileMetadata(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path) {
      throw new Error('Path is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path,
        include_media_info: params.include_media_info || false,
        include_deleted: params.include_deleted || false,
        include_has_explicit_shared_members: params.include_has_explicit_shared_members || false,
        include_mounted_folders: params.include_mounted_folders || false
      }
    };

    const metadata = await invoke<DropboxMetadata>('dropbox_get_file_metadata_enhanced', options.args);
    
    return {
      success: true,
      metadata: metadata,
      timestamp: new Date().toISOString()
    };
  }

  private async listFileVersions(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path) {
      throw new Error('Path is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path,
        limit: params.limit || 10
      }
    };

    const versions = await invoke<DropboxFileVersion[]>('dropbox_list_file_versions_enhanced', options.args);
    
    return {
      success: true,
      versions: versions,
      count: versions.length,
      timestamp: new Date().toISOString()
    };
  }

  private async restoreFileVersion(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path || !params.rev) {
      throw new Error('Path and rev are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path,
        rev: params.rev
      }
    };

    const file = await invoke<DropboxFile>('dropbox_restore_file_version_enhanced', options.args);
    
    if (file) {
      EventBus.emit('dropbox:file:restored', {
        path: params.path,
        rev: params.rev,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      file: file,
      timestamp: new Date().toISOString()
    };
  }

  private async getFilePreview(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path) {
      throw new Error('Path is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path,
        format: params.preview_format || 'png',
        size: 'm'
      }
    };

    const result = await invoke<any>('dropbox_get_file_preview_enhanced', options.args);
    
    return {
      success: true,
      preview_url: result.preview_url,
      timestamp: new Date().toISOString()
    };
  }

  private async getSharingInfo(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path) {
      throw new Error('Path is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path
      }
    };

    const sharingInfo = await invoke<DropboxSharingInfo>('dropbox_get_sharing_info_enhanced', options.args);
    
    return {
      success: true,
      sharing_info: sharingInfo,
      timestamp: new Date().toISOString()
    };
  }

  private async addFileProperties(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.path || !params.property_groups) {
      throw new Error('Path and property groups are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        path: params.path,
        property_groups: params.property_groups
      }
    };

    const result = await invoke<any>('dropbox_add_file_properties_enhanced', options.args);
    
    if (result) {
      EventBus.emit('dropbox:file:properties:added', {
        path: params.path,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      result: result,
      timestamp: new Date().toISOString()
    };
  }

  private async getSpaceUsage(params: DropboxSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const spaceUsage = await invoke<any>('dropbox_get_space_usage_enhanced', options.args);
    
    return {
      success: true,
      space_usage: spaceUsage,
      timestamp: new Date().toISOString()
    };
  }
}

// Export skill instance
export const dropboxEnhancedSkill = new DropboxEnhancedSkill();

// Export types for external use
export type {
  DropboxUser,
  DropboxFile,
  DropboxFolder,
  DropboxSharedLink,
  DropboxUploadSession,
  DropboxMetadata,
  DropboxFileVersion,
  DropboxSharingInfo,
  DropboxPropertyGroup,
  DropboxSkillParams
};