/**
 * Enhanced Figma Integration Skills
 * Natural language commands for Figma operations following established pattern
 */

import { 
  FigmaFile,
  FigmaTeam,
  FigmaProject,
  FigmaComponent,
  FigmaUser,
  FigmaComment,
  FigmaVersion,
  FigmaLibrary
} from '../types/figma-types';

export interface FigmaSkillResult {
  success: boolean;
  data?: any;
  error?: string;
  action: string;
  platform: 'figma';
}

export class EnhancedFigmaSkills {
  private userId: string;
  private baseUrl: string;

  constructor(userId: string = 'default-user', baseUrl: string = '') {
    this.userId = userId;
    this.baseUrl = baseUrl;
  }

  /**
   * Execute natural language Figma command
   */
  async executeCommand(command: string, context?: any): Promise<FigmaSkillResult> {
    const lowerCommand = command.toLowerCase().trim();

    try {
      // File commands
      if (lowerCommand.includes('file')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listFiles(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchFiles(lowerCommand, context);
        }
        if (lowerCommand.includes('open') || lowerCommand.includes('launch')) {
          return await this.openFile(lowerCommand, context);
        }
        if (lowerCommand.includes('create') || lowerCommand.includes('new')) {
          return await this.createFile(lowerCommand, context);
        }
        if (lowerCommand.includes('duplicate') || lowerCommand.includes('copy')) {
          return await this.duplicateFile(lowerCommand, context);
        }
        if (lowerCommand.includes('archive') || lowerCommand.includes('delete')) {
          return await this.archiveFile(lowerCommand, context);
        }
      }

      // Component commands
      if (lowerCommand.includes('component')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listComponents(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchComponents(lowerCommand, context);
        }
        if (lowerCommand.includes('create') || lowerCommand.includes('add')) {
          return await this.createComponent(lowerCommand, context);
        }
      }

      // Team commands
      if (lowerCommand.includes('team')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listTeams(lowerCommand, context);
        }
        if (lowerCommand.includes('members') || lowerCommand.includes('users')) {
          return await this.listTeamMembers(lowerCommand, context);
        }
      }

      // Project commands
      if (lowerCommand.includes('project')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listProjects(lowerCommand, context);
        }
        if (lowerCommand.includes('create') || lowerCommand.includes('new')) {
          return await this.createProject(lowerCommand, context);
        }
      }

      // Design commands
      if (lowerCommand.includes('design')) {
        if (lowerCommand.includes('create') || lowerCommand.includes('new')) {
          return await this.createDesign(lowerCommand, context);
        }
        if (lowerCommand.includes('mockup') || lowerCommand.includes('wireframe')) {
          return await this.createMockup(lowerCommand, context);
        }
      }

      // Prototype commands
      if (lowerCommand.includes('prototype')) {
        if (lowerCommand.includes('create') || lowerCommand.includes('new')) {
          return await this.createPrototype(lowerCommand, context);
        }
        if (lowerCommand.includes('preview') || lowerCommand.includes('share')) {
          return await this.sharePrototype(lowerCommand, context);
        }
      }

