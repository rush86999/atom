/**
 * ATOM Integration Registry
 * Central registry for all ATOM integrations
 */

import {
  INTEGRATION_CATEGORY_STORAGE,
  INTEGRATION_CATEGORY_COMMUNICATION,
  INTEGRATION_CATEGORY_PRODUCTIVITY,
  INTEGRATION_CATEGORY_DEVELOPMENT,
  INTEGRATION_CATEGORY_COLLABORATION,
  INTEGRATION_CATEGORY_MARKETING,
  INTEGRATION_CATEGORY_CUSTOMER_SERVICE
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
  },
  {
    id: 'discord',
    name: 'Discord',
    description: 'Communication platform for communities and teams',
    category: INTEGRATION_CATEGORY_COMMUNICATION,
    platform: 'web',
    status: 'complete',
    features: [
      'server_management',
      'channel_management',
      'message_sending',
      'user_authentication',
      'bot_integration',
      'voice_channels',
      'role_management',
      'webhook_support',
      'api_access'
    ],
    oauth: {
      provider: 'discord',
      scopes: ['bot', 'identify', 'guilds', 'messages.read'],
      flow: 'oauth2'
    },
    webhooks: [
      'message.create',
      'message.update',
      'message.delete',
      'guild.member.add',
      'guild.member.remove',
      'channel.create',
      'channel.update',
      'channel.delete'
    ],
    limits: {
      max_guilds: 100,
      max_channels_per_guild: 500,
      max_members_per_guild: 250000,
      api_calls_per_second: 50,
      api_calls_per_minute: 1200
    }
  },
  // Development Tools Integrations
  {
    id: 'linear',
    name: 'Linear',
    description: 'Modern issue tracking and project management for software development teams',
    category: INTEGRATION_CATEGORY_DEVELOPMENT,
    platform: 'web',
    status: 'complete',
    features: [
      'issue_tracking',
      'project_management',
      'team_collaboration',
      'issue_assignment',
      'status_tracking',
      'priority_management',
      'milestone_tracking',
      'time_tracking',
      'issue_comments',
      'attachments',
      'labels',
      'milestones',
      'release_tracking',
      'automations',
      'webhooks',
      'api_access',
      'real_time_updates',
      'issue_templates',
      'custom_fields',
      'issue_history',
      'search_filtering',
      'bulk_operations',
      'reporting',
      'team_dashboards',
      'productivity_metrics',
      'integration_apis'
    ],
    oauth: {
      provider: 'linear',
      scopes: [
        'read',
        'write',
        'issues:read',
        'issues:write',
        'projects:read',
        'projects:write',
        'teams:read',
        'teams:write',
        'users:read',
        'labels:read',
        'labels:write',
        'webhooks:read',
        'webhooks:write'
      ],
      flow: 'oauth2'
    },
    webhooks: [
      'Issue.created',
      'Issue.updated',
      'Issue.removed',
      'Issue.completed',
      'Issue.archived',
      'Issue.reopened',
      'Issue.status_changed',
      'Issue.assignee_changed',
      'Issue.priority_changed',
      'Issue.title_changed',
      'Issue.description_changed',
      'Issue.comment_created',
      'Issue.comment_updated',
      'Issue.attachment_created',
      'Project.created',
      'Project.updated',
      'Project.removed',
      'Team.created',
      'Team.updated',
      'Team.member_added',
      'Team.member_removed',
      'User.created',
      'User.updated',
      'Label.created',
      'Label.updated',
      'Label.removed',
      'Milestone.created',
      'Milestone.updated',
      'Milestone.completed'
    ],
    limits: {
      max_issues_per_project: 100000,
      max_projects_per_team: 1000,
      max_teams_per_workspace: 100,
      max_users_per_workspace: 5000,
      max_webhooks_per_workspace: 100,
      api_calls_per_minute: 1000,
      api_calls_per_hour: 60000,
      attachment_size_mb: 10,
      max_attachments_per_issue: 100
    }
  },
  // Project Management & Productivity Integrations
  {
    id: 'asana',
    name: 'Asana',
    description: 'Work management and project coordination platform for teams',
    category: INTEGRATION_CATEGORY_PRODUCTIVITY,
    platform: 'web',
    status: 'complete',
    features: [
      'task_management',
      'project_tracking',
      'team_coordination',
      'workflow_automation',
      'deadline_monitoring',
      'dependency_tracking',
      'collaboration_tools',
      'file_attachments',
      'comment_threads',
      'status_updates',
      'milestone_tracking',
      'resource_allocation',
      'progress_tracking',
      'team_assignments',
      'task_dependencies',
      'project_templates',
      'time_tracking',
      'workload_management',
      'integrations',
      'api_access',
      'real_time_updates',
      'custom_fields',
      'advanced_search',
      'reporting',
      'dashboard_analytics'
    ],
    oauth: {
      provider: 'asana',
      scopes: [
        'default',
        'tasks:read',
        'tasks:write',
        'projects:read',
        'projects:write',
        'teams:read',
        'stories:read',
        'stories:write',
        'attachments:read',
        'attachments:write',
        'events:read',
        'goals:read',
        'goals:write',
        'portfolio:read',
        'portfolio:write'
      ],
      flow: 'oauth2'
    },
    webhooks: [
      'Task.created',
      'Task.updated',
      'Task.completed',
      'Task.removed',
      'Task.assigned',
      'Task.unassigned',
      'Task.dependency_added',
      'Task.dependency_removed',
      'Task.status_changed',
      'Task.due_date_changed',
      'Task.priority_changed',
      'Task.project_changed',
      'Task.tags_changed',
      'Task.custom_fields_changed',
      'Story.created',
      'Story.updated',
      'Story.removed',
      'Story.attachment_added',
      'Story.attachment_removed',
      'Project.created',
      'Project.updated',
      'Project.removed',
      'Project.status_changed',
      'Project.archived',
      'Project.team_changed',
      'Team.added',
      'Team.removed',
      'Team.updated',
      'Team.name_changed',
      'Goal.created',
      'Goal.updated',
      'Goal.completed',
      'Goal.progress_changed',
      'Portfolio.created',
      'Portfolio.updated',
      'Portfolio.item_added',
      'Portfolio.item_removed'
    ],
    limits: {
      max_tasks_per_project: 100000,
      max_projects: 10000,
      max_teams: 1000,
      max_users_per_team: 10000,
      max_attachments_per_task: 100,
      max_comments_per_task: 1000,
      api_calls_per_minute: 1500,
      api_calls_per_hour: 60000,
      webhook_events_per_minute: 1000,
      attachment_size_mb: 100,
      max_custom_fields: 100
    }
  },
  // Financial & Accounting Integrations
  {
    id: 'xero',
    name: 'Xero',
    description: 'Complete small business accounting and financial management platform',
    category: INTEGRATION_CATEGORY_FINANCIAL,
    platform: 'web',
    status: 'complete',
    features: [
      'invoice_management',
      'contact_management',
      'bank_reconciliation',
      'financial_reporting',
      'expense_tracking',
      'tax_management',
      'payment_processing',
      'budget_tracking',
      'cash_flow_management',
      'multi_currency_support',
      'bank_feeds',
      'reconciliation_automation',
      'inventory_tracking',
      'payroll_management',
      'project_accounting',
      'time_tracking',
      'fixed_assets',
      'bill_management',
      'quoting',
      'mobile_access',
      'api_integration',
      'webhook_support',
      'multi_organization',
      'audit_trails',
      'compliance_reporting'
    ],
    oauth: {
      provider: 'xero',
      scopes: [
        'openid',
        'profile',
        'email',
        'accounting.settings',
        'accounting.transactions',
        'accounting.reports.read',
        'accounting.journals.read',
        'accounting.contacts',
        'accounting.attachments',
        'accounting.budgets.read',
        'offline_access'
      ],
      flow: 'oauth2'
    },
    webhooks: [
      'Invoice.Created',
      'Invoice.Updated',
      'Invoice.Paid',
      'Invoice.Voided',
      'Invoice.Deleted',
      'Contact.Created',
      'Contact.Updated',
      'Contact.Deleted',
      'BankTransaction.Created',
      'BankTransaction.Updated',
      'BankTransaction.Deleted',
      'Payment.Created',
      'Payment.Updated',
      'Payment.Deleted',
      'Expense.Claim.Created',
      'Expense.Claim.Updated',
      'Expense.Claim.Approved',
      'Expense.Claim.Paid',
      'Journal.Created',
      'Journal.Updated',
      'Journal.Posted',
      'ManualJournal.Created',
      'ManualJournal.Updated',
      'ManualJournal.Posted',
      'Item.Created',
      'Item.Updated',
      'Item.Deleted',
      'PurchaseOrder.Created',
      'PurchaseOrder.Updated',
      'PurchaseOrder.Approved',
      'PurchaseOrder.EmailSent'
    ],
    limits: {
      max_invoices_per_month: 10000,
      max_contacts: 10000,
      max_bank_accounts: 100,
      max_transactions_per_day: 5000,
      max_reports_per_month: 1000,
      max_users: 100,
      api_calls_per_day: 5000,
      api_calls_per_minute: 60,
      attachment_size_mb: 25,
      max_attachments_per_entity: 100
    }
  },
  // Customer Service Integrations
  {
    id: 'zendesk',
    name: 'Zendesk',
    description: 'Complete customer support and ticketing management platform',
    category: INTEGRATION_CATEGORY_CUSTOMER_SERVICE,
    platform: 'web',
    status: 'complete',
    features: [
      'ticket_management',
      'customer_support',
      'user_management',
      'group_management',
      'organization_management',
      'knowledge_base',
      'automation',
      'ai_insights',
      'sentiment_analysis',
      'ticket_routing',
      'satisfaction_tracking',
      'multi_channel_support',
      'real_time_chat',
      'phone_integration',
      'email_integration',
      'social_integration',
      'self_service_portal',
      'community_forum',
      'help_center',
      'sla_management',
      'reporting_analytics',
      'custom_fields',
      'macros',
      'triggers',
      'automations',
      'multi_brand_support',
      'sdk_integration',
      'webhook_support'
    ],
    oauth: {
      provider: 'zendesk',
      scopes: [
        'tickets:read',
        'tickets:write',
        'users:read',
        'users:write',
        'organizations:read',
        'organizations:write',
        'groups:read',
        'groups:write',
        'macros:read',
        'automations:read',
        'triggers:read',
        'satisfaction:read',
        'forums:read',
        'topics:read',
        'posts:read',
        'articles:read',
        'webhooks:read',
        'webhooks:write'
      ],
      flow: 'oauth2'
    },
    webhooks: [
      'ticket.created',
      'ticket.updated',
      'ticket.deleted',
      'ticket.merged',
      'ticket.changed',
      'comment.created',
      'comment.updated',
      'comment.deleted',
      'user.created',
      'user.updated',
      'user.deleted',
      'organization.created',
      'organization.updated',
      'organization.deleted',
      'group.created',
      'group.updated',
      'group.deleted',
      'satisfaction.created',
      'satisfaction.updated',
      'voice-call.started',
      'voice-call.completed',
      'voice-call.missed',
      'chat.conversation.started',
      'chat.conversation.updated',
      'chat.conversation.ended',
      'macro.applied',
      'automation.applied',
      'trigger.applied'
    ],
    limits: {
      max_tickets: 5000000,
      max_users: 1000000,
      max_groups: 10000,
      max_organizations: 1000000,
      max_articles: 100000,
      max_webhooks: 100,
      api_calls_per_minute: 700,
      api_calls_per_hour: 42000,
      upload_size_mb: 50
    }
  },
  // Marketing & CRM Integrations
  {
    id: 'hubspot',
    name: 'HubSpot',
    description: 'Complete CRM, marketing, and sales automation platform',
    category: INTEGRATION_CATEGORY_MARKETING,
    platform: 'web',
    status: 'complete',
    features: [
      'contact_management',
      'company_management',
      'deal_pipeline',
      'marketing_automation',
      'email_campaigns',
      'lead_scoring',
      'analytics_reporting',
      'sales_forecasting',
      'ai_insights',
      'workflow_automation',
      'ticket_management',
      'live_chat',
      'social_media_integration',
      'landing_pages',
      'forms',
      'call_tracking',
      'meeting_scheduling'
    ],
    oauth: {
      provider: 'hubspot',
      scopes: [
        'contacts',
        'companies',
        'deals',
        'marketing',
        'sales',
        'tickets',
        'automation',
        'integration-bridge',
        'e-commerce',
        'settings',
        'analytics',
        'business-intelligence'
      ],
      flow: 'oauth2'
    },
    webhooks: [
      'contact.creation',
      'contact.deletion',
      'contact.propertyChange',
      'company.creation',
      'company.deletion',
      'company.propertyChange',
      'deal.creation',
      'deal.deletion',
      'deal.propertyChange',
      'ticket.creation',
      'ticket.deletion',
      'ticket.propertyChange',
      'marketing.email',
      'subscription.change'
    ],
    limits: {
      max_contacts: 1000000,
      max_companies: 100000,
      max_deals: 500000,
      max_tickets: 1000000,
      api_calls_per_10_seconds: 100,
      api_calls_per_day: 250000
    }
  },
  zendesk: {
    name: 'Zendesk',
    auth_url: 'https://{subdomain}.zendesk.com/oauth/authorizations/new',
    token_url: 'https://{subdomain}.zendesk.com/oauth/tokens',
    scopes: [
      'tickets:read',
      'tickets:write',
      'users:read',
      'users:write',
      'organizations:read',
      'organizations:write',
      'groups:read',
      'groups:write',
      'macros:read',
      'automations:read',
      'triggers:read',
      'satisfaction:read',
      'forums:read',
      'topics:read',
      'posts:read',
      'articles:read',
      'webhooks:read',
      'webhooks:write'
    ]
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
  },
  hubspot: {
    name: 'HubSpot',
    auth_url: 'https://app.hubspot.com/oauth/authorize',
    token_url: 'https://api.hubapi.com/oauth/v1/token',
    scopes: [
      'contacts',
      'companies', 
      'deals',
      'marketing',
      'sales',
      'tickets',
      'automation',
      'integration-bridge',
      'e-commerce',
      'settings',
      'analytics',
      'business-intelligence'
    ]
  },
  linear: {
    name: 'Linear',
    auth_url: 'https://linear.app/oauth/authorize',
    token_url: 'https://api.linear.app/graphql',
    scopes: [
      'read',
      'write',
      'issues:read',
      'issues:write',
      'projects:read',
      'projects:write',
      'teams:read',
      'teams:write',
      'users:read',
      'labels:read',
      'labels:write',
      'webhooks:read',
      'webhooks:write'
    ]
  },
  xero: {
    name: 'Xero',
    auth_url: 'https://login.xero.com/identity/connect/authorize',
    token_url: 'https://identity.xero.com/connect/token',
    scopes: [
      'openid',
      'profile',
      'email',
      'accounting.settings',
      'accounting.transactions',
      'accounting.reports.read',
      'accounting.journals.read',
      'accounting.contacts',
      'accounting.attachments',
      'accounting.budgets.read',
      'offline_access'
    ]
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
    'issue.closed',
    'issue.assigned',
    'issue.unassigned',
    'issue.priority_changed',
    'issue.label_added',
    'issue.label_removed'
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
  ],
  ticket: [
    'ticket.created',
    'ticket.updated',
    'ticket.deleted',
    'ticket.merged',
    'ticket.changed',
    'ticket.assigned',
    'ticket.unassigned'
  ],
  contact: [
    'contact.creation',
    'contact.deletion',
    'contact.propertyChange'
  ],
  company: [
    'company.creation',
    'company.deletion',
    'company.propertyChange'
  ],
  deal: [
    'deal.creation',
    'deal.deletion',
    'deal.propertyChange'
  ],
  organization: [
    'organization.created',
    'organization.updated',
    'organization.deleted'
  ],
  user: [
    'user.created',
    'user.updated',
    'user.deleted'
  ],
  group: [
    'group.created',
    'group.updated',
    'group.deleted'
  ],
  comment: [
    'comment.created',
    'comment.updated',
    'comment.deleted'
  ],
  satisfaction: [
    'satisfaction.created',
    'satisfaction.updated'
  ],
  voice_call: [
    'voice-call.started',
    'voice-call.completed',
    'voice-call.missed'
  ],
  chat_conversation: [
    'chat.conversation.started',
    'chat.conversation.updated',
    'chat.conversation.ended'
  ],
  financial: [
    'invoice.created',
    'invoice.updated',
    'invoice.paid',
    'invoice.voided',
    'invoice.deleted',
    'contact.created',
    'contact.updated',
    'contact.deleted',
    'bank_transaction.created',
    'bank_transaction.updated',
    'bank_transaction.deleted',
    'payment.created',
    'payment.updated',
    'payment.deleted',
    'expense_claim.created',
    'expense_claim.updated',
    'expense_claim.approved',
    'expense_claim.paid',
    'journal.created',
    'journal.updated',
    'journal.posted'
  ],
  marketing: [
    'marketing.email',
    'marketing.email.sent',
    'subscription.change',
    'campaign.created',
    'campaign.updated'
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