/**
 * ATOM Integration Registry
 * Central registry for all ATOM integrations
 */

import {
  INTEGRATION_CATEGORY_STORAGE,
  INTEGRATION_CATEGORY_COMMUNICATION,
  INTEGRATION_CATEGORY_PRODUCTIVITY,
  INTEGRATION_CATEGORY_DEVELOPMENT,
  INTEGRATION_CATEGORY_COLLABORATION
} from './constants';

// Integration Registry
export const ATOM_INTEGRATIONS = [
  // File Storage Integrations
  {
    id: 'box',
    name: 'Box',
    description: 'Secure file storage and collaboration platform',
    category: INTEGRATION_CATEGORY_STORAGE,
    platform: 'web',
    status: 'complete',
    features: [
      'file_discovery',
      'real_time_sync',
      'metadata_extraction',
      'batch_processing',
      'preview_generation'
    ],
    oauth: {
      provider: 'box',
      scopes: ['read', 'write', 'manage'],
      flow: 'oauth2'
    },
    webhooks: [
      'file.created',
      'file.updated',
      'file.deleted',
      'folder.created',
      'folder.updated'
    ],
    limits: {
      max_files: 10000,
      max_size_per_file: '5GB',
      api_calls_per_hour: 1000
    }
  },
  {
    id: 'dropbox',
    name: 'Dropbox',
    description: 'Cloud storage and file sharing platform',
    category: INTEGRATION_CATEGORY_STORAGE,
    platform: 'web',
    status: 'complete',
    features: [
      'file_discovery',
      'real_time_sync',
      'metadata_extraction',
      'batch_processing',
      'preview_generation'
    ],
    oauth: {
      provider: 'dropbox',
      scopes: ['files.metadata.read', 'files.content.read', 'files.content.write'],
      flow: 'oauth2'
    },
    webhooks: [
      'file.added',
      'file.updated',
      'file.deleted',
      'folder.added'
    ],
    limits: {
      max_files: 10000,
      max_size_per_file: '2GB',
      api_calls_per_hour: 1600
    }
  },
  {
    id: 'gdrive',
    name: 'Google Drive',
    description: 'Cloud storage and document management platform',
    category: INTEGRATION_CATEGORY_STORAGE,
    platform: 'web',
    status: 'complete',
    features: [
      'file_discovery',
      'real_time_sync',
      'metadata_extraction',
      'batch_processing',
      'preview_generation'
    ],
    oauth: {
      provider: 'google',
      scopes: ['https://www.googleapis.com/auth/drive'],
      flow: 'oauth2'
    },
    webhooks: [
      'files.create',
      'files.update',
      'files.delete'
    ],
    limits: {
      max_files: 10000,
      max_size_per_file: '100GB',
      api_calls_per_hour: 10000
    }
  },
  // Communication Integrations
  {
    id: 'slack',
    name: 'Slack',
    description: 'Team communication and collaboration platform',
    category: INTEGRATION_CATEGORY_COMMUNICATION,
    platform: 'web',
    status: 'complete',
    features: [
      'message_discovery',
      'real_time_events',
      'thread_processing',
      'attachment_processing',
      'user_context'
    ],
    oauth: {
      provider: 'slack',
      scopes: ['channels:read', 'channels:history', 'users:read', 'files:read'],
      flow: 'oauth2'
    },
    webhooks: [
      'message.channels',
      'message.private',
      'file.shared',
      'user.typing'
    ],
    limits: {
      max_messages: 50000,
      max_channels: 1000,
      api_calls_per_minute: 20
    }
  },
  {
    id: 'gmail',
    name: 'Gmail',
    description: 'Email communication and organization platform',
    category: INTEGRATION_CATEGORY_COMMUNICATION,
    platform: 'web',
    status: 'complete',
    features: [
      'email_discovery',
      'contact_extraction',
      'header_extraction',
      'attachment_processing',
      'batch_processing'
    ],
    oauth: {
      provider: 'google',
      scopes: ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send'],
      flow: 'oauth2'
    },
    webhooks: [
      'message.added',
      'message.updated',
      'label.created'
    ],
    limits: {
      max_emails: 50000,
      max_attachments: 10000,
      api_calls_per_day: 1000000
    }
  },
  // Productivity Integrations
  {
    id: 'notion',
    name: 'Notion',
    description: 'Document management and knowledge base platform',
    category: INTEGRATION_CATEGORY_PRODUCTIVITY,
    platform: 'web',
    status: 'complete',
    features: [
      'page_discovery',
      'content_extraction',
      'block_processing',
      'database_query',
      'real_time_sync'
    ],
    oauth: {
      provider: 'notion',
      scopes: ['read_content', 'read_workspace'],
      flow: 'oauth2'
    },
    webhooks: [
      'page.created',
      'page.updated',
      'database.created',
      'database.rows.created'
    ],
    limits: {
      max_pages: 10000,
      max_blocks: 100000,
      api_calls_per_minute: 20
    }
  },
  {
    id: 'jira',
    name: 'Jira',
    description: 'Project management and issue tracking platform',
    category: INTEGRATION_CATEGORY_PRODUCTIVITY,
    platform: 'web',
    status: 'complete',
    features: [
      'issue_discovery',
      'project_sync',
      'comment_processing',
      'workflow_extraction',
      'real_time_events'
    ],
    oauth: {
      provider: 'atlassian',
      scopes: ['read:jira-work', 'read:jira-user'],
      flow: 'oauth2'
    },
    webhooks: [
      'issue.created',
      'issue.updated',
      'project.updated',
      'sprint.created'
    ],
    limits: {
      max_issues: 50000,
      max_projects: 1000,
      api_calls_per_hour: 1000
    }
  },
  // Development Integrations
  {
    id: 'github',
    name: 'GitHub',
    description: 'Code repository and development platform',
    category: INTEGRATION_CATEGORY_DEVELOPMENT,
    platform: 'web',
    status: 'complete',
    features: [
      'repository_discovery',
      'code_analysis',
      'issue_tracking',
      'pull_request_processing',
      'commit_history',
      'release_management'
    ],
    oauth: {
      provider: 'github',
      scopes: ['repo', 'read:user', 'read:org'],
      flow: 'oauth2'
    },
    webhooks: [
      'push',
      'pull_request',
      'issues',
      'release'
    ],
    limits: {
      max_repos: 1000,
      max_commits: 100000,
      api_calls_per_hour: 5000
    }
  },
  {
    id: 'nextjs',
    name: 'Next.js',
    description: 'Vercel project management and deployment platform',
    category: INTEGRATION_CATEGORY_DEVELOPMENT,
    platform: 'web',
    status: 'complete',
    features: [
      'project_discovery',
      'deployment_tracking',
      'build_monitoring',
      'analytics_integration',
      'environment_variable_management',
      'real_time_build_updates',
      'deployment_automation',
      'performance_optimization',
      'webhook_integration'
    ],
    oauth: {
      provider: 'vercel',
      scopes: ['read', 'write', 'projects', 'deployments', 'builds'],
      flow: 'oauth2'
    },
    webhooks: [
      'deployment.created',
      'deployment.ready',
      'deployment.error',
      'build.created',
      'build.ready',
      'build.error'
    ],
    limits: {
      max_projects: 1000,
      max_deployments: 10000,
      max_builds: 50000,
      api_calls_per_hour: 1000
    }
  }
];

