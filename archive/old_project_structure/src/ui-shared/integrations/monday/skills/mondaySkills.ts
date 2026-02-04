/**
 * Monday.com Skills Service
 * Complete API client for Monday.com Work OS operations
 */

import { 
  MondayUser, MondayWorkspace, MondayTeam, MondayBoard, MondayColumn, MondayGroup,
  MondayItem, MondayUpdate, MondayNotification, MondayFile, MondayReply,
  MondayView, MondayTag, MondayActivity, MondayForm, MondayFormSubmission,
  MondayAutomation, MondayConfig
} from '../components/MondayManager';

// API Configuration
const API_BASE_URL = '/api/monday';
const DEFAULT_TIMEOUT = 30000;

// Response Types
interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp?: string;
}

interface PaginatedResponse<T = any> extends ApiResponse<T> {
  count?: number;
  total?: number;
  page?: number;
  pageSize?: number;
}

// Error Types
export class MondayApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public endpoint?: string,
    public details?: any
  ) {
    super(message);
    this.name = 'MondayApiError';
  }
}

// Utility Functions
const handleResponse = async <T = any>(response: Response): Promise<T> => {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.error || errorData.message || errorMessage;
    } catch (e) {
      // Ignore JSON parsing errors for error response
    }
    throw new MondayApiError(errorMessage, response.status, response.url);
  }

  const data = await response.json();
  if (!data.success) {
    throw new MondayApiError(data.error || 'API request failed', undefined, response.url, data);
  }

  return data.data || data;
};

const makeRequest = async <T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> => {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const config: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT),
  };

  return fetch(url, config).then(handleResponse<T>);
};

// Main Skills Service Class
export class MondaySkillsService {
  private config: MondayConfig;
  private apiBase: string;

  constructor(config: MondayConfig) {
    this.config = config;
    this.apiBase = API_BASE_URL;
  }

  // ==============================
  // AUTHENTICATION OPERATIONS
  // ==============================

  /**
   * Check authentication status
   */
  async checkAuthStatus(): Promise<ApiResponse> {
    return makeRequest('/auth/status');
  }

  /**
   * Register integration
   */
  async registerIntegration(config: MondayConfig): Promise<ApiResponse> {
    return makeRequest('/integration/register', {
      method: 'POST',
      body: JSON.stringify({ config }),
    });
  }

  /**
   * Get integration status
   */
  async getIntegrationStatus(): Promise<ApiResponse> {
    return makeRequest('/integration/status');
  }

  /**
   * Unregister integration
   */
  async unregisterIntegration(): Promise<ApiResponse> {
    return makeRequest('/integration/unregister', {
      method: 'POST',
    });
  }

  // ==============================
  // WORKSPACE OPERATIONS
  // ==============================

  /**
   * Get all workspaces
   */
  async getWorkspaces(limit: number = 50): Promise<PaginatedResponse<MondayWorkspace[]>> {
    return makeRequest(`/workspaces?limit=${limit}`);
  }

  /**
   * Get workspace by ID
   */
  async getWorkspace(workspaceId: string): Promise<ApiResponse<MondayWorkspace>> {
    return makeRequest(`/workspaces/${workspaceId}`);
  }

  /**
   * Create new workspace
   */
  async createWorkspace(workspaceData: Partial<MondayWorkspace>): Promise<ApiResponse<MondayWorkspace>> {
    return makeRequest('/workspaces', {
      method: 'POST',
      body: JSON.stringify(workspaceData),
    });
  }

  /**
   * Update workspace
   */
  async updateWorkspace(workspaceId: string, workspaceData: Partial<MondayWorkspace>): Promise<ApiResponse<MondayWorkspace>> {
    return makeRequest(`/workspaces/${workspaceId}`, {
      method: 'PUT',
      body: JSON.stringify(workspaceData),
    });
  }

