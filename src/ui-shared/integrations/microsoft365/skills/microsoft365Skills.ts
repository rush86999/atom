/**
 * Microsoft 365 Skills Service
 * Complete API client for Microsoft 365 unified platform operations
 */

import { Microsoft365User, Microsoft365Team, Microsoft365Channel, Microsoft365Message,
         Microsoft365Document, Microsoft365Event, Microsoft365Flow, Microsoft365Site,
         Microsoft365Analytics, Microsoft365Config } from '../components/Microsoft365Manager';

// API Configuration
const API_BASE_URL = '/api/m365';
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
export class Microsoft365ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public endpoint?: string,
    public details?: any
  ) {
    super(message);
    this.name = 'Microsoft365ApiError';
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
    throw new Microsoft365ApiError(errorMessage, response.status, response.url);
  }

  const data = await response.json();
  if (!data.success) {
    throw new Microsoft365ApiError(data.error || 'API request failed', undefined, response.url, data);
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
export class Microsoft365SkillsService {
  private config: Microsoft365Config;
  private apiBase: string;

  constructor(config: Microsoft365Config) {
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
   * Get service health status
   */
  async getServiceHealth(): Promise<ApiResponse> {
    return makeRequest('/health');
  }

  /**
   * Register integration
   */
  async registerIntegration(config: Microsoft365Config): Promise<ApiResponse> {
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
   * Get integration info
   */
  async getIntegrationInfo(): Promise<ApiResponse> {
    return makeRequest('/integration/info');
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
  // USER OPERATIONS
  // ==============================

  /**
   * Get all users
   */
  async getUsers(limit: number = 50, skip: number = 0): Promise<PaginatedResponse<Microsoft365User[]>> {
    return makeRequest(`/users?limit=${limit}&skip=${skip}`);
  }

  /**
   * Get user by ID
   */
  async getUser(userId: string): Promise<ApiResponse<Microsoft365User>> {
    return makeRequest(`/users/${userId}`);
  }

  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<ApiResponse<Microsoft365User>> {
    return makeRequest('/users/me');
  }

  /**
   * Search users
   */
  async searchUsers(query: string, limit: number = 20): Promise<PaginatedResponse<Microsoft365User[]>> {
    return makeRequest(`/users/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  }

  /**
   * Update user
   */
  async updateUser(userId: string, userData: Partial<Microsoft365User>): Promise<ApiResponse<Microsoft365User>> {
    return makeRequest(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    });
  }

  /**
   * Enable/disable user
   */
  async setUserStatus(userId: string, enabled: boolean): Promise<ApiResponse> {
    return makeRequest(`/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    });
  }

  // ==============================
  // TEAMS OPERATIONS
  // ==============================

  /**
   * Get all teams
   */
  async getTeams(limit: number = 50): Promise<PaginatedResponse<Microsoft365Team[]>> {
    return makeRequest(`/teams?limit=${limit}`);
  }

  /**
   * Get team by ID
   */
  async getTeam(teamId: string): Promise<ApiResponse<Microsoft365Team>> {
    return makeRequest(`/teams/${teamId}`);
  }

  /**
   * Create new team
   */
  async createTeam(teamData: Partial<Microsoft365Team>): Promise<ApiResponse<Microsoft365Team>> {
    return makeRequest('/teams', {
      method: 'POST',
      body: JSON.stringify(teamData),
    });
  }

  /**
   * Update team
   */
  async updateTeam(teamId: string, teamData: Partial<Microsoft365Team>): Promise<ApiResponse<Microsoft365Team>> {
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
   * Archive team
   */
  async archiveTeam(teamId: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/archive`, {
      method: 'POST',
    });
  }

  /**
   * Unarchive team
   */
  async unarchiveTeam(teamId: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/unarchive`, {
      method: 'POST',
    });
  }

  /**
   * Get team members
   */
  async getTeamMembers(teamId: string, limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/teams/${teamId}/members?limit=${limit}`);
  }

  /**
   * Add team member
   */
  async addTeamMember(teamId: string, userId: string, role: string = 'member'): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/members`, {
      method: 'POST',
      body: JSON.stringify({ userId, role }),
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

  /**
   * Update team member role
   */
  async updateTeamMemberRole(teamId: string, userId: string, role: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    });
  }

  // ==============================
  // CHANNEL OPERATIONS
  // ==============================

  /**
   * Get team channels
   */
  async getTeamChannels(teamId: string, limit: number = 50): Promise<PaginatedResponse<Microsoft365Channel[]>> {
    return makeRequest(`/teams/${teamId}/channels?limit=${limit}`);
  }

  /**
   * Get channel by ID
   */
  async getChannel(teamId: string, channelId: string): Promise<ApiResponse<Microsoft365Channel>> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}`);
  }

  /**
   * Create new channel
   */
  async createChannel(teamId: string, channelData: Partial<Microsoft365Channel>): Promise<ApiResponse<Microsoft365Channel>> {
    return makeRequest(`/teams/${teamId}/channels`, {
      method: 'POST',
      body: JSON.stringify(channelData),
    });
  }

  /**
   * Update channel
   */
  async updateChannel(teamId: string, channelId: string, channelData: Partial<Microsoft365Channel>): Promise<ApiResponse<Microsoft365Channel>> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}`, {
      method: 'PUT',
      body: JSON.stringify(channelData),
    });
  }

  /**
   * Delete channel
   */
  async deleteChannel(teamId: string, channelId: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Get channel messages
   */
  async getChannelMessages(teamId: string, channelId: string, limit: number = 50): Promise<PaginatedResponse<Microsoft365Message[]>> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}/messages?limit=${limit}`);
  }

  /**
   * Send message to channel
   */
  async sendChannelMessage(teamId: string, channelId: string, message: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}/message`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  /**
   * Get channel members
   */
  async getChannelMembers(teamId: string, channelId: string, limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}/members?limit=${limit}`);
  }

  /**
   * Add channel member
   */
  async addChannelMember(teamId: string, channelId: string, userId: string, role: string = 'member'): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}/members`, {
      method: 'POST',
      body: JSON.stringify({ userId, role }),
    });
  }

  /**
   * Remove channel member
   */
  async removeChannelMember(teamId: string, channelId: string, userId: string): Promise<ApiResponse> {
    return makeRequest(`/teams/${teamId}/channels/${channelId}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  // ==============================
  // MESSAGE OPERATIONS
  // ==============================

  /**
   * Get emails
   */
  async getEmails(folder: string = 'inbox', limit: number = 50): Promise<PaginatedResponse<Microsoft365Message[]>> {
    return makeRequest(`/emails?folder=${folder}&limit=${limit}`);
  }

  /**
   * Get message by ID
   */
  async getMessage(messageId: string): Promise<ApiResponse<Microsoft365Message>> {
    return makeRequest(`/messages/${messageId}`);
  }

  /**
   * Send email
   */
  async sendEmail(emailData: {
    to_addresses: string[];
    subject: string;
    body: string;
    cc_addresses?: string[];
    bcc_addresses?: string[];
    attachments?: any[];
  }): Promise<ApiResponse> {
    return makeRequest('/emails/send', {
      method: 'POST',
      body: JSON.stringify(emailData),
    });
  }

  /**
   * Reply to email
   */
  async replyToEmail(messageId: string, replyData: {
    body: string;
    replyAll?: boolean;
  }): Promise<ApiResponse> {
    return makeRequest(`/emails/${messageId}/reply`, {
      method: 'POST',
      body: JSON.stringify(replyData),
    });
  }

  /**
   * Forward email
   */
  async forwardEmail(messageId: string, forwardData: {
    to_addresses: string[];
    body?: string;
  }): Promise<ApiResponse> {
    return makeRequest(`/emails/${messageId}/forward`, {
      method: 'POST',
      body: JSON.stringify(forwardData),
    });
  }

  /**
   * Mark email as read/unread
   */
  async markEmail(messageId: string, read: boolean): Promise<ApiResponse> {
    return makeRequest(`/emails/${messageId}/read`, {
      method: 'PATCH',
      body: JSON.stringify({ read }),
    });
  }

  /**
   * Move email to folder
   */
  async moveEmail(messageId: string, folder: string): Promise<ApiResponse> {
    return makeRequest(`/emails/${messageId}/move`, {
      method: 'POST',
      body: JSON.stringify({ folder }),
    });
  }

  /**
   * Delete email
   */
  async deleteEmail(messageId: string): Promise<ApiResponse> {
    return makeRequest(`/emails/${messageId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Search emails
   */
  async searchEmails(query: string, folder: string = 'inbox', limit: number = 20): Promise<PaginatedResponse<Microsoft365Message[]>> {
    return makeRequest(`/emails/search?q=${encodeURIComponent(query)}&folder=${folder}&limit=${limit}`);
  }

  // ==============================
  // DOCUMENT OPERATIONS
  // ==============================

  /**
   * Get documents
   */
  async getDocuments(serviceType: string = 'onedrive', limit: number = 100): Promise<PaginatedResponse<Microsoft365Document[]>> {
    return makeRequest(`/documents?service_type=${serviceType}&limit=${limit}`);
  }

  /**
   * Get document by ID
   */
  async getDocument(documentId: string): Promise<ApiResponse<Microsoft365Document>> {
    return makeRequest(`/documents/${documentId}`);
  }

  /**
   * Upload document
   */
  async uploadDocument(fileData: {
    file_path: string;
    content: File | Blob;
    service_type?: string;
  }): Promise<ApiResponse<Microsoft365Document>> {
    const formData = new FormData();
    formData.append('file', fileData.content);
    formData.append('file_path', fileData.file_path);
    if (fileData.service_type) {
      formData.append('service_type', fileData.service_type);
    }

    return makeRequest('/documents/upload', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  /**
   * Update document metadata
   */
  async updateDocument(documentId: string, metadata: Partial<Microsoft365Document>): Promise<ApiResponse<Microsoft365Document>> {
    return makeRequest(`/documents/${documentId}`, {
      method: 'PUT',
      body: JSON.stringify(metadata),
    });
  }

  /**
   * Delete document
   */
  async deleteDocument(documentId: string): Promise<ApiResponse> {
    return makeRequest(`/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Download document
   */
  async downloadDocument(documentId: string): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/documents/${documentId}/download`);
    if (!response.ok) {
      throw new Microsoft365ApiError(`Download failed: ${response.statusText}`, response.status);
    }
    return response.blob();
  }

  /**
   * Share document
   */
  async shareDocument(documentId: string, shareData: {
    recipients: string[];
    permissions: string[];
    message?: string;
  }): Promise<ApiResponse> {
    return makeRequest(`/documents/${documentId}/share`, {
      method: 'POST',
      body: JSON.stringify(shareData),
    });
  }

  /**
   * Create sharing link
   */
  async createSharingLink(documentId: string, linkType: string = 'view'): Promise<ApiResponse> {
    return makeRequest(`/documents/${documentId}/sharelink`, {
      method: 'POST',
      body: JSON.stringify({ link_type: linkType }),
    });
  }

  /**
   * Search documents
   */
  async searchDocuments(query: string, serviceType: string = 'onedrive', limit: number = 20): Promise<PaginatedResponse<Microsoft365Document[]>> {
    return makeRequest(`/documents/search?q=${encodeURIComponent(query)}&service_type=${serviceType}&limit=${limit}`);
  }

  /**
   * Get document versions
   */
  async getDocumentVersions(documentId: string, limit: number = 10): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/documents/${documentId}/versions?limit=${limit}`);
  }

  // ==============================
  // CALENDAR OPERATIONS
  // ==============================

  /**
   * Get calendar events
   */
  async getCalendarEvents(options: {
    limit?: number;
    start_date?: string;
    end_date?: string;
  } = {}): Promise<PaginatedResponse<Microsoft365Event[]>> {
    const params = new URLSearchParams();
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.start_date) params.append('start_date', options.start_date);
    if (options.end_date) params.append('end_date', options.end_date);

    return makeRequest(`/calendar/events?${params}`);
  }

  /**
   * Get event by ID
   */
  async getCalendarEvent(eventId: string): Promise<ApiResponse<Microsoft365Event>> {
    return makeRequest(`/calendar/events/${eventId}`);
  }

  /**
   * Create calendar event
   */
  async createCalendarEvent(eventData: Partial<Microsoft365Event>): Promise<ApiResponse<Microsoft365Event>> {
    return makeRequest('/calendar/events', {
      method: 'POST',
      body: JSON.stringify(eventData),
    });
  }

  /**
   * Update calendar event
   */
  async updateCalendarEvent(eventId: string, eventData: Partial<Microsoft365Event>): Promise<ApiResponse<Microsoft365Event>> {
    return makeRequest(`/calendar/events/${eventId}`, {
      method: 'PUT',
      body: JSON.stringify(eventData),
    });
  }

  /**
   * Delete calendar event
   */
  async deleteCalendarEvent(eventId: string): Promise<ApiResponse> {
    return makeRequest(`/calendar/events/${eventId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Cancel calendar event
   */
  async cancelCalendarEvent(eventId: string, reason?: string): Promise<ApiResponse> {
    return makeRequest(`/calendar/events/${eventId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  /**
   * Accept meeting invitation
   */
  async acceptMeeting(eventId: string, response?: string): Promise<ApiResponse> {
    return makeRequest(`/calendar/events/${eventId}/accept`, {
      method: 'POST',
      body: JSON.stringify({ response }),
    });
  }

  /**
   * Decline meeting invitation
   */
  async declineMeeting(eventId: string, reason?: string): Promise<ApiResponse> {
    return makeRequest(`/calendar/events/${eventId}/decline`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  /**
   * Tentatively accept meeting
   */
  async tentativelyAcceptMeeting(eventId: string, response?: string): Promise<ApiResponse> {
    return makeRequest(`/calendar/events/${eventId}/tentative`, {
      method: 'POST',
      body: JSON.stringify({ response }),
    });
  }

  /**
   * Search calendar events
   */
  async searchCalendarEvents(query: string, limit: number = 20): Promise<PaginatedResponse<Microsoft365Event[]>> {
    return makeRequest(`/calendar/events/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  }

  // ==============================
  // POWER AUTOMATE OPERATIONS
  // ==============================

  /**
   * Get Power Automate flows
   */
  async getPowerAutomateFlows(environmentName?: string): Promise<PaginatedResponse<Microsoft365Flow[]>> {
    const params = environmentName ? `?environment_name=${environmentName}` : '';
    return makeRequest(`/power-automate/flows${params}`);
  }

  /**
   * Get flow by ID
   */
  async getPowerAutomateFlow(flowId: string): Promise<ApiResponse<Microsoft365Flow>> {
    return makeRequest(`/power-automate/flows/${flowId}`);
  }

  /**
   * Create Power Automate flow
   */
  async createPowerAutomateFlow(flowData: Partial<Microsoft365Flow>): Promise<ApiResponse<Microsoft365Flow>> {
    return makeRequest('/power-automate/flows', {
      method: 'POST',
      body: JSON.stringify(flowData),
    });
  }

  /**
   * Update Power Automate flow
   */
  async updatePowerAutomateFlow(flowId: string, flowData: Partial<Microsoft365Flow>): Promise<ApiResponse<Microsoft365Flow>> {
    return makeRequest(`/power-automate/flows/${flowId}`, {
      method: 'PUT',
      body: JSON.stringify(flowData),
    });
  }

  /**
   * Delete Power Automate flow
   */
  async deletePowerAutomateFlow(flowId: string): Promise<ApiResponse> {
    return makeRequest(`/power-automate/flows/${flowId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Enable/disable Power Automate flow
   */
  async setFlowStatus(flowId: string, status: 'enabled' | 'disabled'): Promise<ApiResponse> {
    return makeRequest(`/power-automate/flows/${flowId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  /**
   * Execute Power Automate flow
   */
  async executeFlow(flowId: string, inputs?: Record<string, any>): Promise<ApiResponse> {
    return makeRequest(`/power-automate/flows/${flowId}/execute`, {
      method: 'POST',
      body: JSON.stringify({ inputs }),
    });
  }

  /**
   * Get flow execution history
   */
  async getFlowExecutions(flowId: string, limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/power-automate/flows/${flowId}/executions?limit=${limit}`);
  }

  // ==============================
  // SHAREPOINT OPERATIONS
  // ==============================

  /**
   * Get SharePoint sites
   */
  async getSharePointSites(): Promise<PaginatedResponse<Microsoft365Site[]>> {
    return makeRequest('/sharepoint/sites');
  }

  /**
   * Get SharePoint site by ID
   */
  async getSharePointSite(siteId: string): Promise<ApiResponse<Microsoft365Site>> {
    return makeRequest(`/sharepoint/sites/${siteId}`);
  }

  /**
   * Create SharePoint site
   */
  async createSharePointSite(siteData: Partial<Microsoft365Site>): Promise<ApiResponse<Microsoft365Site>> {
    return makeRequest('/sharepoint/sites', {
      method: 'POST',
      body: JSON.stringify(siteData),
    });
  }

  /**
   * Update SharePoint site
   */
  async updateSharePointSite(siteId: string, siteData: Partial<Microsoft365Site>): Promise<ApiResponse<Microsoft365Site>> {
    return makeRequest(`/sharepoint/sites/${siteId}`, {
      method: 'PUT',
      body: JSON.stringify(siteData),
    });
  }

  /**
   * Delete SharePoint site
   */
  async deleteSharePointSite(siteId: string): Promise<ApiResponse> {
    return makeRequest(`/sharepoint/sites/${siteId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Get site documents
   */
  async getSiteDocuments(siteId: string, limit: number = 50): Promise<PaginatedResponse<Microsoft365Document[]>> {
    return makeRequest(`/sharepoint/sites/${siteId}/documents?limit=${limit}`);
  }

  /**
   * Get site members
   */
  async getSiteMembers(siteId: string, limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/sharepoint/sites/${siteId}/members?limit=${limit}`);
  }

  /**
   * Add site member
   */
  async addSiteMember(siteId: string, userData: {
    userId: string;
    role: string;
  }): Promise<ApiResponse> {
    return makeRequest(`/sharepoint/sites/${siteId}/members`, {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  // ==============================
  // WORKFLOW OPERATIONS
  // ==============================

  /**
   * Create cross-service workflow
   */
  async createCrossServiceWorkflow(workflowDefinition: Record<string, any>): Promise<ApiResponse> {
    return makeRequest('/workflows/create', {
      method: 'POST',
      body: JSON.stringify({ workflow_definition: workflowDefinition }),
    });
  }

  /**
   * Get workflows
   */
  async getWorkflows(limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/workflows?limit=${limit}`);
  }

  /**
   * Execute workflow
   */
  async executeWorkflow(workflowId: string, triggerData?: Record<string, any>): Promise<ApiResponse> {
    return makeRequest(`/workflows/${workflowId}/execute`, {
      method: 'POST',
      body: JSON.stringify({ trigger_data: triggerData }),
    });
  }

  /**
   * Get workflow executions
   */
  async getWorkflowExecutions(workflowId: string, limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/workflows/${workflowId}/executions?limit=${limit}`);
  }

  // ==============================
  // ANALYTICS OPERATIONS
  // ==============================

  /**
   * Get unified analytics
   */
  async getUnifiedAnalytics(options: {
    start_date?: string;
    end_date?: string;
  } = {}): Promise<ApiResponse<Microsoft365Analytics>> {
    const params = new URLSearchParams();
    if (options.start_date) params.append('start_date', options.start_date);
    if (options.end_date) params.append('end_date', options.end_date);

    return makeRequest(`/analytics/unified?${params}`);
  }

  /**
   * Get service analytics
   */
  async getServiceAnalytics(serviceName: string, options: {
    start_date?: string;
    end_date?: string;
    period?: string;
  } = {}): Promise<ApiResponse> {
    const params = new URLSearchParams();
    params.append('service', serviceName);
    if (options.start_date) params.append('start_date', options.start_date);
    if (options.end_date) params.append('end_date', options.end_date);
    if (options.period) params.append('period', options.period);

    return makeRequest(`/analytics/service?${params}`);
  }

  /**
   * Get usage metrics
   */
  async getUsageMetrics(): Promise<ApiResponse> {
    return makeRequest('/analytics/usage');
  }

  /**
   * Get performance metrics
   */
  async getPerformanceMetrics(): Promise<ApiResponse> {
    return makeRequest('/analytics/performance');
  }

  // ==============================
  // BATCH OPERATIONS
  // ==============================

  /**
   * Batch send emails
   */
  async batchSendEmails(emails: Array<{
    to_addresses: string[];
    subject: string;
    body: string;
    cc_addresses?: string[];
  }>): Promise<ApiResponse> {
    return makeRequest('/emails/batch', {
      method: 'POST',
      body: JSON.stringify({ emails }),
    });
  }

  /**
   * Batch upload documents
   */
  async batchUploadDocuments(files: Array<{
    file_path: string;
    content: File | Blob;
    service_type?: string;
  }>): Promise<ApiResponse> {
    const formData = new FormData();
    files.forEach((file, index) => {
      formData.append(`files[${index}]`, file.content);
      formData.append(`file_paths[${index}]`, file.file_path);
      if (file.service_type) {
        formData.append(`service_types[${index}]`, file.service_type);
      }
    });

    return makeRequest('/documents/batch', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  /**
   * Batch create calendar events
   */
  async batchCreateCalendarEvents(events: Partial<Microsoft365Event>[]): Promise<ApiResponse> {
    return makeRequest('/calendar/events/batch', {
      method: 'POST',
      body: JSON.stringify({ events }),
    });
  }

  // ==============================
  // SEARCH OPERATIONS
  // ==============================

  /**
   * Global search across all M365 services
   */
  async globalSearch(query: string, options: {
    services?: string[];
    limit?: number;
    filters?: Record<string, any>;
  } = {}): Promise<ApiResponse> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (options.services) params.append('services', options.services.join(','));
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.filters) params.append('filters', JSON.stringify(options.filters));

    return makeRequest(`/search/global?${params}`);
  }

  /**
   * Advanced search with filters
   */
  async advancedSearch(searchQuery: {
    query: string;
    filters: Record<string, any>;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    limit?: number;
  }): Promise<ApiResponse> {
    return makeRequest('/search/advanced', {
      method: 'POST',
      body: JSON.stringify(searchQuery),
    });
  }

  // ==============================
  // UTILITY OPERATIONS
  // ==============================

  /**
   * Get API limits and quotas
   */
  async getApiLimits(): Promise<ApiResponse> {
    return makeRequest('/limits');
  }

  /**
   * Get supported services
   */
  async getSupportedServices(): Promise<ApiResponse> {
    return makeRequest('/services');
  }

  /**
   * Test API connectivity
   */
  async testConnectivity(): Promise<ApiResponse> {
    return makeRequest('/test');
  }

  /**
   * Get webhook events
   */
  async getWebhookEvents(): Promise<ApiResponse> {
    return makeRequest('/webhooks/events');
  }

  /**
   * Subscribe to webhook events
   */
  async subscribeToWebhook(eventType: string, config: {
    callback_url: string;
    filters?: Record<string, any>;
  }): Promise<ApiResponse> {
    return makeRequest('/webhooks/subscribe', {
      method: 'POST',
      body: JSON.stringify({
        event_type: eventType,
        ...config,
      }),
    });
  }

  /**
   * Unsubscribe from webhook events
   */
  async unsubscribeFromWebhook(subscriptionId: string): Promise<ApiResponse> {
    return makeRequest(`/webhooks/${subscriptionId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Get recent activities
   */
  async getRecentActivities(limit: number = 50): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/activities/recent?limit=${limit}`);
  }

  /**
   * Export data
   */
  async exportData(options: {
    services?: string[];
    format?: string;
    date_range?: {
      start: string;
      end: string;
    };
  }): Promise<Blob> {
    const params = new URLSearchParams();
    if (options.services) params.append('services', options.services.join(','));
    if (options.format) params.append('format', options.format);
    if (options.date_range) {
      params.append('start_date', options.date_range.start);
      params.append('end_date', options.date_range.end);
    }

    const response = await fetch(`${API_BASE_URL}/export?${params}`);
    if (!response.ok) {
      throw new Microsoft365ApiError(`Export failed: ${response.statusText}`, response.status);
    }
    return response.blob();
  }
}

// Factory function to create service instance
export const createMicrosoft365SkillsService = (config: Microsoft365Config): Microsoft365SkillsService => {
  return new Microsoft365SkillsService(config);
};

// Default export
export default Microsoft365SkillsService;

// Export service instance with default configuration
export const microsoft365Skills = createMicrosoft365SkillsService({
  tenantId: '',
  clientId: '',
  clientSecret: '',
  redirectUri: '',
  scopes: ['User.Read', 'Mail.Read', 'Files.Read', 'Team.ReadBasic.All'],
});

// Export types and error class
export { Microsoft365ApiError };
export type { ApiResponse, PaginatedResponse };