// Integration Category Mapping
export const INTEGRATIONS_BY_CATEGORY = ATOM_INTEGRATIONS.reduce((acc, integration) => {
  if (!acc[integration.category]) {
    acc[integration.category] = [];
  }
  acc[integration.category].push(integration);
  return acc;
}, {} as Record<string, typeof ATOM_INTEGRATIONS>);

// Platform Support
export const PLATFORMS = ['web', 'tauri', 'nextjs'] as const;

// Integration Status
export const INTEGRATION_STATUS = {
  complete: {
    label: 'Complete',
    color: 'green',
    description: 'Fully implemented and production ready'
  },
  in_progress: {
    label: 'In Progress',
    color: 'yellow',
    description: 'Currently under development'
  },
  planned: {
    label: 'Planned',
    color: 'gray',
    description: 'Scheduled for future development'
  }
} as const;

// OAuth Providers
export const OAUTH_PROVIDERS = {
  box: {
    name: 'Box',
    auth_url: 'https://account.box.com/api/oauth2/authorize',
    token_url: 'https://api.box.com/oauth2/token',
    scopes: ['read', 'write', 'manage']
  },
  dropbox: {
    name: 'Dropbox',
    auth_url: 'https://www.dropbox.com/oauth2/authorize',
    token_url: 'https://api.dropboxapi.com/oauth2/token',
    scopes: ['files.metadata.read', 'files.content.read', 'files.content.write']
  },
  google: {
    name: 'Google',
    auth_url: 'https://accounts.google.com/o/oauth2/v2/auth',
    token_url: 'https://oauth2.googleapis.com/token',
    scopes: ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/gmail.readonly']
  },
  slack: {
    name: 'Slack',
    auth_url: 'https://slack.com/oauth/v2/authorize',
    token_url: 'https://slack.com/api/oauth.v2.access',
    scopes: ['channels:read', 'channels:history', 'users:read', 'files:read']
  },
  notion: {
    name: 'Notion',
    auth_url: 'https://api.notion.com/v1/oauth/authorize',
    token_url: 'https://api.notion.com/v1/oauth/token',
    scopes: ['read_content', 'read_workspace']
  },
  atlassian: {
    name: 'Atlassian',
    auth_url: 'https://auth.atlassian.com/authorize',
    token_url: 'https://auth.atlassian.com/oauth/token',
    scopes: ['read:jira-work', 'read:jira-user']
  },
  github: {
    name: 'GitHub',
    auth_url: 'https://github.com/login/oauth/authorize',
    token_url: 'https://github.com/login/oauth/access_token',
    scopes: ['repo', 'read:user', 'read:org']
  },
  vercel: {
    name: 'Vercel',
    auth_url: 'https://vercel.com/oauth/authorize',
    token_url: 'https://api.vercel.com/v2/oauth/access_token',
    scopes: ['read', 'write', 'projects', 'deployments', 'builds']
  }
} as const;