  /**
   * Delete workspace
   */
  async deleteWorkspace(workspaceId: string): Promise<ApiResponse> {
    return makeRequest(`/workspaces/${workspaceId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // TEAM OPERATIONS
  // ==============================

  /**
   * Get teams
   */
  async getTeams(workspaceId?: string, limit: number = 50): Promise<PaginatedResponse<MondayTeam[]>> {
    const params = workspaceId ? `?workspace_id=${workspaceId}&limit=${limit}` : `?limit=${limit}`;
    return makeRequest(`/teams${params}`);
  }

  /**
   * Get team by ID
   */
  async getTeam(teamId: string): Promise<ApiResponse<MondayTeam>> {
    return makeRequest(`/teams/${teamId}`);
  }

  /**
   * Create new team
   */
  async createTeam(teamData: Partial<MondayTeam>): Promise<ApiResponse<MondayTeam>> {
    return makeRequest('/teams', {
      method: 'POST',
      body: JSON.stringify(teamData),
    });
  }

  /**
   * Update team
   */
  async updateTeam(teamId: string, teamData: Partial<MondayTeam>): Promise<ApiResponse<MondayTeam>> {
    return makeRequest(`/teams/${teamId}`, {
      method: 'PUT',
      body: JSON.stringify(teamData),
    });
  }

  /**
   * Delete team
   */
  async deleteTeam(teamId: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Add team member
   */
  async addTeamMember(teamId: string, userId: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/members`, {
      method: 'POST',
      body: JSON.stringify({ userId }),
    });
  }

  /**
   * Remove team member
   */
  async removeTeamMember(teamId: string, userId: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // BOARD OPERATIONS
  // ==============================

  /**
   * Get all boards
   */
  async getBoards(workspaceId?: string, teamId?: string, limit: number = 50): Promise<PaginatedResponse<MondayBoard[]>> {
    const params = new URLSearchParams();
    if (workspaceId) params.append('workspace_id', workspaceId);
    if (teamId) params.append('team_id', teamId);
    if (limit) params.append('limit', limit.toString());

    return makeRequest(`/boards?${params}`);
  }

  /**
   * Get board by ID
   */
  async getBoard(boardId: string): Promise<ApiResponse<MondayBoard>> {
    return makeRequest(`/boards/${boardId}`);
  }

  /**
   * Create new board
   */
  async createBoard(boardData: Partial<MondayBoard>): Promise<ApiResponse<MondayBoard>> {
    return makeRequest('/boards', {
      method: 'POST',
      body: JSON.stringify(boardData),
    });
  }

  /**
   * Update board
   */
  async updateBoard(boardId: string, boardData: Partial<MondayBoard>): Promise<ApiResponse<MondayBoard>> {
    return makeRequest(`/boards/${boardId}`, {
      method: 'PUT',
      body: JSON.stringify(boardData),
    });
  }

  /**
   * Delete board
   */
  async deleteBoard(boardId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Duplicate board
   */
  async duplicateBoard(boardId: string, options: {
    name?: string;
    includeItems?: boolean;
    includeColumns?: boolean;
    includeGroups?: boolean;
  }): Promise<ApiResponse<MondayBoard>> {
    return makeRequest(`/boards/${boardId}/duplicate`, {
      method: 'POST',
      body: JSON.stringify(options),
    });
  }

  /**
   * Archive board
   */
  async archiveBoard(boardId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/archive`, {
      method: 'POST',
    });
  }

  /**
   * Unarchive board
   */
  async unarchiveBoard(boardId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/unarchive`, {
      method: 'POST',
    });
  }

  /**
   * Get board subscribers
   */
  async getBoardSubscribers(boardId: string, limit: number = 50): Promise<PaginatedResponse<MondayUser[]>> {
    return makeRequest(`/boards/${boardId}/subscribers?limit=${limit}`);
  }

  /**
   * Add board subscriber
   */
  async addBoardSubscriber(boardId: string, userId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/subscribers`, {
      method: 'POST',
      body: JSON.stringify({ userId }),
    });
  }

  /**
   * Remove board subscriber
   */
  async removeBoardSubscriber(boardId: string, userId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/subscribers/${userId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // COLUMN OPERATIONS
  // ==============================

  /**
   * Get board columns
   */
  async getBoardColumns(boardId: string): Promise<PaginatedResponse<MondayColumn[]>> {
    return makeRequest(`/boards/${boardId}/columns`);
  }

  /**
   * Get column by ID
   */
  async getColumn(boardId: string, columnId: string): Promise<ApiResponse<MondayColumn>> {
    return makeRequest(`/boards/${boardId}/columns/${columnId}`);
  }

  /**
   * Create new column
   */
  async createColumn(boardId: string, columnData: Partial<MondayColumn>): Promise<ApiResponse<MondayColumn>> {
    return makeRequest(`/boards/${boardId}/columns`, {
      method: 'POST',
      body: JSON.stringify(columnData),
    });
  }

  /**
   * Update column
   */
  async updateColumn(boardId: string, columnId: string, columnData: Partial<MondayColumn>): Promise<ApiResponse<MondayColumn>> {
    return makeRequest(`/boards/${boardId}/columns/${columnId}`, {
      method: 'PUT',
      body: JSON.stringify(columnData),
    });
  }

  /**
   * Delete column
   */
  async deleteColumn(boardId: string, columnId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/columns/${columnId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Reorder columns
   */
  async reorderColumns(boardId: string, columnIds: string[]): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/columns/reorder`, {
      method: 'POST',
      body: JSON.stringify({ column_ids: columnIds }),
    });
  }

