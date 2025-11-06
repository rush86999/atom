/**
 * Figma Desktop Integration TypeScript Definitions
 * Complete TypeScript interfaces and functions for Figma integration
 */

// Figma interfaces
interface FigmaFile {
  id: string;
  key: string;
  name: string;
  thumbnail_url: string;
  thumbnail_url_default?: string;
  content_readonly: boolean;
  editor_type: 'figma' | 'figjam';
  last_modified: string;
  workspace_id: string;
  workspace_name: string;
  branch_id?: string;
  url: string;
  share_url: string;
}

interface FigmaTeam {
  id: string;
  name: string;
  description?: string;
  profile_picture_url?: string;
  users: FigmaUser[];
  member_count: number;
}

interface FigmaUser {
  id: string;
  name: string;
  username: string;
  email: string;
  profile_picture_url?: string;
  department?: string;
  title?: string;
  organization_id?: string;
  role: string;
  can_edit: boolean;
  has_guests: boolean;
  is_active: boolean;
}

interface FigmaProject {
  id: string;
  name: string;
  description?: string;
  team_id: string;
  team_name: string;
  files: FigmaFile[];
  file_count: number;
}

interface FigmaComponent {
  id: string;
  component_key: string;
  file_key: string;
  node_id: string;
  name: string;
  description?: string;
  component_type: string;
  thumbnail_url?: string;
  created_at: string;
  modified_at: string;
  creator_id?: string;
  url: string;
}

interface FigmaUserProfile {
  id: string;
  name: string;
  username: string;
  email: string;
  profile_picture_url?: string;
  department?: string;
  title?: string;
  organization_id?: string;
  role: string;
  can_edit: boolean;
  has_guests: boolean;
  is_active: boolean;
  tokens_info: {
    scope: string;
    token_type: string;
    expires_at: string;
  };
  services: Record<string, {enabled: boolean; status: string}>;
  teams?: FigmaTeam[];
  usage_stats?: {
    files_created: number;
    components_created: number;
    projects_contributed: number;
    last_active: string;
    storage_used_bytes: number;
    api_calls_this_month: number;
  };
  permissions?: {
    can_create_files: boolean;
    can_edit_files: boolean;
    can_create_teams: boolean;
    can_manage_teams: boolean;
    can_use_libraries: boolean;
    can_create_libraries: boolean;
  };
}

interface FigmaSearchResult {
  object: 'file' | 'component' | 'project' | 'team' | 'user';
  id: string;
  title: string;
  url: string;
  highlighted_title?: string;
  snippet?: string;
  score?: number;
  matches?: {
    title: boolean;
    description: boolean;
  };
  thumbnail_url?: string;
  file_key?: string;
  component_key?: string;
  node_id?: string;
  editor_type?: string;
}

interface FigmaApiResponse<T = any> {
  ok: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    service?: string;
    endpoint?: string;
  };
  endpoint?: string;
  timestamp?: string;
  source?: string;
}

interface FigmaHealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version?: string;
  service_available?: boolean;
  database_available?: boolean;
  services?: Record<string, {status: string}>;
  components?: Record<string, {
    status: string;
    [key: string]: any;
  }>;
}

