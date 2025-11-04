/**
 * ATOM 3rd Party Integrations - Master Index (Updated with GitHub)
 * Complete Integration System for ATOM Agent Ingestion Pipeline
 * Cross-platform: Next.js & Tauri
 * Production Ready
 */

// Box Integration (File Storage)
export { default as ATOMBoxManager } from '../components/box/ATOMBoxManager';
export { default as ATOMBoxDataSource } from './box/components/BoxDataSource';
export * as BoxTypes from './box/types';

// Dropbox Integration (File Storage)
export { default as ATOMDropboxDataSource } from './dropbox/components/DropboxDataSource';
export * as DropboxTypes from './dropbox/types';

// Google Drive Integration (File Storage) - Complete
export { default as ATOMGDriveDataSource } from './gdrive/components/GDriveDataSource';
export * as GDriveTypes from './gdrive/types';

// OneDrive Integration (File Storage) - Complete
export { default as ATOMOneDriveDataSource } from './onedrive/components/OneDriveDataSource';
export * as OneDriveTypes from './onedrive/types';

// MS Teams Integration (Communication) - Complete
export { default as ATOMTeamsDataSource } from './teams/components/TeamsDataSource';
export * as TeamsTypes from './teams/types';

// Slack Integration (Messaging)
export { default as ATOMSlackDataSource } from './slack/components/SlackDataSource';
export * as SlackTypes from './slack/types';

// Gmail Integration (Email)
export { default as ATOMGmailDataSource } from './gmail/components/GmailDataSource';
export * as GmailTypes from './gmail/types';

// Notion Integration (Documents)
export { default as ATOMNotionDataSource } from './notion/components/NotionDataSource';
export * as NotionTypes from './notion/types';

// Jira Integration (Project Management)
export { default as ATOMJiraManager } from './jira/components/JiraManager';
export { default as ATOMJiraDataSource } from './jira/components/JiraDataSource';
export * as JiraTypes from './jira/types';

// GitHub Integration (Development)
export { default as ATOMGitHubManager } from './github/components/GitHubManager';
export { default as ATOMGitHubDataSource } from './github/components/GitHubDataSource';
export * as GitHubTypes from './github/types';

// Next.js Integration (Development & Deployment)
export { 
  NextjsManager, 
  NextjsCallback, 
  NextjsDesktopManager, 
  NextjsDesktopCallback 
} from './nextjs';
export * as NextjsTypes from './nextjs/types';

// GitLab Integration (Development & CI/CD)
export { 
  GitLabManager, 
  GitLabCallback, 
  GitLabDesktopManager 
} from './gitlab';
export * as GitLabTypes from './gitlab/types';
export { NextjsSkills } from './nextjs/skills/nextjsSkills';

// GitLab Integration
export { default as GitLabManager } from './gitlab/components/GitLabManager';
export { GitLabSkills } from './gitlab/skills/gitlabSkills';

// Base Integration Template
export * as BaseIntegration from './_template/baseIntegration';

// Integration Types
export type {
  AtomIntegrationBase,
  AtomIntegrationProps,
  AtomIntegrationState,
  AtomIntegrationAPI,
  AtomIntegrationHookReturn
} from './_template/baseIntegration';

// Configuration Types
export type {
  AtomFileStorageConfig,
  AtomMessagingConfig,
  AtomEmailConfig
} from './_template/baseIntegration';

// Integration Registry
export interface AtomIntegrationRegistry {
  register: (integration: any) => Promise<void>;
  get: (integrationId: string) => Promise<any>;
  list: () => Promise<any[]>;
  remove: (integrationId: string) => Promise<void>;
  update: (integrationId: string, integration: any) => Promise<void>;
}

// Integration Factory
export class AtomIntegrationFactory {
  static createDataSource(type: string, props: any) {
    switch (type) {
      case 'box':
        return ATOMBoxDataSource(props);
      case 'dropbox':
        return ATOMDropboxDataSource(props);
      case 'gdrive':
        return ATOMGDriveDataSource(props);
      case 'slack':
        return ATOMSlackDataSource(props);
      case 'gmail':
        return ATOMGmailDataSource(props);
      case 'notion':
        return ATOMNotionDataSource(props);
      case 'jira':
        return ATOMJiraDataSource(props);
      case 'github':
        return ATOMGitHubDataSource(props);
      case 'nextjs':
        return NextjsManager(props);
      case 'gitlab':
        return GitLabManager(props);
      default:
        throw new Error(`Unknown integration type: ${type}`);
    }
  }
  