  // ==============================
  // GROUP OPERATIONS
  // ==============================

  /**
   * Get board groups
   */
  async getBoardGroups(boardId: string): Promise<PaginatedResponse<MondayGroup[]>> {
    return makeRequest(`/boards/${boardId}/groups`);
  }

  /**
   * Get group by ID
   */
  async getGroup(boardId: string, groupId: string): Promise<ApiResponse<MondayGroup>> {
    return makeRequest(`/boards/${boardId}/groups/${groupId}`);
  }

  /**
   * Create new group
   */
  async createGroup(boardId: string, groupData: Partial<MondayGroup>): Promise<ApiResponse<MondayGroup>> {
    return makeRequest(`/boards/${boardId}/groups`, {
      method: 'POST',
      body: JSON.stringify(groupData),
    });
  }

  /**
   * Update group
   */
  async updateGroup(boardId: string, groupId: string, groupData: Partial<MondayGroup>): Promise<ApiResponse<MondayGroup>> {
    return makeRequest(`/boards/${boardId}/groups/${groupId}`, {
      method: 'PUT',
      body: JSON.stringify(groupData),
    });
  }

  /**
   * Delete group
   */
  async deleteGroup(boardId: string, groupId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/groups/${groupId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Reorder groups
   */
  async reorderGroups(boardId: string, groupIds: string[]): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/groups/reorder`, {
      method: 'POST',
      body: JSON.stringify({ group_ids: groupIds }),
    });
  }

  // ==============================
  // ITEM OPERATIONS
  // ==============================

  /**
   * Get board items
   */
  async getBoardItems(boardId: string, options: {
    limit?: number;
    groupId?: string;
    columnId?: string;
    columnValue?: any;
    search?: string;
    sortBy?: string;
    sortDirection?: 'asc' | 'desc';
  } = {}): Promise<PaginatedResponse<MondayItem[]>> {
    const params = new URLSearchParams();
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.groupId) params.append('group_id', options.groupId);
    if (options.columnId) params.append('column_id', options.columnId);
    if (options.columnValue) params.append('column_value', JSON.stringify(options.columnValue));
    if (options.search) params.append('search', options.search);
    if (options.sortBy) params.append('sort_by', options.sortBy);
    if (options.sortDirection) params.append('sort_direction', options.sortDirection);

    return makeRequest(`/boards/${boardId}/items?${params}`);
  }

  /**
   * Get item by ID
   */
  async getItem(boardId: string, itemId: string): Promise<ApiResponse<MondayItem>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}`);
  }

  /**
   * Create new item
   */
  async createItem(boardId: string, itemData: {
    name: string;
    groupId?: string;
    columnValues?: Record<string, any>;
    subscribers?: string[];
    parentItemId?: string;
  }): Promise<ApiResponse<MondayItem>> {
    return makeRequest(`/boards/${boardId}/items`, {
      method: 'POST',
      body: JSON.stringify(itemData),
    });
  }

