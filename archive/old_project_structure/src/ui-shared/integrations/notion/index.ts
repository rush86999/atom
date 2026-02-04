/**
 * Notion Integration Main Index
 * Exports all Notion integration components, types, and utilities
 */

// Components
export { NotionManager, NotionCallback, NotionDataSource } from './components';

// Skills
export { notionSkills } from './skills/notionSkills';

// Types
export * from './types';

// Utilities
export * from './utils';

// Integration configuration
export const NOTION_INTEGRATION_CONFIG = {
  name: 'Notion',
  platform: 'notion',
  version: '1.0.0',
  description: 'Notion workspace integration for ATOM',
  scopes: ['read:page', 'read:database', 'write:page', 'write:database'],
  redirectUri: 'http://localhost:3000/oauth/notion/callback',
  endpoints: {
    authorize: '/api/auth/notion/authorize',
    callback: '/api/auth/notion/callback',
    status: '/api/auth/notion/status',
    disconnect: '/api/auth/notion/disconnect',
    health: '/api/integrations/notion/health',
    sync: '/api/integrations/notion/sync',
    search: '/api/integrations/notion/search',
    workspaces: '/api/integrations/notion/workspaces',
    pages: '/api/integrations/notion/pages',
    databases: '/api/integrations/notion/databases'
  }
};

export default NOTION_INTEGRATION_CONFIG;
