/**
 * Enhanced Notion Integration Skills
 * Natural language commands for Notion operations following established pattern
 */

import { 
  NotionDatabase,
  NotionPage,
  NotionBlock,
  NotionUser,
  NotionWorkspace
} from '../types/notion-types';

export interface NotionSkillResult {
  success: boolean;
  data?: any;
  error?: string;
  action: string;
  platform: 'notion';
}

export class EnhancedNotionSkills {
  private userId: string;
  private baseUrl: string;

  constructor(userId: string = 'default-user', baseUrl: string = '') {
    this.userId = userId;
    this.baseUrl = baseUrl;
  }

  /**
   * Execute natural language Notion command
   */
  async executeCommand(command: string, context?: any): Promise<NotionSkillResult> {
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
        if (lowerCommand.includes('info')) {
          return await this.getWorkspaceInfo(lowerCommand, context);
        }
      }

      // Database commands
      if (lowerCommand.includes('database') || lowerCommand.includes('db')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listDatabases(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchDatabases(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createDatabase(lowerCommand, context);
        }
        if (lowerCommand.includes('query')) {
          return await this.queryDatabase(lowerCommand, context);
        }
      }

      // Page commands
      if (lowerCommand.includes('page')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listPages(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchPages(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createPage(lowerCommand, context);
        }
        if (lowerCommand.includes('update') || lowerCommand.includes('edit')) {
          return await this.updatePage(lowerCommand, context);
        }
        if (lowerCommand.includes('delete')) {
          return await this.deletePage(lowerCommand, context);
        }
      }

      // Block commands
      if (lowerCommand.includes('block')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listBlocks(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchBlocks(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createBlock(lowerCommand, context);
        }
        if (lowerCommand.includes('update') || lowerCommand.includes('edit')) {
          return await this.updateBlock(lowerCommand, context);
        }
        if (lowerCommand.includes('delete')) {
          return await this.deleteBlock(lowerCommand, context);
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

      // Search commands
      if (lowerCommand.includes('search')) {
        return await this.globalSearch(lowerCommand, context);
      }

      // Content creation commands
      if (lowerCommand.includes('create') || lowerCommand.includes('new')) {
        if (lowerCommand.includes('note') || lowerCommand.includes('doc')) {
          return await this.createNote(lowerCommand, context);
        }
        if (lowerCommand.includes('task') || lowerCommand.includes('todo')) {
          return await this.createTask(lowerCommand, context);
        }
        if (lowerCommand.includes('project')) {
          return await this.createProject(lowerCommand, context);
        }
      }

      // Default: Search across Notion
      return await this.globalSearch(lowerCommand, context);

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        action: 'execute_command',
        platform: 'notion'
      };
    }
  }

  /**
   * List workspaces
   */
  private async listWorkspaces(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/notion/workspaces`, {
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
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list workspaces',
        action: 'list_workspaces',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_workspaces',
        platform: 'notion'
      };
    }
  }

  /**
   * List databases
   */
  private async listDatabases(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const filters = this.extractDatabaseFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/notion/databases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          include_archived: filters.includeArchived,
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        const databases = data.databases;
        const summary = this.generateDatabasesSummary(databases);
        
        return {
          success: true,
          data: {
            databases,
            summary,
            total: data.total_count
          },
          action: 'list_databases',
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list databases',
        action: 'list_databases',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_databases',
        platform: 'notion'
      };
    }
  }

  /**
   * List pages
   */
  private async listPages(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const databaseId = this.extractDatabaseId(command, context);
      const filters = this.extractPageFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/notion/pages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          database_id: databaseId,
          include_archived: filters.includeArchived,
          filters,
          limit: this.extractLimit(command) || 100
        })
      });

      const data = await response.json();

      if (data.ok) {
        const pages = data.pages;
        const summary = this.generatePagesSummary(pages);
        
        return {
          success: true,
          data: {
            pages,
            summary,
            total: data.total_count
          },
          action: 'list_pages',
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list pages',
        action: 'list_pages',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_pages',
        platform: 'notion'
      };
    }
  }

  /**
   * Create page
   */
  private async createPage(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const pageInfo = this.extractPageInfo(command, context);
      
      if (!pageInfo.title) {
        return {
          success: false,
          error: 'Page title is required. Example: "create page [title] with content [content]"',
          action: 'create_page',
          platform: 'notion'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/notion/pages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: pageInfo
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            page: data.page,
            url: data.page.url,
            message: `Page "${pageInfo.title}" created successfully`
          },
          action: 'create_page',
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create page',
        action: 'create_page',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_page',
        platform: 'notion'
      };
    }
  }

  /**
   * Search pages
   */
  private async searchPages(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search pages deadline"',
          action: 'search_pages',
          platform: 'notion'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/notion/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'pages',
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            pages: data.pages,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'search_pages',
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search pages',
        action: 'search_pages',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_pages',
        platform: 'notion'
      };
    }
  }

  /**
   * List users
   */
  private async listUsers(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const filters = this.extractUserFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/notion/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
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
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list users',
        action: 'list_users',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_users',
        platform: 'notion'
      };
    }
  }

  /**
   * Get user profile
   */
  private async getUserProfile(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/notion/user/profile`, {
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
            workspace: data.workspace
          },
          action: 'get_user_profile',
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to get user profile',
        action: 'get_user_profile',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'get_user_profile',
        platform: 'notion'
      };
    }
  }

