/**
 * Microsoft Teams Integration Main Index
 * Exports all Teams integration components, types, and utilities
 */

// Components
export { default as TeamsManager } from './components/TeamsManager';
export { default as EnhancedTeamsManager } from './components/EnhancedTeamsManager';
export { default as TeamsCallback } from './components/TeamsCallback';
export { default as TeamsDataSource } from './components/TeamsDataSource';

// Skills
export { teamsSkills } from './skills/teamsSkills';

// Types
export * from './types';

// Utilities
export * from './utils';

// Integration configuration
export const TEAMS_INTEGRATION_CONFIG = {
  name: 'Microsoft Teams',
  platform: 'teams',
  version: '1.0.0',
  description: 'Microsoft Teams integration for ATOM',
  scopes: [
    'https://graph.microsoft.com/Team.ReadBasic.All',
    'https://graph.microsoft.com/Channel.ReadBasic.All',
    'https://graph.microsoft.com/ChannelMessage.Read',
    'https://graph.microsoft.com/ChannelMessage.Send',
    'https://graph.microsoft.com/Chat.Read',
    'https://graph.microsoft.com/Chat.ReadWrite',
    'https://graph.microsoft.com/User.Read',
    'https://graph.microsoft.com/offline_access'
  ],
  redirectUri: 'http://localhost:3000/oauth/teams/callback',
  endpoints: {
    authorize: '/api/auth/teams/authorize',
    callback: '/api/auth/teams/callback',
    status: '/api/auth/teams/status',
    disconnect: '/api/auth/teams/disconnect',
    health: '/api/integrations/teams/health',
    sync: '/api/integrations/teams/sync',
    teams: '/api/integrations/teams/teams',
    channels: '/api/integrations/teams/channels',
    messages: '/api/integrations/teams/messages',
    chat: '/api/integrations/teams/chat'
  }
};

export default TEAMS_INTEGRATION_CONFIG;