  static getSupportedIntegrations(): string[] {
    return ['box', 'dropbox', 'gdrive', 'slack', 'gmail', 'notion', 'jira', 'github', 'nextjs', 'gitlab'];
  }
  
  static getIntegrationConfig(type: string): any {
    switch (type) {
      case 'box':
        return { name: 'Box', type: 'file-storage', category: 'storage', status: 'complete' };
      case 'dropbox':
        return { name: 'Dropbox', type: 'file-storage', category: 'storage', status: 'complete' };
      case 'gdrive':
        return { name: 'Google Drive', type: 'file-storage', category: 'storage', status: 'complete' };
      case 'slack':
        return { name: 'Slack', type: 'messaging', category: 'communication', status: 'complete' };
      case 'gmail':
        return { name: 'Gmail', type: 'email', category: 'communication', status: 'complete' };
      case 'notion':
        return { name: 'Notion', type: 'document', category: 'productivity', status: 'complete' };
      case 'jira':
        return { name: 'Jira', type: 'project-management', category: 'productivity', status: 'complete' };
      case 'github':
        return { name: 'GitHub', type: 'development', category: 'development', status: 'complete' };
      case 'nextjs':
        return { name: 'Next.js', type: 'development', category: 'development', status: 'complete' };
      case 'gitlab':
        return { name: 'GitLab', type: 'development', category: 'development', status: 'complete' };
      default:
        throw new Error(`Unknown integration type: ${type}`);
    }
  }
  
  static getIntegrationsByCategory(): Record<string, string[]> {
    return {
      storage: ['box', 'dropbox', 'gdrive'],
      communication: ['slack', 'gmail'],
      productivity: ['notion', 'jira'],
      development: ['github', 'nextjs', 'gitlab']
    };
  }
  
  static getCompletedIntegrations(): string[] {
    return ['box', 'dropbox', 'gdrive', 'slack', 'gmail', 'notion', 'jira', 'github', 'nextjs'];
  }
}

// Integration Utilities
export class AtomIntegrationUtils {
  static getOAuthUrl(type: string, clientId: string, redirectUri: string, scopes: string[]): string {
    switch (type) {
      case 'box':
        return `https://account.box.com/api/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${scopes.join(' ')}`;
      case 'dropbox':
        return `https://www.dropbox.com/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&token_access_type=offline`;
      case 'gdrive':
      case 'gmail':
        return `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${scopes.join(' ')}&access_type=offline`;
      case 'slack':
        return `https://slack.com/oauth/v2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scopes.join(' ')}&user_scope=`;
      case 'notion':
        return `https://api.notion.com/v1/oauth/authorize?client_id=${clientId}&response_type=code&redirect_uri=${redirectUri}&owner=user`;
      case 'jira':
        return `https://auth.atlassian.com/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${scopes.join(' ')}`;
      case 'github':
        return `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${scopes.join(' ')}`;
      case 'nextjs':
        return `https://vercel.com/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scopes.join(' ')}`;
      default:
        throw new Error(`Unknown integration type: ${type}`);
    }
  }
  
  static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
  
  static formatDate(date: Date | string): string {
    const d = new Date(date);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
  }
  
  static extractFileType(fileName: string): string {
    const parts = fileName.split('.');
    return parts.length > 1 ? parts.pop()!.toLowerCase() : '';
  }
  
  static isFileTypeSupported(fileName: string, supportedTypes: string[]): boolean {
    const extension = '.' + this.extractFileType(fileName);
    return supportedTypes.includes(extension);
  }
  
  static sanitizeFileName(fileName: string): string {
    return fileName.replace(/[^\w\s.-]/gi, '').trim();
  }
  
  static generateIntegrationId(type: string): string {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substr(2, 5);
    return `${type}-${timestamp}-${random}`;
  }
  