// Figma API service class
class FigmaDesktopService {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(baseUrl: string = 'http://localhost:8000', accessToken?: string) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Content-Type': 'application/json',
    };
    
    if (accessToken) {
      this.headers['Authorization'] = `Bearer ${accessToken}`;
    }
  }

  // User Management
  async getUserProfile(userId: string): Promise<FigmaApiResponse<FigmaUserProfile>> {
    const response = await fetch(`${this.baseUrl}/api/figma/users/profile?user_id=${userId}`);
    return response.json();
  }

  // File Management
  async getFiles(options: {
    userId: string;
    teamId?: string;
    projectId?: string;
    includeArchived?: boolean;
    limit?: number;
    offset?: number;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
    fileType?: 'figma' | 'figjam' | 'all';
  }): Promise<FigmaApiResponse<{files: FigmaFile[]; total_count: number}>> {
    const params = new URLSearchParams();
    params.append('user_id', options.userId);
    
    if (options.teamId) params.append('team_id', options.teamId);
    if (options.projectId) params.append('project_id', options.projectId);
    if (options.includeArchived) params.append('include_archived', 'true');
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());
    if (options.sortBy) params.append('sort_by', options.sortBy);
    if (options.sortOrder) params.append('sort_order', options.sortOrder);
    if (options.fileType) params.append('file_type', options.fileType);

    const response = await fetch(`${this.baseUrl}/api/figma/files?${params}`, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  // Enhanced File Management
  async getFilesEnhanced(options: {
    userId: string;
    teamId?: string;
    projectId?: string;
    includeArchived?: boolean;
    limit?: number;
    offset?: number;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
    fileType?: 'figma' | 'figjam' | 'all';
  }): Promise<FigmaApiResponse<{files: FigmaFile[]; total_count: number}>> {
    const response = await fetch(`${this.baseUrl}/api/integrations/figma/files`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        team_id: options.teamId,
        project_id: options.projectId,
        include_archived: options.includeArchived || false,
        limit: options.limit || 50,
        offset: options.offset || 0,
        sort_by: options.sortBy || 'last_modified',
        sort_order: options.sortOrder || 'desc',
        file_type: options.fileType || 'all'
      }),
    });
    return response.json();
  }

  // Team Management
  async getTeams(userId: string, limit?: number): Promise<FigmaApiResponse<{teams: FigmaTeam[]; total_count: number}>> {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    if (limit) params.append('limit', limit.toString());

    const response = await fetch(`${this.baseUrl}/api/figma/teams?${params}`, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  async getTeamsEnhanced(options: {
    userId: string;
    includeMembers?: boolean;
    includeProjects?: boolean;
    includeMemberRoles?: boolean;
    limit?: number;
  }): Promise<FigmaApiResponse<{teams: FigmaTeam[]; total_count: number}>> {
    const response = await fetch(`${this.baseUrl}/api/integrations/figma/teams`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        include_members: options.includeMembers !== false,
        include_projects: options.includeProjects !== false,
        include_member_roles: options.includeMemberRoles !== false,
        limit: options.limit || 50
      }),
    });
    return response.json();
  }

  // Project Management
  async getProjects(userId: string, teamId: string, limit?: number): Promise<FigmaApiResponse<{projects: FigmaProject[]; total_count: number}>> {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    params.append('team_id', teamId);
    if (limit) params.append('limit', limit.toString());

    const response = await fetch(`${this.baseUrl}/api/figma/projects?${params}`, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  async getProjectsEnhanced(options: {
    userId: string;
    teamId?: string;
    includeFileCounts?: boolean;
    includeThumbnails?: boolean;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
    limit?: number;
  }): Promise<FigmaApiResponse<{projects: FigmaProject[]; total_count: number}>> {
    const response = await fetch(`${this.baseUrl}/api/integrations/figma/projects`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        team_id: options.teamId,
        include_file_counts: options.includeFileCounts !== false,
        include_thumbnails: options.includeThumbnails !== false,
        sort_by: options.sortBy || 'name',
        sort_order: options.sortOrder || 'asc',
        limit: options.limit || 50
      }),
    });
    return response.json();
  }

  // Component Management
  async getComponents(userId: string, fileKey: string, limit?: number): Promise<FigmaApiResponse<{components: FigmaComponent[]; total_count: number}>> {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    params.append('file_key', fileKey);
    if (limit) params.append('limit', limit.toString());

    const response = await fetch(`${this.baseUrl}/api/figma/components?${params}`, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  async getComponentsEnhanced(options: {
    userId: string;
    fileKey?: string;
    teamId?: string;
    includeVariants?: boolean;
    includeMetadata?: boolean;
    componentType?: 'component' | 'variant' | 'all';
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
    limit?: number;
  }): Promise<FigmaApiResponse<{components: FigmaComponent[]; total_count: number}>> {
    const response = await fetch(`${this.baseUrl}/api/integrations/figma/components`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        file_key: options.fileKey,
        team_id: options.teamId,
        include_variants: options.includeVariants !== false,
        include_metadata: options.includeMetadata !== false,
        component_type: options.componentType || 'all',
        sort_by: options.sortBy || 'name',
        sort_order: options.sortOrder || 'asc',
        limit: options.limit || 100
      }),
    });
    return response.json();
  }

  // Search Functionality
  async search(options: {
    userId: string;
    query: string;
    searchType?: 'global' | 'files' | 'components';
    teamId?: string;
    limit?: number;
  }): Promise<FigmaApiResponse<{results: FigmaSearchResult[]; total_count: number}>> {
    const response = await fetch(`${this.baseUrl}/api/figma/search`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        query: options.query,
        search_type: options.searchType || 'global',
        team_id: options.teamId,
        limit: options.limit || 50
      }),
    });
    return response.json();
  }

  async searchEnhanced(options: {
    userId: string;
    query: string;
    searchType?: 'all' | 'files' | 'components' | 'projects';
    teamId?: string;
    fileTypes?: string[];
    includeThumbnails?: boolean;
    limit?: number;
  }): Promise<FigmaApiResponse<{results: FigmaSearchResult[]; total_count: number}>> {
    const response = await fetch(`${this.baseUrl}/api/integrations/figma/search`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        query: options.query,
        search_type: options.searchType || 'all',
        team_id: options.teamId,
        file_types: options.fileTypes || ['figma', 'figjam'],
        include_thumbnails: options.includeThumbnails !== false,
        limit: options.limit || 50
      }),
    });
    return response.json();
  }

  // Health Checks
  async getHealthStatus(userId?: string): Promise<FigmaApiResponse<FigmaHealthStatus>> {
    const url = userId 
      ? `${this.baseUrl}/api/figma/health/summary?user_id=${userId}`
      : `${this.baseUrl}/api/figma/health`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  async getDetailedHealthStatus(userId?: string): Promise<FigmaApiResponse<FigmaHealthStatus>> {
    const url = userId 
      ? `${this.baseUrl}/api/figma/health/detailed?user_id=${userId}`
      : `${this.baseUrl}/api/figma/health/detailed`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  // OAuth Management
  async getOAuthUrl(userId: string): Promise<FigmaApiResponse<{oauth_url: string; state: string; scopes: string[]}>> {
    const response = await fetch(`${this.baseUrl}/api/oauth/figma/url?user_id=${userId}`, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  async handleOAuthCallback(code: string, state: string): Promise<FigmaApiResponse<any>> {
    const response = await fetch(`${this.baseUrl}/api/oauth/figma/callback`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({ code, state }),
    });
    return response.json();
  }

  // Comments and Collaboration
  async addComment(options: {
    userId: string;
    fileKey: string;
    comment: string;
    position?: {x: number; y: number};
  }): Promise<FigmaApiResponse<any>> {
    const response = await fetch(`${this.baseUrl}/api/figma/comments`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        file_key: options.fileKey,
        comment: options.comment,
        position: options.position
      }),
    });
    return response.json();
  }

  async getFileVersions(userId: string, fileKey: string, limit?: number): Promise<FigmaApiResponse<any>> {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    params.append('file_key', fileKey);
    if (limit) params.append('limit', limit.toString());

    const response = await fetch(`${this.baseUrl}/api/figma/versions?${params}`, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }

  // Export Functionality
  async exportFile(options: {
    userId: string;
    fileKey: string;
    format: 'png' | 'jpg' | 'svg' | 'pdf';
  }): Promise<FigmaApiResponse<{export_url: string}>> {
    const response = await fetch(`${this.baseUrl}/api/figma/export`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        user_id: options.userId,
        file_key: options.fileKey,
        format: options.format
      }),
    });
    return response.json();
  }

  // Styles (Mock Implementation)
  async getStyles(userId: string, fileKey: string, limit?: number): Promise<FigmaApiResponse<any>> {
    const params = new URLSearchParams();
    params.append('user_id', userId);
    params.append('file_key', fileKey);
    if (limit) params.append('limit', limit.toString());

    const response = await fetch(`${this.baseUrl}/api/figma/styles?${params}`, {
      method: 'GET',
      headers: this.headers,
    });
    return response.json();
  }
}

// Export the service and interfaces
export {
  FigmaDesktopService,
  type FigmaFile,
  type FigmaTeam,
  type FigmaUser,
  type FigmaProject,
  type FigmaComponent,
  type FigmaUserProfile,
  type FigmaSearchResult,
  type FigmaApiResponse,
  type FigmaHealthStatus
};

// Create a default instance
export const figmaDesktopService = new FigmaDesktopService();