/**
 * Slack Integration Skills
 * Natural language commands for Slack operations
 */

import { 
  SlackWorkspace,
  SlackChannel,
  SlackMessage,
  SlackUser,
  SlackFile,
  SlackReaction
} from '../types/slack-types';

export interface SlackSkillResult {
  success: boolean;
  data?: any;
  error?: string;
  action: string;
  platform: 'slack';
}

export class SlackSkills {
  private userId: string;
  private baseUrl: string;

  constructor(userId: string = 'default-user', baseUrl: string = '') {
    this.userId = userId;
    this.baseUrl = baseUrl;
  }

  /**
   * Execute natural language Slack command
   */
  async executeCommand(command: string, context?: any): Promise<SlackSkillResult> {
    const lowerCommand = command.toLowerCase().trim();

    try {
      // Workspace commands
      if (lowerCommand.includes('workspace')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listWorkspaces(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchWorkspaces(lowerCommand, context);
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
        if (lowerCommand.includes('join')) {
          return await this.joinChannel(lowerCommand, context);
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
        if (lowerCommand.includes('star')) {
          return await this.starMessage(lowerCommand, context);
        }
        if (lowerCommand.includes('pin')) {
          return await this.pinMessage(lowerCommand, context);
        }
      }

      // User commands
      if (lowerCommand.includes('user') || lowerCommand.includes('profile')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listUsers(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchUsers(lowerCommand, context);
        }
        if (lowerCommand.includes('profile')) {
          return await this.getUserProfile(lowerCommand, context);
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
        if (lowerCommand.includes('upload')) {
          return await this.uploadFile(lowerCommand, context);
        }
      }

      // Reaction commands
      if (lowerCommand.includes('reaction') || lowerCommand.includes('emoji')) {
        if (lowerCommand.includes('add')) {
          return await this.addReaction(lowerCommand, context);
        }
        if (lowerCommand.includes('remove')) {
          return await this.removeReaction(lowerCommand, context);
        }
        if (lowerCommand.includes('list')) {
          return await this.listReactions(lowerCommand, context);
        }
      }

      // Search commands
      if (lowerCommand.includes('search')) {
        return await this.globalSearch(lowerCommand, context);
      }

      // Default: Search across Slack
      return await this.globalSearch(lowerCommand, context);

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        action: 'execute_command',
        platform: 'slack'
      };
    }
  }

  /**
   * List workspaces
   */
  private async listWorkspaces(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/slack/workspaces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        const workspaces = data.workspaces;
        const summary = this.generateWorkspacesSummary(workspaces);
        
        return {
          success: true,
          data: {
            workspaces,
            summary,
            total: data.total_count
          },
          action: 'list_workspaces',
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list workspaces',
        action: 'list_workspaces',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_workspaces',
        platform: 'slack'
      };
    }
  }

  /**
   * List channels
   */
  private async listChannels(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const workspaceId = this.extractWorkspaceId(command, context);
      const filters = this.extractChannelFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/slack/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          workspace_id: workspaceId,
          include_private: filters.includePrivate,
          include_archived: filters.includeArchived,
          limit: this.extractLimit(command) || 100
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
            total: data.total_count
          },
          action: 'list_channels',
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list channels',
        action: 'list_channels',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_channels',
        platform: 'slack'
      };
    }
  }

  /**
   * List messages
   */
  private async listMessages(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const channelId = this.extractChannelId(command, context);
      const workspaceId = this.extractWorkspaceId(command, context);
      const filters = this.extractMessageFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/slack/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          workspace_id: workspaceId,
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
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list messages',
        action: 'list_messages',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_messages',
        platform: 'slack'
      };
    }
  }

  /**
   * Send message
   */
  private async sendMessage(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const messageInfo = this.extractMessageInfo(command, context);
      
      if (!messageInfo.text) {
        return {
          success: false,
          error: 'Message content is required. Example: "send message Hello world to #general"',
          action: 'send_message',
          platform: 'slack'
        };
      }

      if (!messageInfo.channelId && !messageInfo.channelName) {
        return {
          success: false,
          error: 'Channel is required. Example: "send message Hello world to #general"',
          action: 'send_message',
          platform: 'slack'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/slack/messages`, {
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
            channel: data.channel,
            url: data.message.url,
            message: `Message sent to ${messageInfo.channelName || 'channel'}`
          },
          action: 'send_message',
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to send message',
        action: 'send_message',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'send_message',
        platform: 'slack'
      };
    }
  }

  /**
   * Search messages
   */
  private async searchMessages(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search messages deadline"',
          action: 'search_messages',
          platform: 'slack'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/slack/search`, {
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
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search messages',
        action: 'search_messages',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_messages',
        platform: 'slack'
      };
    }
  }

  /**
   * List users
   */
  private async listUsers(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const workspaceId = this.extractWorkspaceId(command, context);
      const filters = this.extractUserFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/slack/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          workspace_id: workspaceId,
          include_restricted: filters.includeRestricted,
          include_bots: filters.includeBots,
          limit: this.extractLimit(command) || 100
        })
      });

      const data = await response.json();

      if (data.ok) {
        const users = data.users;
        const summary = this.generateUsersSummary(users);
        
        return {
          success: true,
          data: {
            users,
            summary,
            total: data.total_count
          },
          action: 'list_users',
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list users',
        action: 'list_users',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_users',
        platform: 'slack'
      };
    }
  }

  /**
   * Get user profile
   */
  private async getUserProfile(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/slack/user/profile`, {
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
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to get user profile',
        action: 'get_user_profile',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'get_user_profile',
        platform: 'slack'
      };
    }
  }

  /**
   * List files
   */
  private async listFiles(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const channelId = this.extractChannelId(command, context);
      const workspaceId = this.extractWorkspaceId(command, context);
      const filters = this.extractFileFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/slack/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          workspace_id: workspaceId,
          channel_id: channelId,
          filters,
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        const files = data.files;
        const summary = this.generateFilesSummary(files);
        
        return {
          success: true,
          data: {
            files,
            summary,
            total: data.total_count
          },
          action: 'list_files',
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list files',
        action: 'list_files',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_files',
        platform: 'slack'
      };
    }
  }

  /**
   * Global search across Slack
   */
  private async globalSearch(command: string, context?: any): Promise<SlackSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search project deadline"',
          action: 'global_search',
          platform: 'slack'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/slack/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'global',
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            results: data.results,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'global_search',
          platform: 'slack'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search Slack',
        action: 'global_search',
        platform: 'slack'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'global_search',
        platform: 'slack'
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

  private extractWorkspaceId(command: string, context?: any): string | null {
    // First check context for workspace reference
    if (context?.workspaceId) return context.workspaceId;
    if (context?.workspace?.id) return context.workspace.id;

    // Extract from command
    const workspaceMatch = command.match(/(?:workspace|in)\s+["']?([^"']+)["']?/i);
    if (workspaceMatch) {
      // In real implementation, this would resolve workspace name to ID
      return workspaceMatch[1];
    }

    return null;
  }

  private extractChannelId(command: string, context?: any): string | null {
    // First check context for channel reference
    if (context?.channelId) return context.channelId;
    if (context?.channel?.id) return context.channel.id;

    // Extract from command
    const channelMatch = command.match(/(?:channel|to)\s+["']?#?([^"'\s]+)["']?/i);
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
      info.text = messageMatch[1];
    }

    // Extract target channel
    const channelMatch = command.match(/(?:to|in)\s+["']?#?([^"'\s]+)["']?/i);
    if (channelMatch) {
      info.channelName = channelMatch[1];
      info.channelId = channelMatch[1]; // In real implementation, resolve to ID
    }

    // Extract from context
    if (context?.channelId) info.channelId = context.channelId;
    if (context?.channel?.name) info.channelName = context.channel.name;
    if (context?.workspaceId) info.workspaceId = context.workspaceId;

    return info;
  }

  private extractChannelFilters(command: string): any {
    const filters: any = {};

    if (command.includes('private')) {
      filters.includePrivate = true;
    }

    if (command.includes('archived')) {
      filters.includeArchived = true;
    }

    if (command.includes('public')) {
      filters.includePublic = true;
    }

    if (command.includes('shared')) {
      filters.includeShared = true;
    }

    return filters;
  }

  private extractMessageFilters(command: string): any {
    const filters: any = {};

    if (command.includes('from me')) {
      filters.from = 'me';
    }

    if (command.includes('mentions me')) {
      filters.mentions = 'me';
    }

    if (command.includes('with files')) {
      filters.hasFiles = true;
    }

    if (command.includes('starred')) {
      filters.starred = true;
    }

    if (command.includes('pinned')) {
      filters.pinned = true;
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

    return filters;
  }

  private extractUserFilters(command: string): any {
    const filters: any = {};

    if (command.includes('restricted')) {
      filters.includeRestricted = true;
    }

    if (command.includes('bots')) {
      filters.includeBots = true;
    }

    if (command.includes('active')) {
      filters.includeActive = true;
    }

    return filters;
  }

  private extractFileFilters(command: string): any {
    const filters: any = {};

    if (command.includes('images')) {
      filters.fileType = 'images';
    } else if (command.includes('documents')) {
      filters.fileType = 'documents';
    } else if (command.includes('videos')) {
      filters.fileType = 'videos';
    } else if (command.includes('audio')) {
      filters.fileType = 'audio';
    }

    if (command.includes('uploaded by me')) {
      filters.uploadedBy = 'me';
    }

    return filters;
  }

  // Summary generators
  
  private generateWorkspacesSummary(workspaces: SlackWorkspace[]): string {
    const total = workspaces.length;
    const enterpriseCount = workspaces.filter(w => w.enterprise_id).length;

    return `Found ${total} workspaces: ${enterpriseCount} with enterprise`;
  }

  private generateChannelsSummary(channels: SlackChannel[]): string {
    const total = channels.length;
    const privateCount = channels.filter(c => c.is_private).length;
    const archivedCount = channels.filter(c => c.is_archived).length;
    const sharedCount = channels.filter(c => c.is_shared).length;
    const totalMembers = channels.reduce((sum, c) => sum + (c.num_members || 0), 0);

    return `Found ${total} channels: ${privateCount} private, ${archivedCount} archived, ${sharedCount} shared, ${totalMembers} total members`;
  }

  private generateMessagesSummary(messages: SlackMessage[]): string {
    const total = messages.length;
    const withFiles = messages.filter(m => m.files && m.files.length > 0).length;
    const withReactions = messages.filter(m => m.reactions && m.reactions.length > 0).length;
    const starred = messages.filter(m => m.is_starred).length;
    const replies = messages.reduce((sum, m) => sum + (m.reply_count || 0), 0);

    return `Found ${total} messages: ${withFiles} with files, ${withReactions} with reactions, ${starred} starred, ${replies} total replies`;
  }

  private generateUsersSummary(users: SlackUser[]): string {
    const total = users.length;
    const adminCount = users.filter(u => u.is_admin).length;
    const ownerCount = users.filter(u => u.is_owner).length;
    const botCount = users.filter(u => u.is_bot).length;
    const restrictedCount = users.filter(u => u.is_restricted || u.is_ultra_restricted).length;

    return `Found ${total} users: ${adminCount} admins, ${ownerCount} owners, ${botCount} bots, ${restrictedCount} restricted`;
  }

  private generateFilesSummary(files: SlackFile[]): string {
    const total = files.length;
    const imageCount = files.filter(f => f.mimetype?.startsWith('image/')).length;
    const videoCount = files.filter(f => f.mimetype?.startsWith('video/')).length;
    const audioCount = files.filter(f => f.mimetype?.startsWith('audio/')).length;
    const documentCount = files.filter(f => f.mimetype?.includes('pdf') || f.mimetype?.includes('document')).length;

    return `Found ${total} files: ${imageCount} images, ${videoCount} videos, ${audioCount} audio, ${documentCount} documents`;
  }
}

// Export singleton instance
export const slackSkills = new SlackSkills();

// Export types
export type { SlackSkillResult };