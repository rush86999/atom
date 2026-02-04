/**
 * Next.js Integration Index
 * Export all Next.js integration components and utilities
 */

// Components
export { NextjsCallback } from './components/NextjsCallback';
export { NextjsManager } from './components/NextjsManager';
export { NextjsDesktopCallback } from './components/NextjsDesktopCallback';
export { NextjsDesktopManager } from './components/NextjsDesktopManager';

// Skills
export { NextjsSkills, default as NextjsSkillsDefault } from './skills/nextjsSkills';

// Types
export type {
  NextjsProject,
  NextjsBuild,
  NextjsDeployment,
  NextjsAnalytics,
  NextjsEnvironmentVariable,
  NextjsWebhookEvent,
  NextjsConfig,
  NextjsIntegrationProps,
  NextjsDataSourceConfig,
  NextjsTeamMember,
} from './types';

// Utils for platform detection
export const detectNextjsPlatform = (): 'nextjs' | 'tauri' | 'web' => {
  if (typeof window !== 'undefined' && (window as any).__TAURI__) {
    return 'tauri';
  }
  if (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app')) {
    return 'nextjs';
  }
  return 'web';
};

// Constants
export const NEXTJS_INTEGRATION_ID = 'nextjs';
export const NEXTJS_PLATFORM = 'vercel';
export const NEXTJS_OAUTH_SCOPES = [
  'read',
  'write', 
  'projects',
  'deployments',
  'builds',
  'analytics'
];

// Default configuration
export const DEFAULT_NEXTJS_CONFIG = {
  platform: 'nextjs' as const,
  projects: [],
  deployments: [],
  builds: [],
  includeAnalytics: true,
  includeBuildLogs: true,
  includeEnvironmentVariables: false,
  realTimeSync: true,
  webhookEvents: ['deployment.created', 'deployment.ready', 'deployment.error', 'build.ready'],
  syncFrequency: 'realtime' as const,
  dateRange: {
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
    end: new Date(),
  },
  maxProjects: 50,
  maxBuilds: 100,
  enableNotifications: true,
  backgroundSync: true,
};