      // Library commands
      if (lowerCommand.includes('library')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listLibraries(lowerCommand, context);
        }
        if (lowerCommand.includes('publish') || lowerCommand.includes('share')) {
          return await this.publishLibrary(lowerCommand, context);
        }
      }

      // Style guide commands
      if (lowerCommand.includes('style') || lowerCommand.includes('styleguide')) {
        if (lowerCommand.includes('create') || lowerCommand.includes('generate')) {
          return await this.createStyleGuide(lowerCommand, context);
        }
        if (lowerCommand.includes('update') || lowerCommand.includes('refresh')) {
          return await this.updateStyleGuide(lowerCommand, context);
        }
      }

      // Collaboration commands
      if (lowerCommand.includes('collaborat') || lowerCommand.includes('share')) {
        if (lowerCommand.includes('invite') || lowerCommand.includes('add')) {
          return await this.inviteCollaborator(lowerCommand, context);
        }
        if (lowerCommand.includes('permissions') || lowerCommand.includes('access')) {
          return await this.updatePermissions(lowerCommand, context);
        }
      }

      // Comment commands
      if (lowerCommand.includes('comment')) {
        if (lowerCommand.includes('add') || lowerCommand.includes('create')) {
          return await this.addComment(lowerCommand, context);
        }
        if (lowerCommand.includes('reply')) {
          return await this.replyToComment(lowerCommand, context);
        }
      }

      // Version commands
      if (lowerCommand.includes('version') || lowerCommand.includes('history')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listVersions(lowerCommand, context);
        }
        if (lowerCommand.includes('create') || lowerCommand.includes('save')) {
          return await this.createVersion(lowerCommand, context);
        }
      }

      // Search commands
      if (lowerCommand.includes('search')) {
        return await this.globalSearch(lowerCommand, context);
      }

      // Content creation commands
      if (lowerCommand.includes('create') || lowerCommand.includes('add') || lowerCommand.includes('new')) {
        if (lowerCommand.includes('wireframe') || lowerCommand.includes('sketch')) {
          return await this.createWireframe(lowerCommand, context);
        }
        if (lowerCommand.includes('icon') || lowerCommand.includes('symbol')) {
          return await this.createIcon(lowerCommand, context);
        }
        if (lowerCommand.includes('illustration') || lowerCommand.includes('art')) {
          return await this.createIllustration(lowerCommand, context);
        }
      }

      // Export commands
      if (lowerCommand.includes('export') || lowerCommand.includes('download')) {
        if (lowerCommand.includes('svg')) {
          return await this.exportSVG(lowerCommand, context);
        }
        if (lowerCommand.includes('png')) {
          return await this.exportPNG(lowerCommand, context);
        }
        if (lowerCommand.includes('pdf')) {
          return await this.exportPDF(lowerCommand, context);
        }
      }

      // Action commands
      if (lowerCommand.includes('activities') || lowerCommand.includes('history') || lowerCommand.includes('log')) {
        return await this.getActivities(lowerCommand, context);
      }

      // User commands
      if (lowerCommand.includes('user') || lowerCommand.includes('profile')) {
        if (lowerCommand.includes('profile')) {
          return await this.getUserProfile(lowerCommand, context);
        }
        if (lowerCommand.includes('settings') || lowerCommand.includes('preferences')) {
          return await this.getUserSettings(lowerCommand, context);
        }
      }

      // Default: Search across Figma
      return await this.globalSearch(lowerCommand, context);

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        action: 'execute_command',
        platform: 'figma'
      };
    }
  }

  /**
   * List files
   */
  private async listFiles(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          team_id: this.extractTeamId(command, context),
          include_archived: this.extractIncludeArchived(command),
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
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list files',
        action: 'list_files',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_files',
        platform: 'figma'
      };
    }
  }

  /**
   * List components
   */
  private async listComponents(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const fileKey = this.extractFileKey(command, context);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/figma/components`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          file_key: fileKey,
          limit: this.extractLimit(command) || 100
        })
      });

      const data = await response.json();

      if (data.ok) {
        const components = data.components;
        const summary = this.generateComponentsSummary(components);
        
        return {
          success: true,
          data: {
            components,
            summary,
            total: data.total_count
          },
          action: 'list_components',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list components',
        action: 'list_components',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_components',
        platform: 'figma'
      };
    }
  }

  /**
   * List teams
   */
  private async listTeams(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/figma/teams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          limit: this.extractLimit(command) || 20
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
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list teams',
        action: 'list_teams',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_teams',
        platform: 'figma'
      };
    }
  }

  /**
   * List projects
   */
  private async listProjects(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const teamId = this.extractTeamId(command, context);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/figma/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          team_id: teamId,
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        const projects = data.projects;
        const summary = this.generateProjectsSummary(projects);
        
        return {
          success: true,
          data: {
            projects,
            summary,
            total: data.total_count
          },
          action: 'list_projects',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list projects',
        action: 'list_projects',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_projects',
        platform: 'figma'
      };
    }
  }

  /**
   * Create design file
   */
  private async createDesign(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const designInfo = this.extractDesignInfo(command, context);
      
      if (!designInfo.name) {
        return {
          success: false,
          error: 'Design name is required. Example: "create design [name] with description [description]"',
          action: 'create_design',
          platform: 'figma'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: designInfo
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            file: data.file,
            url: data.file.thumbnail_url,
            message: `Design "${designInfo.name}" created successfully`
          },
          action: 'create_design',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create design',
        action: 'create_design',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_design',
        platform: 'figma'
      };
    }
  }

  /**
   * Create wireframe
   */
  private async createWireframe(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const wireframeInfo = this.extractWireframeInfo(command, context);
      
      if (!wireframeInfo.name) {
        return {
          success: false,
          error: 'Wireframe name is required. Example: "create wireframe [name] with description [description]"',
          action: 'create_wireframe',
          platform: 'figma'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: {
            ...wireframeInfo,
            file_type: 'wireframe',
            template: 'wireframe'
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            file: data.file,
            url: data.file.thumbnail_url,
            message: `Wireframe "${wireframeInfo.name}" created successfully`
          },
          action: 'create_wireframe',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create wireframe',
        action: 'create_wireframe',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_wireframe',
        platform: 'figma'
      };
    }
  }

  /**
   * Create icon
   */
  private async createIcon(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const iconInfo = this.extractIconInfo(command, context);
      
      if (!iconInfo.name) {
        return {
          success: false,
          error: 'Icon name is required. Example: "create icon [name] with description [description]"',
          action: 'create_icon',
          platform: 'figma'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/figma/components`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: {
            ...iconInfo,
            component_type: 'icon',
            size: iconInfo.size || '24x24'
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            component: data.component,
            message: `Icon "${iconInfo.name}" created successfully`
          },
          action: 'create_icon',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create icon',
        action: 'create_icon',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_icon',
        platform: 'figma'
      };
    }
  }

  /**
   * Create style guide
   */
  private async createStyleGuide(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const styleGuideInfo = this.extractStyleGuideInfo(command, context);
      
      if (!styleGuideInfo.name) {
        return {
          success: false,
          error: 'Style guide name is required. Example: "create style guide [name] with description [description]"',
          action: 'create_style_guide',
          platform: 'figma'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/figma/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: {
            ...styleGuideInfo,
            file_type: 'style_guide',
            template: 'style_guide'
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            file: data.file,
            url: data.file.thumbnail_url,
            message: `Style guide "${styleGuideInfo.name}" created successfully`
          },
          action: 'create_style_guide',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create style guide',
        action: 'create_style_guide',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_style_guide',
        platform: 'figma'
      };
    }
  }

  /**
   * Search files
   */
  private async searchFiles(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search files dashboard"',
          action: 'search_files',
          platform: 'figma'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/figma/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'files',
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            files: data.files,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'search_files',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search files',
        action: 'search_files',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_files',
        platform: 'figma'
      };
    }
  }

  /**
   * List users
   */
  private async listUsers(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const teamId = this.extractTeamId(command, context);
      const filters = this.extractUserFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/figma/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          team_id: teamId,
          include_guests: filters.includeGuests,
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
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list users',
        action: 'list_users',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_users',
        platform: 'figma'
      };
    }
  }

  /**
   * Get user profile
   */
  private async getUserProfile(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/figma/user/profile`, {
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
            organization: data.organization
          },
          action: 'get_user_profile',
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to get user profile',
        action: 'get_user_profile',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'get_user_profile',
        platform: 'figma'
      };
    }
  }

  /**
   * Global search across Figma
   */
  private async globalSearch(command: string, context?: any): Promise<FigmaSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search project design"',
          action: 'global_search',
          platform: 'figma'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/figma/search`, {
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
          platform: 'figma'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search Figma',
        action: 'global_search',
        platform: 'figma'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'global_search',
        platform: 'figma'
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
    const teamMatch = command.match(/(?:team)\s+["']?([^"']+)["']?/i);
    if (teamMatch) {
      // In real implementation, this would resolve team name to ID
      return teamMatch[1];
    }

    return null;
  }

  private extractFileKey(command: string, context?: any): string | null {
    // First check context for file reference
    if (context?.fileKey) return context.fileKey;
    if (context?.file?.key) return context.file.key;

    // Extract from command
    const fileMatch = command.match(/(?:file)\s+["']?([^"']+)["']?/i);
    if (fileMatch) {
      // In real implementation, this would resolve file name to key
      return fileMatch[1];
    }

    return null;
  }

  private extractIncludeArchived(command: string): boolean {
    return command.includes('archived') || command.includes('deleted');
  }

  private extractUserFilters(command: string): any {
    const filters: any = {};

    if (command.includes('guests')) {
      filters.includeGuests = true;
    }

    if (command.includes('inactive')) {
      filters.includeInactive = true;
    }

    if (command.includes('active')) {
      filters.includeActive = true;
    }

    return filters;
  }

  private extractDesignInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:design|file)\s+(?:with\s+(?:title|name)|titled?)\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.name = titleMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    // Extract team/project
    const teamMatch = command.match(/(?:in|within)\s+team\s+["']?([^"']+)["']?/i);
    if (teamMatch) {
      info.team_id = teamMatch[1];
    }

    const projectMatch = command.match(/(?:in|within)\s+project\s+["']?([^"']+)["']?/i);
    if (projectMatch) {
      info.project_id = projectMatch[1];
    }

    // Extract from context
    if (context?.teamId) info.team_id = context.teamId;
    if (context?.projectId) info.project_id = context.projectId;

    return info;
  }

  private extractWireframeInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:wireframe)\s+(?:titled?)?\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.name = titleMatch[1];
    }

    // Extract type
    const typeMatch = command.match(/(?:type|kind)\s+(["']?\w+["']?)/i);
    if (typeMatch) {
      info.wireframe_type = typeMatch[1].replace(/["']/g, '');
    }

    // Extract device
    const deviceMatch = command.match(/(?:for|on)\s+(desktop|mobile|tablet|web)/i);
    if (deviceMatch) {
      info.device = deviceMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    return info;
  }

  private extractIconInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:icon)\s+(?:titled?)?\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.name = titleMatch[1];
    }

    // Extract size
    const sizeMatch = command.match(/(?:size|dimension)\s+(\d+(?:x\d+)?)/i);
    if (sizeMatch) {
      info.size = sizeMatch[1].includes('x') ? sizeMatch[1] : `${sizeMatch[1]}x${sizeMatch[1]}`;
    }

    // Extract style
    const styleMatch = command.match(/(?:style|type)\s+(filled|outline|duotone|rounded|sharp)/i);
    if (styleMatch) {
      info.style = styleMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    return info;
  }

  private extractStyleGuideInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:style\s*guide)\s+(?:titled?)?\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.name = titleMatch[1];
    }

    // Extract sections
    const sectionsMatch = command.match(/(?:sections|includes?)\s+["']([^"']+)["']/i);
    if (sectionsMatch) {
      info.sections = sectionsMatch[1].split(',').map((section: string) => section.trim());
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    return info;
  }

  // Summary generators
  
  private generateFilesSummary(files: any[]): string {
    const total = files.length;
    const archivedCount = files.filter(f => f.content_readonly || f.archived).length;
    const modifiedTodayCount = files.filter(f => {
      const lastMod = new Date(f.last_modified);
      const today = new Date();
      return lastMod.toDateString() === today.toDateString();
    }).length;

    return `Found ${total} files: ${archivedCount} read-only/archived, ${modifiedTodayCount} modified today`;
  }

  private generateComponentsSummary(components: any[]): string {
    const total = components.length;
    const types = components.reduce((acc, comp) => {
      acc[comp.component_type] = (acc[comp.component_type] || 0) + 1;
      return acc;
    }, {});

    const typeInfo = Object.entries(types).map(([type, count]) => `${count} ${type}s`).join(', ');

    return `Found ${total} components: ${typeInfo}`;
  }

  private generateTeamsSummary(teams: any[]): string {
    const total = teams.length;
    const totalMembers = teams.reduce((sum, team) => sum + (team.users?.length || 0), 0);

    return `Found ${total} teams with ${totalMembers} total members`;
  }

  private generateProjectsSummary(projects: any[]): string {
    const total = projects.length;
    const totalFiles = projects.reduce((sum, proj) => sum + (proj.files?.length || 0), 0);

    return `Found ${total} projects with ${totalFiles} total files`;
  }

  private generateUsersSummary(users: any[]): string {
    const total = users.length;
    const adminCount = users.filter(u => u.role === 'admin').length;
    const guestCount = users.filter(u => u.role === 'guest').length;

    return `Found ${total} users: ${adminCount} admins, ${guestCount} guests`;
  }
}

// Export singleton instance
export const enhancedFigmaSkills = new EnhancedFigmaSkills();

// Export types
export type { FigmaSkillResult };