/**
 * Microsoft Teams Integration Skills
 * Natural language commands for Teams operations
 */

import { 
  TeamsTeam,
  TeamsChannel,
  TeamsMessage,
  TeamsUser,
  TeamsFile,
  TeamsMeeting
} from '../types/teams-types';

export interface TeamsSkillResult {
  success: boolean;
  data?: any;
  error?: string;
  action: string;
  platform: 'teams';
}

export class TeamsSkills {
  private userId: string;
  private baseUrl: string;

  constructor(userId: string = 'default-user', baseUrl: string = '') {
    this.userId = userId;
    this.baseUrl = baseUrl;
  }

  /**
   * Execute natural language Teams command
   */
  async executeCommand(command: string, context?: any): Promise<TeamsSkillResult> {
    const lowerCommand = command.toLowerCase().trim();

    try {
      // Team commands
      if (lowerCommand.includes('team')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listTeams(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchTeams(lowerCommand, context);
        }
        if (lowerCommand.includes('members')) {
          return await this.getTeamMembers(lowerCommand, context);
        }
      }

      // Channel commands
      if (lowerCommand.includes('channel')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listChannels(lowerCommand, context);
        }
        if (lowerCommand.includes('messages')) {
          return await this.getChannelMessages(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createChannel(lowerCommand, context);
        }
      }

      // Message commands
      if (lowerCommand.includes('message') || lowerCommand.includes('chat')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listMessages(lowerCommand, context);
        }
        if (lowerCommand.includes('send')) {
          return await this.sendMessage(lowerCommand, context);
        }
        if (lowerCommand.includes('reply')) {
          return await this.replyToMessage(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchMessages(lowerCommand, context);
        }
      }

      // User commands
      if (lowerCommand.includes('user') || lowerCommand.includes('profile')) {
        return await this.getUserProfile(lowerCommand, context);
      }

      // Meeting commands
      if (lowerCommand.includes('meeting')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listMeetings(lowerCommand, context);
        }
        if (lowerCommand.includes('schedule')) {
          return await this.scheduleMeeting(lowerCommand, context);
        }
      }

      // File commands
      if (lowerCommand.includes('file') || lowerCommand.includes('document')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listFiles(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchFiles(lowerCommand, context);
        }
      }

      // Default: Search across Teams
      return await this.searchTeams(lowerCommand, context);

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        action: 'execute_command',
        platform: 'teams'
      };
    }
  }

  /**
   * List teams
   */
  private async listTeams(command: string, context?: any): Promise<TeamsSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/teams/teams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          include_private: command.includes('private'),
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        const teams = data.teams;
        const summary = this.generateTeamsSummary(teams);
        
        return {
          success: true,
          data: {
            teams,
            summary,
            total: data.total_count
          },
          action: 'list_teams',
          platform: 'teams'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list teams',
        action: 'list_teams',
        platform: 'teams'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_teams',
        platform: 'teams'
      };
    }
  }

  /**
   * Search teams
   */
  private async searchTeams(command: string, context?: any): Promise<TeamsSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search teams project"',
          action: 'search_teams',
          platform: 'teams'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/teams/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'teams',
          limit: this.extractLimit(command) || 20
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            teams: data.teams,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'search_teams',
          platform: 'teams'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search teams',
        action: 'search_teams',
        platform: 'teams'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_teams',
        platform: 'teams'
      };
    }
  }

  /**
   * List channels
   */
  private async listChannels(command: string, context?: any): Promise<TeamsSkillResult> {
    try {
      const teamId = this.extractTeamId(command, context);
      if (!teamId) {
        return {
          success: false,
          error: 'Team ID is required. Example: "list channels in team [team-name]"',
          action: 'list_channels',
          platform: 'teams'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/teams/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          team_id: teamId,
          include_private: command.includes('private'),
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        const channels = data.channels;
        const summary = this.generateChannelsSummary(channels);
        
        return {
          success: true,
          data: {
            channels,
            summary,
            total: data.total_count,
            team_id: teamId
          },
          action: 'list_channels',
          platform: 'teams'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list channels',
        action: 'list_channels',
        platform: 'teams'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_channels',
        platform: 'teams'
      };
    }
  }

  /**
   * List messages
   */
  private async listMessages(command: string, context?: any): Promise<TeamsSkillResult> {
    try {
      const channelId = this.extractChannelId(command, context);
      const teamId = this.extractTeamId(command, context);
      
      if (!channelId && !teamId) {
        return {
          success: false,
          error: 'Channel ID is required. Example: "list messages in [channel-name]"',
          action: 'list_messages',
          platform: 'teams'
        };
      }

      const filters = this.extractMessageFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/teams/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          team_id: teamId,
          channel_id: channelId,
          filters,
          limit: this.extractLimit(command) || 100
        })
      });

      const data = await response.json();

      if (data.ok) {
        const messages = data.messages;
        const summary = this.generateMessagesSummary(messages);
        
        return {
          success: true,
          data: {
            messages,
            summary,
            total: data.total_count
          },
          action: 'list_messages',
          platform: 'teams'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list messages',
        action: 'list_messages',
        platform: 'teams'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_messages',
        platform: 'teams'
      };
    }
  }

  /**
   * Send message
   */
  private async sendMessage(command: string, context?: any): Promise<TeamsSkillResult> {
    try {
      const messageInfo = this.extractMessageInfo(command, context);
      
      if (!messageInfo.content) {
        return {
          success: false,
          error: 'Message content is required. Example: "send message [your message] to [channel-name]"',
          action: 'send_message',
          platform: 'teams'
        };
      }

      if (!messageInfo.channelId && !messageInfo.teamId) {
        return {
          success: false,
          error: 'Channel or team is required. Example: "send message [content] to [channel-name]"',
          action: 'send_message',
          platform: 'teams'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/teams/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: messageInfo
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            message: data.message,
            url: data.message.webUrl,
            channel_name: messageInfo.channelName,
            message: `Message sent to ${messageInfo.channelName}`
          },
          action: 'send_message',
          platform: 'teams'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to send message',
        action: 'send_message',
        platform: 'teams'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'send_message',
        platform: 'teams'
      };
    }
  }

  /**
   * Search messages
   */
  private async searchMessages(command: string, context?: any): Promise<TeamsSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search messages deadline"',
          action: 'search_messages',
          platform: 'teams'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/teams/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'messages',
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            messages: data.messages,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'search_messages',
          platform: 'teams'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search messages',
        action: 'search_messages',
        platform: 'teams'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_messages',
        platform: 'teams'
      };
    }
  }

  /**
   * Get user profile
   */
  private async getUserProfile(command: string, context?: any): Promise<TeamsSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/teams/user/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            user: data.user,
            profile: data.profile
          },
          action: 'get_user_profile',
          platform: 'teams'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to get user profile',
        action: 'get_user_profile',
        platform: 'teams'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'get_user_profile',
        platform: 'teams'
      };
    }
  }

  // Helper methods for extracting information from commands
  
  private extractLimit(command: string): number | null {
    const limitMatch = command.match(/limit\s+(\d+)/i);
    return limitMatch ? parseInt(limitMatch[1]) : null;
  }

  private extractSearchQuery(command: string): string {
    const patterns = [
      /search\s+for\s+["']([^"']+)["']/i,
      /search\s+["']([^"']+)["']/i,
      /find\s+["']([^"']+)["']/i,
      /search\s+(\w+)/i,
      /find\s+(\w+)/i
    ];

    for (const pattern of patterns) {
      const match = command.match(pattern);
      if (match && match[1]) {
        return match[1];
      }
    }

    return '';
  }

  private extractTeamId(command: string, context?: any): string | null {
    // First check context for team reference
    if (context?.teamId) return context.teamId;
    if (context?.team?.id) return context.team.id;

    // Extract from command
    const teamMatch = command.match(/(?:team|in)\s+["']?([^"']+)["']?/i);
    if (teamMatch) {
      // In real implementation, this would resolve team name to ID
      return teamMatch[1];
    }

    return null;
  }

  private extractChannelId(command: string, context?: any): string | null {
    // First check context for channel reference
    if (context?.channelId) return context.channelId;
    if (context?.channel?.id) return context.channel.id;

    // Extract from command
    const channelMatch = command.match(/(?:channel)\s+["']?([^"']+)["']?/i);
    if (channelMatch) {
      // In real implementation, this would resolve channel name to ID
      return channelMatch[1];
    }

    return null;
  }

  private extractMessageInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract message content
    const messageMatch = command.match(/(?:message|chat)\s+["']([^"']+)["']/i);
    if (messageMatch) {
      info.content = messageMatch[1];
    }

    // Extract target (channel/team)
    const targetMatch = command.match(/(?:to|in)\s+["']?([^"']+)["']?/i);
    if (targetMatch) {
      info.channelName = targetMatch[1];
      info.channelId = targetMatch[1]; // In real implementation, resolve to ID
    }

    // Extract from context
    if (context?.channelId) info.channelId = context.channelId;
    if (context?.teamId) info.teamId = context.teamId;
    if (context?.channel?.name) info.channelName = context.channel.name;

    return info;
  }

  private extractMessageFilters(command: string): any {
    const filters: any = {};

    if (command.includes('from me')) {
      filters.from = 'me';
    }

    if (command.includes('mentions me')) {
      filters.mentions = 'me';
    }

    if (command.includes('today')) {
      filters.dateRange = 'today';
    } else if (command.includes('yesterday')) {
      filters.dateRange = 'yesterday';
    } else if (command.includes('this week')) {
      filters.dateRange = 'week';
    } else if (command.includes('this month')) {
      filters.dateRange = 'month';
    }

    if (command.includes('with files')) {
      filters.hasAttachments = true;
    }

    return filters;
  }

  // Summary generators
  
  private generateTeamsSummary(teams: TeamsTeam[]): string {
    const total = teams.length;
    const publicCount = teams.filter(t => t.visibility === 'public').length;
    const privateCount = teams.filter(t => t.visibility === 'private').length;
    const totalMembers = teams.reduce((sum, t) => sum + (t.membersCount || 0), 0);

    return `Found ${total} teams: ${publicCount} public, ${privateCount} private, ${totalMembers} total members`;
  }

  private generateChannelsSummary(channels: TeamsChannel[]): string {
    const total = channels.length;
    const standardCount = channels.filter(c => c.membershipType === 'standard').length;
    const privateCount = channels.filter(c => c.membershipType === 'private').length;
    const sharedCount = channels.filter(c => c.membershipType === 'shared').length;

    return `Found ${total} channels: ${standardCount} standard, ${privateCount} private, ${sharedCount} shared`;
  }

  private generateMessagesSummary(messages: TeamsMessage[]): string {
    const total = messages.length;
    const fromMe = messages.filter(m => m.fromMe).length;
    const withMentions = messages.filter(m => m.mentions?.length).length;
    const withFiles = messages.filter(m => m.attachments?.length).length;

    return `Found ${total} messages: ${fromMe} from me, ${withMentions} with mentions, ${withFiles} with files`;
  }
}

// Export singleton instance
export const teamsSkills = new TeamsSkills();

// Export types
export type { TeamsSkillResult };