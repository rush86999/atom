/**
 * VS Code Skills Complete
 * Complete VS Code development environment integration with file management, search, and memory operations
 */

import { atomApiClient } from '@atom/apiclient';
import { logger } from '@atom/logger';
import { format } from 'date-fns';

// VS Code Data Models
export interface VSCodeFile {
  id: string;
  path: string;
  name: string;
  extension: string;
  size: number;
  created_at: string;
  modified_at: string;
  content: string;
  content_hash: string;
  language: string;
  encoding: string;
  line_count: number;
  char_count: number;
  is_binary: boolean;
  is_hidden: boolean;
  git_status: string;
  build_system: string;
  metadata: any;
}

export interface VSCodeProject {
  id: string;
  name: string;
  path: string;
  type: string;
  files: VSCodeFile[];
  folders: string[];
  settings: any;
  extensions: string[];
  git_info: any;
  build_system: string;
  language_stats: any;
  last_activity: string;
  created_at: string;
  updated_at: string;
  metadata: any;
}

export interface VSCodeExtension {
  id: string;
  name: string;
  publisher: any;
  description: string;
  version: string;
  category: string;
  tags: string[];
  release_date: string;
  last_updated: string;
  download_count: number;
  rating: number;
  is_pre_release: boolean;
  dependencies: string[];
  contributes: any;
  metadata: any;
}

export interface VSCodeSettings {
  user_settings: any;
  workspace_settings: any;
  folder_settings: any;
  keybindings: any[];
  snippets: any;
  tasks: any[];
  launch: any[];
  extensions: any;
  themes: any;
  metadata: any;
}

export interface VSCodeActivity {
  id: string;
  user_id: string;
  project_id: string;
  action_type: string;
  file_path: string;
  content: string;
  timestamp: string;
  language: string;
  session_id: string;
  metadata: any;
}

export interface VSCodeMemorySettings {
  user_id: string;
  ingestion_enabled: boolean;
  sync_frequency: string;
  data_retention_days: number;
  include_projects: string[];
  exclude_projects: string[];
  include_file_types: string[];
  exclude_file_types: string[];
  max_file_size_mb: number;
  max_files_per_project: number;
  include_hidden_files: boolean;
  include_binary_files: boolean;
  code_search_enabled: boolean;
  semantic_search_enabled: boolean;
  metadata_extraction_enabled: boolean;
  activity_logging_enabled: boolean;
  last_sync_timestamp?: string;
  next_sync_timestamp?: string;
  sync_in_progress: boolean;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
}

export interface VSCodeIngestionStats {
  user_id: string;
  total_projects_ingested: number;
  total_files_ingested: number;
  total_activities_ingested: number;
  last_ingestion_timestamp?: string;
  total_size_mb: number;
  failed_ingestions: number;
  last_error_message?: string;
  avg_files_per_project: number;
  avg_processing_time_ms: number;
  created_at?: string;
  updated_at?: string;
}

export interface VSCodeLanguageStats {
  languages: Record<string, {
    count: number;
    size: number;
    size_mb: number;
    percentage: number;
    extensions: string[];
  }>;
  total_files: number;
  total_size: number;
  dominant_language: string;
}