  /**
   * Create note (simplified page creation)
   */
  private async createNote(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const noteInfo = this.extractNoteInfo(command, context);
      
      if (!noteInfo.title && !noteInfo.content) {
        return {
          success: false,
          error: 'Note title or content is required. Example: "create note [title] with content [content]"',
          action: 'create_note',
          platform: 'notion'
        };
      }

      // Use page creation endpoint
      const response = await fetch(`${this.baseUrl}/api/integrations/notion/pages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: {
            ...noteInfo,
            parent_type: 'page_id',
            parent_id: noteInfo.parentPageId || 'root'
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            page: data.page,
            url: data.page.url,
            message: `Note "${noteInfo.title || 'Untitled'}" created successfully`
          },
          action: 'create_note',
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create note',
        action: 'create_note',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_note',
        platform: 'notion'
      };
    }
  }

  /**
   * Global search across Notion
   */
  private async globalSearch(command: string, context?: any): Promise<NotionSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search project deadline"',
          action: 'global_search',
          platform: 'notion'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/notion/search`, {
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
          platform: 'notion'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search Notion',
        action: 'global_search',
        platform: 'notion'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'global_search',
        platform: 'notion'
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

  private extractDatabaseId(command: string, context?: any): string | null {
    // First check context for database reference
    if (context?.databaseId) return context.databaseId;
    if (context?.database?.id) return context.database.id;

    // Extract from command
    const dbMatch = command.match(/(?:database|db)\s+["']?([^"']+)["']?/i);
    if (dbMatch) {
      // In real implementation, this would resolve database name to ID
      return dbMatch[1];
    }

    return null;
  }

  private extractPageInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title
    const titleMatch = command.match(/(?:page|note)\s+(?:with\s+title|titled?)\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.title = titleMatch[1];
    }

    // Extract content
    const contentMatch = command.match(/(?:with\s+content|containing?)\s+["']([^"']+)["']/i);
    if (contentMatch) {
      info.content = contentMatch[1];
    }

    // Extract parent database/page
    const parentMatch = command.match(/(?:in|within)\s+(?:database|page)\s+["']?([^"']+)["']?/i);
    if (parentMatch) {
      info.parentDatabaseName = parentMatch[1];
    }

    // Extract from context
    if (context?.databaseId) info.parent_database_id = context.databaseId;
    if (context?.pageId) info.parent_page_id = context.pageId;

    return info;
  }

  private extractNoteInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title
    const titleMatch = command.match(/note\s+(?:titled?)?\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.title = titleMatch[1];
    }

    // Extract content
    const contentMatch = command.match(/(?:with|containing?)\s+["']([^"']+)["']/i);
    if (contentMatch) {
      info.content = contentMatch[1];
    }

    // Extract parent page
    const parentMatch = command.match(/(?:in|within)\s+page\s+["']?([^"'\s]+)["']?/i);
    if (parentMatch) {
      info.parentPageName = parentMatch[1];
    }

    return info;
  }

  private extractDatabaseFilters(command: string): any {
    const filters: any = {};

    if (command.includes('archived')) {
      filters.includeArchived = true;
    }

    if (command.includes('inline')) {
      filters.includeInline = true;
    }

    return filters;
  }

  private extractPageFilters(command: string): any {
    const filters: any = {};

    if (command.includes('archived')) {
      filters.includeArchived = true;
    }

    if (command.includes('published')) {
      filters.status = 'published';
    }

    if (command.includes('draft')) {
      filters.status = 'draft';
    }

    return filters;
  }

  private extractUserFilters(command: string): any {
    const filters: any = {};

    if (command.includes('bots')) {
      filters.includeBots = true;
    }

    if (command.includes('guests')) {
      filters.includeGuests = true;
    }

    if (command.includes('active')) {
      filters.includeActive = true;
    }

    return filters;
  }

  // Summary generators
  
  private generateWorkspacesSummary(workspaces: any[]): string {
    const total = workspaces.length;
    const totalUsers = workspaces.reduce((sum, ws) => sum + (ws.users_count || 0), 0);
    const totalDatabases = workspaces.reduce((sum, ws) => sum + (ws.databases_count || 0), 0);

    return `Found ${total} workspaces: ${totalUsers} total users, ${totalDatabases} total databases`;
  }

  private generateDatabasesSummary(databases: any[]): string {
    const total = databases.length;
    const inlineCount = databases.filter(db => db.is_inline).length;
    const archivedCount = databases.filter(db => db.archived).length;

    return `Found ${total} databases: ${inlineCount} inline, ${archivedCount} archived`;
  }

  private generatePagesSummary(pages: any[]): string {
    const total = pages.length;
    const publishedCount = pages.filter(p => !p.archived).length;
    const withContent = pages.filter(p => p.content).length;

    return `Found ${total} pages: ${publishedCount} published, ${withContent} with content`;
  }

  private generateUsersSummary(users: any[]): string {
    const total = users.length;
    const botCount = users.filter(u => u.type === 'bot').length;
    const personCount = users.filter(u => u.type === 'person').length;

    return `Found ${total} users: ${personCount} people, ${botCount} bots`;
  }
}

// Export singleton instance
export const enhancedNotionSkills = new EnhancedNotionSkills();

// Export types
export type { NotionSkillResult };