// Webhook Event Types
export const WEBHOOK_EVENTS = {
  file: [
    'file.created',
    'file.updated',
    'file.deleted',
    'file.added'
  ],
  message: [
    'message.channels',
    'message.private',
    'message.added',
    'message.updated'
  ],
  project: [
    'project.created',
    'project.updated',
    'project.synced'
  ],
  deployment: [
    'deployment.created',
    'deployment.ready',
    'deployment.error',
    'deployment.updated'
  ],
  build: [
    'build.created',
    'build.ready',
    'build.error',
    'build.updated'
  ],
  issue: [
    'issue.created',
    'issue.updated',
    'issue.opened',
    'issue.closed'
  ],
  page: [
    'page.created',
    'page.updated',
    'page.deleted'
  ],
  pull_request: [
    'pull_request.opened',
    'pull_request.closed',
    'pull_request.updated'
  ]
} as const;

// Integration Utilities
export const INTEGRATION_UTILS = {
  // Get integration by ID
  getById: (id: string) => {
    return ATOM_INTEGRATIONS.find(integration => integration.id === id);
  },
  
  // Get integrations by category
  getByCategory: (category: string) => {
    return ATOM_INTEGRATIONS.filter(integration => integration.category === category);
  },
  
  // Get integrations by status
  getByStatus: (status: string) => {
    return ATOM_INTEGRATIONS.filter(integration => integration.status === status);
  },
  
  // Get integrations by platform
  getByPlatform: (platform: string) => {
    return ATOM_INTEGRATIONS.filter(integration => 
      integration.platform === platform || integration.platform === 'web'
    );
  },
  
  // Get OAuth provider
  getOAuthProvider: (provider: string) => {
    return OAUTH_PROVIDERS[provider as keyof typeof OAUTH_PROVIDERS];
  },
  
  // Check if webhook is supported
  isWebhookSupported: (integrationId: string, event: string) => {
    const integration = INTEGRATION_UTILS.getById(integrationId);
    return integration?.webhooks?.includes(event) || false;
  },
  
  // Get integration limits
  getLimits: (integrationId: string) => {
    const integration = INTEGRATION_UTILS.getById(integrationId);
    return integration?.limits || {};
  },
  
  // Get total integrations count
  getTotalCount: () => ATOM_INTEGRATIONS.length,
  
  // Get completed integrations count
  getCompletedCount: () => ATOM_INTEGRATIONS.filter(i => i.status === 'complete').length,
  
  // Get categories with integrations
  getCategoriesWithIntegrations: () => {
    const categories = new Set(ATOM_INTEGRATIONS.map(i => i.category));
    return Array.from(categories);
  },
  
  // Get available features across all integrations
  getAvailableFeatures: () => {
    const features = new Set();
    ATOM_INTEGRATIONS.forEach(integration => {
      integration.features.forEach(feature => features.add(feature));
    });
    return Array.from(features);
  }
};

// Export default registry
export default INTEGRATION_UTILS;