  /**
   * Update item
   */
  async updateItem(boardId: string, itemId: string, itemData: {
    name?: string;
    columnValues?: Record<string, any>;
    subscribers?: string[];
    groupId?: string;
  }): Promise<ApiResponse<MondayItem>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(itemData),
    });
  }

  /**
   * Delete item
   */
  async deleteItem(boardId: string, itemId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Move item to group
   */
  async moveItemToGroup(boardId: string, itemId: string, groupId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/move`, {
      method: 'POST',
      body: JSON.stringify({ group_id: groupId }),
    });
  }

  /**
   * Copy item
   */
  async copyItem(boardId: string, itemId: string, options: {
    groupId?: string;
    includeUpdates?: boolean;
    includeSubscribers?: boolean;
    includeFiles?: boolean;
  }): Promise<ApiResponse<MondayItem>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/copy`, {
      method: 'POST',
      body: JSON.stringify(options),
    });
  }

  /**
   * Archive item
   */
  async archiveItem(boardId: string, itemId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/archive`, {
      method: 'POST',
    });
  }

  /**
   * Unarchive item
   */
  async unarchiveItem(boardId: string, itemId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/unarchive`, {
      method: 'POST',
    });
  }

  /**
   * Get item subscribers
   */
  async getItemSubscribers(boardId: string, itemId: string): Promise<PaginatedResponse<MondayUser[]>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/subscribers`);
  }

  /**
   * Add item subscriber
   */
  async addItemSubscriber(boardId: string, itemId: string, userId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/subscribers`, {
      method: 'POST',
      body: JSON.stringify({ userId }),
    });
  }

  /**
   * Remove item subscriber
   */
  async removeItemSubscriber(boardId: string, itemId: string, userId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/subscribers/${userId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // SUBITEM OPERATIONS
  // ==============================

  /**
   * Get subitems
   */
  async getSubitems(boardId: string, parentId: string): Promise<PaginatedResponse<MondayItem[]>> {
    return makeRequest(`/boards/${boardId}/items/${parentId}/subitems`);
  }

  /**
   * Create subitem
   */
  async createSubitem(boardId: string, parentId: string, itemData: {
    name: string;
    columnValues?: Record<string, any>;
  }): Promise<ApiResponse<MondayItem>> {
    return makeRequest(`/boards/${boardId}/items/${parentId}/subitems`, {
      method: 'POST',
      body: JSON.stringify(itemData),
    });
  }

  // ==============================
  // UPDATE OPERATIONS
  // ==============================

  /**
   * Get item updates
   */
  async getItemUpdates(boardId: string, itemId: string, limit: number = 50): Promise<PaginatedResponse<MondayUpdate[]>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates?limit=${limit}`);
  }

  /**
   * Create update
   */
  async createUpdate(boardId: string, itemId: string, updateData: {
    body: string;
    files?: File[];
    isPinned?: boolean;
  }): Promise<ApiResponse<MondayUpdate>> {
    const formData = new FormData();
    formData.append('body', updateData.body);
    if (updateData.isPinned !== undefined) {
      formData.append('is_pinned', updateData.isPinned.toString());
    }
    if (updateData.files) {
      updateData.files.forEach((file, index) => {
        formData.append(`files[${index}]`, file);
      });
    }

    return makeRequest(`/boards/${boardId}/items/${itemId}/updates`, {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  /**
   * Get update by ID
   */
  async getUpdate(boardId: string, itemId: string, updateId: string): Promise<ApiResponse<MondayUpdate>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}`);
  }

  /**
   * Update update
   */
  async updateUpdate(boardId: string, itemId: string, updateId: string, updateData: {
    body?: string;
    isPinned?: boolean;
  }): Promise<ApiResponse<MondayUpdate>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}`, {
      method: 'PUT',
      body: JSON.stringify(updateData),
    });
  }

  /**
   * Delete update
   */
  async deleteUpdate(boardId: string, itemId: string, updateId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Pin update
   */
  async pinUpdate(boardId: string, itemId: string, updateId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}/pin`, {
      method: 'POST',
    });
  }

  /**
   * Unpin update
   */
  async unpinUpdate(boardId: string, itemId: string, updateId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}/unpin`, {
      method: 'POST',
    });
  }

  // ==============================
  // REPLY OPERATIONS
  // ==============================

  /**
   * Get update replies
   */
  async getUpdateReplies(boardId: string, itemId: string, updateId: string): Promise<PaginatedResponse<MondayReply[]>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}/replies`);
  }

  /**
   * Create reply
   */
  async createReply(boardId: string, itemId: string, updateId: string, replyData: {
    body: string;
    files?: File[];
  }): Promise<ApiResponse<MondayReply>> {
    const formData = new FormData();
    formData.append('body', replyData.body);
    if (replyData.files) {
      replyData.files.forEach((file, index) => {
        formData.append(`files[${index}]`, file);
      });
    }

    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}/replies`, {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  /**
   * Delete reply
   */
  async deleteReply(boardId: string, itemId: string, updateId: string, replyId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/updates/${updateId}/replies/${replyId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // FILE OPERATIONS
  // ==============================

  /**
   * Get files
   */
  async getFiles(boardId: string, itemId?: string, updateId?: string): Promise<PaginatedResponse<MondayFile[]>> {
    const params = new URLSearchParams();
    if (itemId) params.append('item_id', itemId);
    if (updateId) params.append('update_id', updateId);

    return makeRequest(`/boards/${boardId}/files?${params}`);
  }

  /**
   * Upload file
   */
  async uploadFile(boardId: string, fileData: {
    file: File;
    itemId?: string;
    updateId?: string;
    description?: string;
  }): Promise<ApiResponse<MondayFile>> {
    const formData = new FormData();
    formData.append('file', fileData.file);
    if (fileData.itemId) formData.append('item_id', fileData.itemId);
    if (fileData.updateId) formData.append('update_id', fileData.updateId);
    if (fileData.description) formData.append('description', fileData.description);

    return makeRequest(`/boards/${boardId}/files`, {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  /**
   * Download file
   */
  async downloadFile(fileId: string): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/files/${fileId}/download`);
    if (!response.ok) {
      throw new MondayApiError(`Download failed: ${response.statusText}`, response.status);
    }
    return response.blob();
  }

  /**
   * Delete file
   */
  async deleteFile(fileId: string): Promise<ApiResponse> {
    return makeRequest(`/files/${fileId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Get file thumbnails
   */
  async getFileThumbnails(fileId: string): Promise<ApiResponse> {
    return makeRequest(`/files/${fileId}/thumbnails`);
  }

  // ==============================
  // VIEW OPERATIONS
  // ==============================

  /**
   * Get board views
   */
  async getBoardViews(boardId: string): Promise<PaginatedResponse<MondayView[]>> {
    return makeRequest(`/boards/${boardId}/views`);
  }

  /**
   * Get view by ID
   */
  async getView(boardId: string, viewId: string): Promise<ApiResponse<MondayView>> {
    return makeRequest(`/boards/${boardId}/views/${viewId}`);
  }

  /**
   * Create view
   */
  async createView(boardId: string, viewData: Partial<MondayView>): Promise<ApiResponse<MondayView>> {
    return makeRequest(`/boards/${boardId}/views`, {
      method: 'POST',
      body: JSON.stringify(viewData),
    });
  }

  /**
   * Update view
   */
  async updateView(boardId: string, viewId: string, viewData: Partial<MondayView>): Promise<ApiResponse<MondayView>> {
    return makeRequest(`/boards/${boardId}/views/${viewId}`, {
      method: 'PUT',
      body: JSON.stringify(viewData),
    });
  }

  /**
   * Delete view
   */
  async deleteView(boardId: string, viewId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/views/${viewId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Set default view
   */
  async setDefaultView(boardId: string, viewId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/views/${viewId}/default`, {
      method: 'POST',
    });
  }

  // ==============================
  // AUTOMATION OPERATIONS
  // ==============================

  /**
   * Get board automations
   */
  async getBoardAutomations(boardId: string): Promise<PaginatedResponse<MondayAutomation[]>> {
    return makeRequest(`/boards/${boardId}/automations`);
  }

  /**
   * Get automation by ID
   */
  async getAutomation(boardId: string, automationId: string): Promise<ApiResponse<MondayAutomation>> {
    return makeRequest(`/boards/${boardId}/automations/${automationId}`);
  }

  /**
   * Create automation
   */
  async createAutomation(boardId: string, automationData: Partial<MondayAutomation>): Promise<ApiResponse<MondayAutomation>> {
    return makeRequest(`/boards/${boardId}/automations`, {
      method: 'POST',
      body: JSON.stringify(automationData),
    });
  }

  /**
   * Update automation
   */
  async updateAutomation(boardId: string, automationId: string, automationData: Partial<MondayAutomation>): Promise<ApiResponse<MondayAutomation>> {
    return makeRequest(`/boards/${boardId}/automations/${automationId}`, {
      method: 'PUT',
      body: JSON.stringify(automationData),
    });
  }

  /**
   * Delete automation
   */
  async deleteAutomation(boardId: string, automationId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/automations/${automationId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Activate automation
   */
  async activateAutomation(boardId: string, automationId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/automations/${automationId}/activate`, {
      method: 'POST',
    });
  }

  /**
   * Deactivate automation
   */
  async deactivateAutomation(boardId: string, automationId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/automations/${automationId}/deactivate`, {
      method: 'POST',
    });
  }

  /**
   * Get automation execution history
   */
  async getAutomationExecutions(boardId: string, automationId: string, limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/boards/${boardId}/automations/${automationId}/executions?limit=${limit}`);
  }

  // ==============================
  // FORM OPERATIONS
  // ==============================

  /**
   * Get board forms
   */
  async getBoardForms(boardId: string): Promise<PaginatedResponse<MondayForm[]>> {
    return makeRequest(`/boards/${boardId}/forms`);
  }

  /**
   * Get form by ID
   */
  async getForm(boardId: string, formId: string): Promise<ApiResponse<MondayForm>> {
    return makeRequest(`/boards/${boardId}/forms/${formId}`);
  }

  /**
   * Create form
   */
  async createForm(boardId: string, formData: Partial<MondayForm>): Promise<ApiResponse<MondayForm>> {
    return makeRequest(`/boards/${boardId}/forms`, {
      method: 'POST',
      body: JSON.stringify(formData),
    });
  }

  /**
   * Update form
   */
  async updateForm(boardId: string, formId: string, formData: Partial<MondayForm>): Promise<ApiResponse<MondayForm>> {
    return makeRequest(`/boards/${boardId}/forms/${formId}`, {
      method: 'PUT',
      body: JSON.stringify(formData),
    });
  }

  /**
   * Delete form
   */
  async deleteForm(boardId: string, formId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/forms/${formId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Publish form
   */
  async publishForm(boardId: string, formId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/forms/${formId}/publish`, {
      method: 'POST',
    });
  }

  /**
   * Unpublish form
   */
  async unpublishForm(boardId: string, formId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/forms/${formId}/unpublish`, {
      method: 'POST',
    });
  }

  /**
   * Get form submissions
   */
  async getFormSubmissions(boardId: string, formId: string): Promise<PaginatedResponse<MondayFormSubmission[]>> {
    return makeRequest(`/boards/${boardId}/forms/${formId}/submissions`);
  }

  // ==============================
  // TAG OPERATIONS
  // ==============================

  /**
   * Get board tags
   */
  async getBoardTags(boardId: string): Promise<PaginatedResponse<MondayTag[]>> {
    return makeRequest(`/boards/${boardId}/tags`);
  }

  /**
   * Create tag
   */
  async createTag(boardId: string, tagData: Partial<MondayTag>): Promise<ApiResponse<MondayTag>> {
    return makeRequest(`/boards/${boardId}/tags`, {
      method: 'POST',
      body: JSON.stringify(tagData),
    });
  }

  /**
   * Update tag
   */
  async updateTag(boardId: string, tagId: string, tagData: Partial<MondayTag>): Promise<ApiResponse<MondayTag>> {
    return makeRequest(`/boards/${boardId}/tags/${tagId}`, {
      method: 'PUT',
      body: JSON.stringify(tagData),
    });
  }

  /**
   * Delete tag
   */
  async deleteTag(boardId: string, tagId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/tags/${tagId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Apply tag to item
   */
  async applyTagToItem(boardId: string, itemId: string, tagId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/tags/${tagId}`, {
      method: 'POST',
    });
  }

  /**
   * Remove tag from item
   */
  async removeTagFromItem(boardId: string, itemId: string, tagId: string): Promise<ApiResponse> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/tags/${tagId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // ACTIVITY OPERATIONS
  // ==============================

  /**
   * Get board activity log
   */
  async getBoardActivity(boardId: string, options: {
    limit?: number;
    userId?: string;
    eventId?: string;
    from?: string;
    to?: string;
  } = {}): Promise<PaginatedResponse<MondayActivity[]>> {
    const params = new URLSearchParams();
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.userId) params.append('user_id', options.userId);
    if (options.eventId) params.append('event_id', options.eventId);
    if (options.from) params.append('from', options.from);
    if (options.to) params.append('to', options.to);

    return makeRequest(`/boards/${boardId}/activity?${params}`);
  }

  /**
   * Get item activity
   */
  async getItemActivity(boardId: string, itemId: string, limit: number = 50): Promise<PaginatedResponse<MondayActivity[]>> {
    return makeRequest(`/boards/${boardId}/items/${itemId}/activity?limit=${limit}`);
  }

  // ==============================
  // SEARCH OPERATIONS
  // ==============================

  /**
   * Search boards
   */
  async searchBoards(query: string, workspaceId?: string, limit: number = 20): Promise<PaginatedResponse<MondayBoard[]>> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (workspaceId) params.append('workspace_id', workspaceId);
    if (limit) params.append('limit', limit.toString());

    return makeRequest(`/search/boards?${params}`);
  }

  /**
   * Search items
   */
  async searchItems(query: string, options: {
    boardIds?: string[];
    workspaceId?: string;
    limit?: number;
    includeSubitems?: boolean;
  } = {}): Promise<PaginatedResponse<MondayItem[]>> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (options.boardIds) params.append('board_ids', options.boardIds.join(','));
    if (options.workspaceId) params.append('workspace_id', options.workspaceId);
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.includeSubitems !== undefined) params.append('include_subitems', options.includeSubitems.toString());

    return makeRequest(`/search/items?${params}`);
  }

  /**
   * Search updates
   */
  async searchUpdates(query: string, options: {
    boardIds?: string[];
    workspaceId?: string;
    limit?: number;
  } = {}): Promise<PaginatedResponse<MondayUpdate[]>> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (options.boardIds) params.append('board_ids', options.boardIds.join(','));
    if (options.workspaceId) params.append('workspace_id', options.workspaceId);
    if (options.limit) params.append('limit', options.limit.toString());

    return makeRequest(`/search/updates?${params}`);
  }

  /**
   * Global search
   */
  async globalSearch(query: string, options: {
    workspaceId?: string;
    boardIds?: string[];
    limit?: number;
    types?: ('boards' | 'items' | 'updates' | 'users')[];
  } = {}): Promise<ApiResponse> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (options.workspaceId) params.append('workspace_id', options.workspaceId);
    if (options.boardIds) params.append('board_ids', options.boardIds.join(','));
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.types) params.append('types', options.types.join(','));

    return makeRequest(`/search/global?${params}`);
  }

  // ==============================
  // USER OPERATIONS
  // ==============================

  /**
   * Get current user
   */
  async getCurrentUser(): Promise<ApiResponse<MondayUser>> {
    return makeRequest('/users/me');
  }

  /**
   * Get users
   */
  async getUsers(workspaceId?: string, limit: number = 50): Promise<PaginatedResponse<MondayUser[]>> {
    const params = workspaceId ? `?workspace_id=${workspaceId}&limit=${limit}` : `?limit=${limit}`;
    return makeRequest(`/users${params}`);
  }

  /**
   * Get user by ID
   */
  async getUser(userId: string): Promise<ApiResponse<MondayUser>> {
    return makeRequest(`/users/${userId}`);
  }

  /**
   * Search users
   */
  async searchUsers(query: string, workspaceId?: string, limit: number = 20): Promise<PaginatedResponse<MondayUser[]>> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (workspaceId) params.append('workspace_id', workspaceId);
    if (limit) params.append('limit', limit.toString());

    return makeRequest(`/users/search?${params}`);
  }

  // ==============================
  // WEBHOOK OPERATIONS
  // ==============================

  /**
   * Subscribe to webhook
   */
  async subscribeToWebhook(webhookData: {
    boardId?: string;
    event: string;
    config: {
      url: string;
      secret?: string;
      headers?: Record<string, string>;
    };
  }): Promise<ApiResponse> {
    return makeRequest('/webhooks/subscribe', {
      method: 'POST',
      body: JSON.stringify(webhookData),
    });
  }

  /**
   * Get webhooks
   */
  async getWebhooks(boardId?: string): Promise<PaginatedResponse<any[]>> {
    const params = boardId ? `?board_id=${boardId}` : '';
    return makeRequest(`/webhooks${params}`);
  }

  /**
   * Delete webhook
   */
  async deleteWebhook(webhookId: string): Promise<ApiResponse> {
    return makeRequest(`/webhooks/${webhookId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // IMPORT/EXPORT OPERATIONS
  // ==============================

  /**
   * Export board
   */
  async exportBoard(boardId: string, options: {
    format?: 'excel' | 'csv' | 'json';
    includeSubitems?: boolean;
    includeUpdates?: boolean;
    includeFiles?: boolean;
    columnIds?: string[];
  } = {}): Promise<Blob> {
    const params = new URLSearchParams();
    if (options.format) params.append('format', options.format);
    if (options.includeSubitems !== undefined) params.append('include_subitems', options.includeSubitems.toString());
    if (options.includeUpdates !== undefined) params.append('include_updates', options.includeUpdates.toString());
    if (options.includeFiles !== undefined) params.append('include_files', options.includeFiles.toString());
    if (options.columnIds) params.append('column_ids', options.columnIds.join(','));

    const response = await fetch(`${API_BASE_URL}/boards/${boardId}/export?${params}`);
    if (!response.ok) {
      throw new MondayApiError(`Export failed: ${response.statusText}`, response.status);
    }
    return response.blob();
  }

  /**
   * Import items
   */
  async importItems(boardId: string, importData: {
    file: File;
    format: 'excel' | 'csv' | 'json';
    groupId?: string;
    columnMapping?: Record<string, string>;
    options?: {
      createGroups?: boolean;
      createColumns?: boolean;
      skipFirstRow?: boolean;
    };
  }): Promise<ApiResponse> {
    const formData = new FormData();
    formData.append('file', importData.file);
    formData.append('format', importData.format);
    if (importData.groupId) formData.append('group_id', importData.groupId);
    if (importData.columnMapping) formData.append('column_mapping', JSON.stringify(importData.columnMapping));
    if (importData.options) formData.append('options', JSON.stringify(importData.options));

    return makeRequest(`/boards/${boardId}/import`, {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  // ==============================
  // UTILITIES
  // ==============================

  /**
   * Get API usage
   */
  async getApiUsage(): Promise<ApiResponse> {
    return makeRequest('/usage');
  }

  /**
   * Test connection
   */
  async testConnection(): Promise<ApiResponse> {
    return makeRequest('/test');
  }

  /**
   * Get supported features
   */
  async getSupportedFeatures(): Promise<ApiResponse> {
    return makeRequest('/features');
  }
}

// Factory function to create service instance
export const createMondaySkillsService = (config: MondayConfig): MondaySkillsService => {
  return new MondaySkillsService(config);
};

// Default export
export default MondaySkillsService;

// Export service instance with default configuration
export const mondaySkills = createMondaySkillsService({
  apiToken: '',
  version: '2023-10',
  baseUrl: 'https://api.monday.com/v2',
  timeout: 30000,
  maxRetries: 3
});

// Export types and error class
export { MondayApiError };
export type { ApiResponse, PaginatedResponse };