  static validateIntegrationConfig(type: string, config: any): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    switch (type) {
      case 'box':
      case 'dropbox':
      case 'gdrive':
        if (!config.supportedFileTypes) {
          errors.push('supportedFileTypes is required for file storage integrations');
        }
        if (!config.maxFileSize) {
          errors.push('maxFileSize is required for file storage integrations');
        }
        break;
      case 'slack':
        if (!config.channels && !config.dateRange) {
          errors.push('channels or dateRange is required for Slack integration');
        }
        break;
      case 'gmail':
        if (!config.folders && !config.dateRange) {
          errors.push('folders or dateRange is required for Gmail integration');
        }
        break;
      case 'notion':
        if (!config.extractBlockTypes) {
          errors.push('extractBlockTypes is required for Notion integration');
        }
        break;
      case 'jira':
        if (!config.includedProjects && !config.excludedProjects && !config.projectTypes) {
          errors.push('project filtering is required for Jira integration');
        }
        if (!config.jqlQuery && !config.includedProjects) {
          errors.push('JQL query or project filtering is required for Jira integration');
        }
        break;
      case 'github':
        if (!config.includedRepos && !config.excludedRepos && !config.repoLanguages) {
          errors.push('repository filtering is required for GitHub integration');
        }
        if (!config.personalAccessToken && !config.oauthToken) {
          errors.push('personal access token or OAuth token is required for GitHub integration');
        }
        break;
      case 'nextjs':
        if (!config.projects && !config.dateRange) {
          errors.push('projects or dateRange is required for Next.js integration');
        }
        if (!config.accessToken && !config.oauthToken) {
          errors.push('access token or OAuth token is required for Next.js integration');
        }
        break;
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }
}

// Integration Error Classes
export class AtomIntegrationError extends Error {
  public code: string;
  public context?: Record<string, any>;
  public integrationType?: string;

  constructor(message: string, code: string, context?: Record<string, any>, integrationType?: string) {
    super(message);
    this.name = 'AtomIntegrationError';
    this.code = code;
    this.context = context;
    this.integrationType = integrationType;
  }
}

export class AtomAuthenticationError extends AtomIntegrationError {
  constructor(message: string, integrationType?: string) {
    super(message, 'AUTH_ERROR', {}, integrationType);
    this.name = 'AtomAuthenticationError';
  }
}

export class AtomRateLimitError extends AtomIntegrationError {
  public retryAfter?: number;

  constructor(message: string, retryAfter?: number, integrationType?: string) {
    super(message, 'RATE_LIMIT_ERROR', { retryAfter }, integrationType);
    this.name = 'AtomRateLimitError';
    this.retryAfter = retryAfter;
  }
}

export class AtomPermissionError extends AtomIntegrationError {
  constructor(message: string, integrationType?: string) {
    super(message, 'PERMISSION_ERROR', {}, integrationType);
    this.name = 'AtomPermissionError';
  }
}

export class AtomConfigurationError extends AtomIntegrationError {
  constructor(message: string, integrationType?: string) {
    super(message, 'CONFIG_ERROR', {}, integrationType);
    this.name = 'AtomConfigurationError';
  }
}

// Integration Constants
export const ATOM_INTEGRATION_VERSION = '1.0.0';

export const ATOM_INTEGRATION_CATEGORIES = {
  STORAGE: 'storage',
  COMMUNICATION: 'communication',
  COLLABORATION: 'collaboration',
  PRODUCTIVITY: 'productivity',
  DEVELOPMENT: 'development'
} as const;

export const ATOM_INTEGRATION_STATUS = {
  COMPLETE: 'complete',
  TEMPLATE: 'template',
  IN_PROGRESS: 'in_progress',
  PLANNED: 'planned'
} as const;