// VS Code Utilities
export const vscodeUtils = {
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
   * Get file icon based on extension
   */
  getFileIcon: (extension: string): string => {
    const iconMap: Record<string, string> = {
      '.js': 'javascript',
      '.jsx': 'javascriptreact',
      '.ts': 'typescript',
      '.tsx': 'typescriptreact',
      '.py': 'python',
      '.java': 'java',
      '.cpp': 'cpp',
      '.c': 'c',
      '.cs': 'csharp',
      '.go': 'go',
      '.rs': 'rust',
      '.php': 'php',
      '.rb': 'ruby',
      '.swift': 'swift',
      '.kt': 'kotlin',
      '.scala': 'scala',
      '.html': 'html',
      '.htm': 'html',
      '.css': 'css',
      '.scss': 'scss',
      '.sass': 'sass',
      '.less': 'less',
      '.json': 'json',
      '.yaml': 'yaml',
      '.yml': 'yaml',
      '.toml': 'toml',
      '.xml': 'xml',
      '.md': 'markdown',
      '.txt': 'text',
      '.sql': 'sql',
      '.graphql': 'graphql',
      '.dockerfile': 'docker'
    };
    
    return iconMap[extension] || 'file';
  },

  /**
   * Get language color
   */
  getLanguageColor: (language: string): string => {
    const colorMap: Record<string, string> = {
      'javascript': 'yellow',
      'typescript': 'blue',
      'python': 'green',
      'java': 'orange',
      'cpp': 'blue',
      'c': 'gray',
      'csharp': 'purple',
      'go': 'cyan',
      'rust': 'red',
      'php': 'purple',
      'ruby': 'red',
      'swift': 'orange',
      'kotlin': 'purple',
      'scala': 'red',
      'html': 'orange',
      'css': 'blue',
      'scss': 'pink',
      'json': 'gray',
      'yaml': 'cyan',
      'xml': 'orange',
      'markdown': 'blue',
      'sql': 'blue',
      'docker': 'cyan',
      'plaintext': 'gray'
    };
    
    return colorMap[language] || 'gray';
  },

  /**
   * Detect language from file path
   */
  detectLanguage: (filePath: string): string => {
    const ext = filePath.split('.').pop()?.toLowerCase() || '';
    
    const languageMap: Record<string, string> = {
      'js': 'javascript',
      'jsx': 'javascriptreact',
      'ts': 'typescript',
      'tsx': 'typescriptreact',
      'py': 'python',
      'java': 'java',
      'cpp': 'cpp',
      'c': 'c',
      'cs': 'csharp',
      'go': 'go',
      'rs': 'rust',
      'php': 'php',
      'rb': 'ruby',
      'swift': 'swift',
      'kt': 'kotlin',
      'scala': 'scala',
      'html': 'html',
      'htm': 'html',
      'css': 'css',
      'scss': 'scss',
      'sass': 'sass',
      'less': 'less',
      'json': 'json',
      'yaml': 'yaml',
      'yml': 'yaml',
      'toml': 'toml',
      'xml': 'xml',
      'md': 'markdown',
      'txt': 'plaintext',
      'sql': 'sql',
      'graphql': 'graphql',
      'dockerfile': 'docker'
    };
    
    return languageMap[ext] || 'plaintext';
  },

  /**
   * Check if file is binary
   */
  isBinaryFile: (fileName: string, content: string): boolean => {
    const binaryExtensions = ['.exe', '.dll', '.so', '.dylib', '.bin', '.dat', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz'];
    
    // Check extension
    const ext = fileName.split('.').pop()?.toLowerCase() || '';
    if (binaryExtensions.includes(ext)) {
      return true;
    }
    
    // Check content for null bytes (common in binary files)
    return content.includes('\0');
  },

  /**
   * Check if file is hidden
   */
  isHiddenFile: (fileName: string): boolean => {
    return fileName.startsWith('.');
  },

  /**
   * Parse file path
   */
  parseFilePath: (filePath: string) => {
    const parts = filePath.split('/');
    const fileName = parts[parts.length - 1];
    const extension = fileName.includes('.') ? '.' + fileName.split('.').pop()?.toLowerCase() : '';
    const name = fileName.includes('.') ? fileName.substring(0, fileName.lastIndexOf('.')) : fileName;
    const directory = parts.slice(0, -1).join('/');
    
    return { name, extension, fileName, directory };
  },

  /**
   * Create VS Code file from dict
   */
  createVSCodeFile: (data: any): VSCodeFile => {
    return {
      id: data.id || '',
      path: data.path || '',
      name: data.name || '',
      extension: data.extension || '',
      size: data.size || 0,
      created_at: data.created_at || '',
      modified_at: data.modified_at || '',
      content: data.content || '',
      content_hash: data.content_hash || '',
      language: data.language || 'plaintext',
      encoding: data.encoding || 'utf-8',
      line_count: data.line_count || 0,
      char_count: data.char_count || 0,
      is_binary: data.is_binary || false,
      is_hidden: data.is_hidden || false,
      git_status: data.git_status || '',
      build_system: data.build_system || '',
      metadata: data.metadata || {}
    };
  },

  /**
   * Create VS Code project from dict
   */
  createVSCodeProject: (data: any): VSCodeProject => {
    return {
      id: data.id || '',
      name: data.name || '',
      path: data.path || '',
      type: data.type || 'folder',
      files: (data.files || []).map(vscodeUtils.createVSCodeFile),
      folders: data.folders || [],
      settings: data.settings || {},
      extensions: data.extensions || [],
      git_info: data.git_info || {},
      build_system: data.build_system || '',
      language_stats: data.language_stats || {},
      last_activity: data.last_activity || '',
      created_at: data.created_at || '',
      updated_at: data.updated_at || '',
      metadata: data.metadata || {}
    };
  },

  /**
   * Create VS Code extension from dict
   */
  createVSCodeExtension: (data: any): VSCodeExtension => {
    return {
      id: data.id || '',
      name: data.name || '',
      publisher: data.publisher || {},
      description: data.description || '',
      version: data.version || '',
      category: data.category || '',
      tags: data.tags || [],
      release_date: data.release_date || '',
      last_updated: data.last_updated || '',
      download_count: data.download_count || 0,
      rating: data.rating || 0,
      is_pre_release: data.is_pre_release || false,
      dependencies: data.dependencies || [],
      contributes: data.contributes || {},
      metadata: data.metadata || {}
    };
  },

  /**
   * Create VS Code settings from dict
   */
  createVSCodeSettings: (data: any): VSCodeSettings => {
    return {
      user_settings: data.user_settings || {},
      workspace_settings: data.workspace_settings || {},
      folder_settings: data.folder_settings || {},
      keybindings: data.keybindings || [],
      snippets: data.snippets || {},
      tasks: data.tasks || [],
      launch: data.launch || [],
      extensions: data.extensions || {},
      themes: data.themes || {},
      metadata: data.metadata || {}
    };
  },

  /**
   * Validate workspace path
   */
  validateWorkspacePath: (path: string): boolean => {
    // Basic validation
    if (!path || path.trim() === '') {
      return false;
    }
    
    // Check for valid path patterns
    const validPatterns = [
      /^[a-zA-Z]:\\/, // Windows absolute
      /^\/[^\/]/, // Unix absolute
      ^\.\//, // Relative
      ^\.\.\//, // Parent relative
      /^[^\/\\]/ // Relative
    ];
    
    return validPatterns.some(pattern => pattern.test(path));
  },

  /**
   * Sanitize file path
   */
  sanitizeFilePath: (filePath: string): string => {
    return filePath.replace(/[<>:"|?*]/g, '');
  }
};

// VS Code Skills Implementation
export const vscodeSkills = {
  /**
   * Get workspace information
   */
  vscodeGetWorkspace: async (
    userId: string,
    workspacePath: string
  ): Promise<VSCodeProject> => {
    try {
      logger.info(`Getting VS Code workspace for user ${userId}: ${workspacePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/workspace/info', {
        user_id: userId,
        workspace_path: workspacePath
      });
      
      const data = response.data;
      
      if (data.ok) {
        const project = vscodeUtils.createVSCodeProject(data.workspace);
        logger.info(`VS Code workspace retrieved: ${project.name}`);
        return project;
      } else {
        throw new Error(data.error || 'Failed to get workspace information');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetWorkspace:', error);
      throw new Error(`Failed to get VS Code workspace: ${error.message}`);
    }
  },

  /**
   * Search workspace files
   */
  vscodeSearchWorkspace: async (
    userId: string,
    workspacePath: string,
    searchQuery: string,
    filePattern?: string,
    caseSensitive: boolean = false,
    includeContent: boolean = true
  ): Promise<VSCodeFile[]> => {
    try {
      logger.info(`Searching VS Code workspace for user ${userId}: ${workspacePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/workspace/search', {
        user_id: userId,
        workspace_path: workspacePath,
        search_query: searchQuery,
        file_pattern: filePattern,
        case_sensitive: caseSensitive,
        include_content: includeContent
      });
      
      const data = response.data;
      
      if (data.ok) {
        const files = data.results.map(vscodeUtils.createVSCodeFile);
        logger.info(`VS Code workspace search completed: ${files.length} results`);
        return files;
      } else {
        throw new Error(data.error || 'Failed to search workspace');
      }
    } catch (error: any) {
      logger.error('Error in vscodeSearchWorkspace:', error);
      throw new Error(`Failed to search VS Code workspace: ${error.message}`);
    }
  },

  /**
   * Get file content
   */
  vscodeGetFile: async (
    userId: string,
    workspacePath: string,
    filePath: string,
    encoding: string = 'utf-8',
    maxSize: number = 1024 * 1024
  ): Promise<VSCodeFile> => {
    try {
      logger.info(`Getting VS Code file for user ${userId}: ${filePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/files/content', {
        user_id: userId,
        workspace_path: workspacePath,
        file_path: filePath,
        encoding: encoding,
        max_size: maxSize
      });
      
      const data = response.data;
      
      if (data.ok) {
        const file = vscodeUtils.createVSCodeFile(data.file);
        logger.info(`VS Code file retrieved: ${file.name}`);
        return file;
      } else {
        throw new Error(data.error || 'Failed to get file content');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetFile:', error);
      throw new Error(`Failed to get VS Code file: ${error.message}`);
    }
  },

  /**
   * Create file
   */
  vscodeCreateFile: async (
    userId: string,
    workspacePath: string,
    filePath: string,
    content: string,
    encoding: string = 'utf-8'
  ): Promise<boolean> => {
    try {
      logger.info(`Creating VS Code file for user ${userId}: ${filePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/files/create', {
        user_id: userId,
        workspace_path: workspacePath,
        file_path: filePath,
        content: content,
        encoding: encoding
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code file created: ${filePath}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to create file');
      }
    } catch (error: any) {
      logger.error('Error in vscodeCreateFile:', error);
      throw new Error(`Failed to create VS Code file: ${error.message}`);
    }
  },

  /**
   * Update file
   */
  vscodeUpdateFile: async (
    userId: string,
    workspacePath: string,
    filePath: string,
    content: string,
    encoding: string = 'utf-8'
  ): Promise<boolean> => {
    try {
      logger.info(`Updating VS Code file for user ${userId}: ${filePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/files/update', {
        user_id: userId,
        workspace_path: workspacePath,
        file_path: filePath,
        content: content,
        encoding: encoding
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code file updated: ${filePath}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to update file');
      }
    } catch (error: any) {
      logger.error('Error in vscodeUpdateFile:', error);
      throw new Error(`Failed to update VS Code file: ${error.message}`);
    }
  },

  /**
   * Delete file
   */
  vscodeDeleteFile: async (
    userId: string,
    workspacePath: string,
    filePath: string
  ): Promise<boolean> => {
    try {
      logger.info(`Deleting VS Code file for user ${userId}: ${filePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/files/delete', {
        user_id: userId,
        workspace_path: workspacePath,
        file_path: filePath
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code file deleted: ${filePath}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete file');
      }
    } catch (error: any) {
      logger.error('Error in vscodeDeleteFile:', error);
      throw new Error(`Failed to delete VS Code file: ${error.message}`);
    }
  },

  /**
   * Upload file
   */
  vscodeUploadFile: async (
    userId: string,
    workspacePath: string,
    file: File,
    uploadPath?: string
  ): Promise<any> => {
    try {
      logger.info(`Uploading VS Code file for user ${userId}: ${file.name}`);
      
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);
      formData.append('workspace_path', workspacePath);
      if (uploadPath) {
        formData.append('upload_path', uploadPath);
      }
      
      const response = await atomApiClient.post('/api/vscode/development/files/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code file uploaded: ${file.name}`);
        return data;
      } else {
        throw new Error(data.error || 'Failed to upload file');
      }
    } catch (error: any) {
      logger.error('Error in vscodeUploadFile:', error);
      throw new Error(`Failed to upload VS Code file: ${error.message}`);
    }
  },

  /**
   * Download file
   */
  vscodeDownloadFile: async (
    userId: string,
    workspacePath: string,
    filePath: string
  ): Promise<Blob> => {
    try {
      logger.info(`Downloading VS Code file for user ${userId}: ${filePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/files/download', {
        user_id: userId,
        workspace_path: workspacePath,
        file_path: filePath
      }, {
        responseType: 'blob'
      });
      
      logger.info(`VS Code file downloaded: ${filePath}`);
      return response.data;
    } catch (error: any) {
      logger.error('Error in vscodeDownloadFile:', error);
      throw new Error(`Failed to download VS Code file: ${error.message}`);
    }
  },

  /**
   * Search extensions
   */
  vscodeSearchExtensions: async (
    query: string,
    category?: string,
    pageSize: number = 50,
    pageNumber: number = 1
  ): Promise<VSCodeExtension[]> => {
    try {
      logger.info(`Searching VS Code extensions: ${query}`);
      
      const response = await atomApiClient.post('/api/vscode/development/extensions/search', {
        query: query,
        category: category,
        page_size: pageSize,
        page_number: pageNumber
      });
      
      const data = response.data;
      
      if (data.ok) {
        const extensions = data.extensions.map(vscodeUtils.createVSCodeExtension);
        logger.info(`VS Code extensions search completed: ${extensions.length} results`);
        return extensions;
      } else {
        throw new Error(data.error || 'Failed to search extensions');
      }
    } catch (error: any) {
      logger.error('Error in vscodeSearchExtensions:', error);
      throw new Error(`Failed to search VS Code extensions: ${error.message}`);
    }
  },

  /**
   * Get extension information
   */
  vscodeGetExtension: async (
    extensionId: string
  ): Promise<VSCodeExtension> => {
    try {
      logger.info(`Getting VS Code extension: ${extensionId}`);
      
      const response = await atomApiClient.post('/api/vscode/development/extensions/info', {
        extension_id: extensionId
      });
      
      const data = response.data;
      
      if (data.ok) {
        const extension = vscodeUtils.createVSCodeExtension(data.extension);
        logger.info(`VS Code extension retrieved: ${extension.name}`);
        return extension;
      } else {
        throw new Error(data.error || 'Failed to get extension information');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetExtension:', error);
      throw new Error(`Failed to get VS Code extension: ${error.message}`);
    }
  },

  /**
   * Get recommended extensions
   */
  vscodeGetRecommendedExtensions: async (
    workspacePath: string,
    language?: string
  ): Promise<VSCodeExtension[]> => {
    try {
      logger.info(`Getting VS Code recommended extensions for workspace: ${workspacePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/extensions/recommendations', {
        project_path: workspacePath,
        language: language
      });
      
      const data = response.data;
      
      if (data.ok) {
        const extensions = data.recommendations.map(vscodeUtils.createVSCodeExtension);
        logger.info(`VS Code recommended extensions retrieved: ${extensions.length} results`);
        return extensions;
      } else {
        throw new Error(data.error || 'Failed to get recommended extensions');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetRecommendedExtensions:', error);
      throw new Error(`Failed to get VS Code recommended extensions: ${error.message}`);
    }
  },

  /**
   * Get workspace languages
   */
  vscodeGetLanguages: async (
    workspacePath: string
  ): Promise<VSCodeLanguageStats> => {
    try {
      logger.info(`Getting VS Code workspace languages: ${workspacePath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/workspace/languages', {
        workspace_path: workspacePath
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code workspace languages retrieved: ${data.language_stats}`);
        return data.language_stats;
      } else {
        throw new Error(data.error || 'Failed to get workspace languages');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetLanguages:', error);
      throw new Error(`Failed to get VS Code workspace languages: ${error.message}`);
    }
  },

  /**
   * Log development activity
   */
  vscodeLogActivity: async (
    userId: string,
    projectId: string,
    actionType: string,
    filePath: string,
    content: string = '',
    sessionId?: string,
    metadata?: any
  ): Promise<boolean> => {
    try {
      logger.info(`Logging VS Code activity for user ${userId}: ${actionType}`);
      
      const response = await atomApiClient.post('/api/vscode/development/activity/log', {
        user_id: userId,
        activity: {
          action_type: actionType,
          project_id: projectId,
          file_path: filePath,
          content: content,
          session_id: sessionId,
          metadata: metadata
        }
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code activity logged: ${actionType}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to log activity');
      }
    } catch (error: any) {
      logger.error('Error in vscodeLogActivity:', error);
      throw new Error(`Failed to log VS Code activity: ${error.message}`);
    }
  },

  /**
   * Get memory settings
   */
  vscodeGetMemorySettings: async (userId: string): Promise<VSCodeMemorySettings> => {
    try {
      logger.info(`Getting VS Code memory settings for user ${userId}`);
      
      const response = await atomApiClient.post('/api/vscode/development/memory/settings', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code memory settings retrieved for user ${userId}`);
        return data.settings;
      } else {
        throw new Error(data.error || 'Failed to get memory settings');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetMemorySettings:', error);
      throw new Error(`Failed to get VS Code memory settings: ${error.message}`);
    }
  },

  /**
   * Update memory settings
   */
  vscodeUpdateMemorySettings: async (
    userId: string,
    settings: Partial<VSCodeMemorySettings>
  ): Promise<boolean> => {
    try {
      logger.info(`Updating VS Code memory settings for user ${userId}`);
      
      const response = await atomApiClient.put('/api/vscode/development/memory/settings', {
        user_id: userId,
        ...settings
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code memory settings updated for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to update memory settings');
      }
    } catch (error: any) {
      logger.error('Error in vscodeUpdateMemorySettings:', error);
      throw new Error(`Failed to update VS Code memory settings: ${error.message}`);
    }
  },

  /**
   * Start memory ingestion
   */
  vscodeStartIngestion: async (
    userId: string,
    projectPath: string,
    forceSync: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Starting VS Code ingestion for user ${userId}: ${projectPath}`);
      
      const response = await atomApiClient.post('/api/vscode/development/memory/ingest', {
        user_id: userId,
        project_path: projectPath,
        force_sync: forceSync
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code ingestion started: ${data.ingestion_result.project_ingested}`);
        return data.ingestion_result;
      } else {
        throw new Error(data.error || 'Failed to start ingestion');
      }
    } catch (error: any) {
      logger.error('Error in vscodeStartIngestion:', error);
      throw new Error(`Failed to start VS Code ingestion: ${error.message}`);
    }
  },

  /**
   * Get sync status
   */
  vscodeGetSyncStatus: async (userId: string): Promise<any> => {
    try {
      logger.info(`Getting VS Code sync status for user ${userId}`);
      
      const response = await atomApiClient.post('/api/vscode/development/memory/status', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code sync status retrieved for user ${userId}`);
        return data.memory_status;
      } else {
        throw new Error(data.error || 'Failed to get sync status');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetSyncStatus:', error);
      throw new Error(`Failed to get VS Code sync status: ${error.message}`);
    }
  },

  /**
   * Search memory
   */
  vscodeSearchMemory: async (
    userId: string,
    query: string,
    projectId?: string,
    language?: string,
    limit: number = 50,
    dateFrom?: string,
    dateTo?: string
  ): Promise<VSCodeFile[]> => {
    try {
      logger.info(`Searching VS Code memory for user ${userId}: ${query}`);
      
      const response = await atomApiClient.post('/api/vscode/development/memory/search', {
        user_id: userId,
        query: query,
        project_id: projectId,
        language: language,
        limit: limit,
        date_from: dateFrom,
        date_to: dateTo
      });
      
      const data = response.data;
      
      if (data.ok) {
        const files = data.files.map(vscodeUtils.createVSCodeFile);
        logger.info(`VS Code memory search completed: ${files.length} results`);
        return files;
      } else {
        throw new Error(data.error || 'Failed to search memory');
      }
    } catch (error: any) {
      logger.error('Error in vscodeSearchMemory:', error);
      throw new Error(`Failed to search VS Code memory: ${error.message}`);
    }
  },

  /**
   * Get ingestion statistics
   */
  vscodeGetIngestionStats: async (userId: string): Promise<VSCodeIngestionStats> => {
    try {
      logger.info(`Getting VS Code ingestion stats for user ${userId}`);
      
      const response = await atomApiClient.post('/api/vscode/development/memory/ingestion-stats', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code ingestion stats retrieved for user ${userId}`);
        return data.ingestion_stats;
      } else {
        throw new Error(data.error || 'Failed to get ingestion stats');
      }
    } catch (error: any) {
      logger.error('Error in vscodeGetIngestionStats:', error);
      throw new Error(`Failed to get VS Code ingestion stats: ${error.message}`);
    }
  },

  /**
   * Delete user data
   */
  vscodeDeleteUserData: async (userId: string): Promise<boolean> => {
    try {
      logger.info(`Deleting VS Code user data for user ${userId}`);
      
      const response = await atomApiClient.post('/api/vscode/development/memory/delete', {
        user_id: userId,
        confirm: true
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`VS Code user data deleted for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete user data');
      }
    } catch (error: any) {
      logger.error('Error in vscodeDeleteUserData:', error);
      throw new Error(`Failed to delete VS Code user data: ${error.message}`);
    }
  }
};

// Export default
export default vscodeSkills;