export const ATOM_INTEGRATION_TYPES = {
  'file-storage': {
    integrations: ['box', 'dropbox', 'gdrive'],
    category: ATOM_INTEGRATION_CATEGORIES.STORAGE,
    status: ATOM_INTEGRATION_STATUS.COMPLETE,
    features: ['file_discovery', 'real_time_sync', 'metadata_extraction', 'preview_generation', 'batch_processing']
  },
  'messaging': {
    integrations: ['slack'],
    category: ATOM_INTEGRATION_CATEGORIES.COMMUNICATION,
    status: ATOM_INTEGRATION_STATUS.COMPLETE,
    features: ['message_discovery', 'real_time_events', 'thread_processing', 'attachment_processing', 'user_context']
  },
  'email': {
    integrations: ['gmail'],
    category: ATOM_INTEGRATION_CATEGORIES.COMMUNICATION,
    status: ATOM_INTEGRATION_STATUS.COMPLETE,
    features: ['email_discovery', 'thread_processing', 'attachment_processing', 'contact_extraction', 'header_extraction']
  },
  'document': {
    integrations: ['notion'],
    category: ATOM_INTEGRATION_CATEGORIES.PRODUCTIVITY,
    status: ATOM_INTEGRATION_STATUS.COMPLETE,
    features: ['page_discovery', 'real_time_sync', 'content_extraction', 'block_processing', 'database_query']
  },
  'project-management': {
    integrations: ['jira'],
    category: ATOM_INTEGRATION_CATEGORIES.PRODUCTIVITY,
    status: ATOM_INTEGRATION_STATUS.COMPLETE,
    features: ['issue_discovery', 'project_sync', 'comment_processing', 'attachment_processing', 'workflow_extraction']
  },
  'development': {
    integrations: ['github', 'nextjs'],
    category: ATOM_INTEGRATION_CATEGORIES.DEVELOPMENT,
    status: ATOM_INTEGRATION_STATUS.COMPLETE,
    features: ['repository_discovery', 'code_analysis', 'issue_tracking', 'pull_request_processing', 'commit_history', 'release_management', 'project_deployment', 'analytics_monitoring', 'build_tracking']
  },
  'deployment': {
    integrations: ['nextjs'],
    category: ATOM_INTEGRATION_CATEGORIES.DEVELOPMENT,
    status: ATOM_INTEGRATION_STATUS.COMPLETE,
    features: ['project_discovery', 'deployment_tracking', 'build_monitoring', 'analytics_integration', 'environment_management', 'health_monitoring']
  }
} as const;

// Integration Statistics
// Stats
export const ATOM_INTEGRATION_STATS = {
  totalIntegrations: 9,
  completedIntegrations: 9,
  templateIntegrations: 0,
  categories: {
    storage: 3,
    communication: 2,
    productivity: 2,
    development: 2,
    collaboration: 0
  },
  features: {
    file_discovery: 3,
    real_time_sync: 9,
    metadata_extraction: 9,
    preview_generation: 3,
    batch_processing: 9,
    message_discovery: 1,
    real_time_events: 1,
    thread_processing: 2,
    attachment_processing: 5,
    user_context: 1,
    email_discovery: 1,
    contact_extraction: 2,
    header_extraction: 1,
    page_discovery: 1,
    content_extraction: 1,
    block_processing: 1,
    database_query: 1,
    issue_discovery: 1,
    project_sync: 1,
    comment_processing: 3,
    workflow_extraction: 1,
    repository_discovery: 1,
    code_analysis: 1,
    issue_tracking: 1,
    pull_request_processing: 1,
    commit_history: 1,
    release_management: 1,
    project_deployment: 1,
    analytics_monitoring: 1,
    build_tracking: 1,
    environment_variable_management: 1,
    performance_optimization: 1,
    real_time_build_updates: 1,
    deployment_automation: 1,
    webhook_integration: 9
  }
} as const;

// Default Export
export default {
  // Components
  ATOMBoxManager,
  ATOMBoxDataSource,
  ATOMDropboxDataSource,
  ATOMGDriveDataSource,
  ATOMSlackDataSource,
  ATOMGmailDataSource,
  ATOMNotionDataSource,
  ATOMJiraManager,
  ATOMJiraDataSource,
  ATOMGitHubManager,
  ATOMGitHubDataSource,
  NextjsManager,
  NextjsCallback,
  NextjsDesktopManager,
  NextjsDesktopCallback,
  
  // Factory & Registry
  AtomIntegrationFactory,
  AtomIntegrationUtils,
  
  // Error Classes
  AtomIntegrationError,
  AtomAuthenticationError,
  AtomRateLimitError,
  AtomPermissionError,
  AtomConfigurationError,
  
  // Constants
  ATOM_INTEGRATION_VERSION,
  ATOM_INTEGRATION_CATEGORIES,
  ATOM_INTEGRATION_STATUS,
  ATOM_INTEGRATION_TYPES,
  ATOM_INTEGRATION_STATS
};