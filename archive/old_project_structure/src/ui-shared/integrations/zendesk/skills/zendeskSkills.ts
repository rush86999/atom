/**
 * Zendesk Integration Skills
 * Frontend service for Zendesk API interactions
 * Following ATOM patterns for integration services
 */

import { api } from '../../../services/api';

export interface ZendeskTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresAt: string;
  subdomain: string;
  environment: 'production' | 'sandbox';
}

export interface ZendeskTicket {
  id: number;
  subject: string;
  description: string;
  status: 'new' | 'open' | 'pending' | 'hold' | 'solved' | 'closed';
  priority: 'urgent' | 'high' | 'normal' | 'low';
  type: 'question' | 'incident' | 'problem' | 'task';
  requester_id: number;
  requester: {
    id: number;
    name: string;
    email: string;
    role: string;
  };
  assignee_id?: number;
  assignee?: {
    id: number;
    name: string;
    email: string;
  };
  group_id?: number;
  group?: {
    id: number;
    name: string;
  };
  organization_id?: number;
  organization?: {
    id: number;
    name: string;
  };
  via: {
    channel: string;
    source: {
      from: any;
      to: any;
      rel: string;
    };
  };
  created_at: string;
  updated_at: string;
  due_at?: string;
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
  tags: string[];
  satisfaction_rating?: {
    score: string;
    comment: string;
  };
  is_public?: boolean;
  safe?: boolean;
  raw_subject?: string;
  collaborators?: any[];
  follower_ids?: number[];
  email_cc_ids?: number[];
  sharing_agreement_ids?: number[];
  fields?: any[];
  problem_type?: string;
  brand_id?: number;
  followup_ids?: number[];
}

export interface ZendeskUser {
  id: number;
  name: string;
  email: string;
  role: 'end-user' | 'agent' | 'admin';
  custom_role_id?: number;
  default_group_id?: number;
  phone?: string;
  shared_phone_number?: boolean;
  shared_agent?: boolean;
  notes?: string;
  active: boolean;
  verified: boolean;
  locale?: string;
  timezone?: string;
  last_login_at?: string;
  two_factor_auth_enabled?: boolean;
  signature?: string;
  details?: string;
  photo?: {
    thumbnails: {
      small: string;
      medium: string;
      large: string;
    };
  };
  tags: string[];
  restricted_agent: boolean;
  only_private_comments: boolean;
  ticket_restriction: string;
  suspended?: boolean;
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
  organization_id?: number;
  url?: string;
  alias?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ZendeskGroup {
  id: number;
  name: string;
  description?: string;
  is_public: boolean;
  default: boolean;
  created_at: string;
  updated_at: string;
  deleted_at?: string;
  url?: string;
}

export interface ZendeskOrganization {
  id: number;
  name: string;
  notes?: string;
  shared_tickets?: boolean;
  shared_comments?: boolean;
  domain_names?: string[];
  group_id?: number;
  created_at: string;
  updated_at: string;
  tags: string[];
  external_id?: string;
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
  url?: string;
  deleted_at?: string;
}

export interface ZendeskMetric {
  tickets_solved: number;
  tickets_unsolved: number;
  tickets_on_hold: number;
  tickets_opened: number;
  tickets_closed: number;
  tickets_reopened: number;
  tickets_satisfaction_score: number;
  tickets_abandonment_rate: number;
  tickets_first_resolution_time: number;
  tickets_average_reply_time: number;
  tickets_full_resolution_time: number;
  tickets_agent_stations: number;
}

export interface ZendeskMacro {
  id: number;
  title: string;
  actions: Array<{
    field: string;
    value: any;
  }>;
  active: boolean;
  description?: string;
  created_at: string;
  updated_at: string;
  usage: number;
}

export interface ZendeskTrigger {
  id: number;
  title: string;
  conditions: any;
  actions: Array<{
    field: string;
    value: any;
  }>;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ZendeskAutomation {
  id: number;
  title: string;
  conditions: any;
  actions: Array<{
    field: string;
    value: any;
  }>;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ZendeskSLA {
  id: number;
  title: string;
  description: string;
  policy_metrics: Array<{
    metric: string;
    target: number;
    business_hours: boolean;
  }>;
  filter: any;
  created_at: string;
  updated_at: string;
}

export interface ZendeskArticle {
  id: number;
  title: string;
  body: string;
  html_url: string;
  author_id: number;
  comments_disabled: boolean;
  promoted: boolean;
  position: number;
  vote_sum: number;
  vote_count: number;
  section_id: number;
  created_at: string;
  updated_at: string;
  edited_at?: string;
  user_segment_id?: number;
  label_names: string[];
}

export interface ZendeskCategory {
  id: number;
  name: string;
  description?: string;
  locale: string;
  out_of_date?: string;
  position?: number;
  created_at: string;
  updated_at: string;
  url?: string;
}

export interface ZendeskSection {
  id: number;
  name: string;
  description?: string;
  locale: string;
  category_id: number;
  position?: number;
  out_of_date?: string;
  parent_section_id?: number;
  source_locale?: string;
  out_of_date: boolean;
  created_at: string;
  updated_at: string;
  url?: string;
}

export interface ZendeskSearchOptions {
  query?: string;
  type?: 'ticket' | 'user' | 'organization' | 'group' | 'article' | 'entry';
  page?: number;
  per_page?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface ZendeskListOptions {
  page?: number;
  per_page?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface ZendeskCreateOptions {
  properties?: { [key: string]: any };
  attachments?: Array<{
    filename: string;
    content: string;
    contentType?: string;
  }>;
}

export interface ZendeskUpdateOptions {
  comment?: {
    body: string;
    html_body?: string;
    public?: boolean;
    author_id?: number;
    uploads?: number[];
  };
  assignee_id?: number;
  group_id?: number;
  organization_id?: number;
  status?: string;
  priority?: string;
  type?: string;
  tags?: string[];
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
  safe?: boolean;
  additional_collaborators?: Array<{
    id: number;
    email?: string;
    name?: string;
  }>;
  collaborators?: Array<{
    id: number;
    email?: string;
    name?: string;
  }>;
  email_ccs?: Array<{
    id: number;
    email?: string;
    name?: string;
  }>;
  followup_ids?: number[];
  problem_type?: string;
  brand_id?: number;
  sharing_agreement_ids?: number[];
}

class ZendeskSkills {
  private readonly baseUrl = '/api/zendesk';
  private readonly authUrl = '/api/zendesk/oauth';

  // Authentication methods
  async getStoredTokens(): Promise<ZendeskTokens | null> {
    try {
      const response = await api.get('/api/integrations/zendesk/health');
      if (response.data.status === 'healthy') {
        // For now, we'll assume tokens are stored in backend
        // This would need to be enhanced to retrieve actual token data
        return {
          accessToken: 'stored',
          refreshToken: 'stored',
          subdomain: 'stored',
          environment: 'production',
          expiresAt: undefined,
          scopes: []
        };
      }
      return null;
    } catch (error) {
      console.error('Failed to get stored tokens:', error);
      return null;
    }
  }

  async initiateOAuth(): Promise<void> {
    try {
      window.location.href = `${this.authUrl}/start`;
    } catch (error) {
      throw new Error(`Failed to initiate OAuth: ${error.message}`);
    }
  }

  async handleOAuthCallback(code: string, state: string): Promise<ZendeskTokens> {
    try {
      const response = await api.post(`${this.authUrl}/callback`, { code });
      return response.data.tokens;
    } catch (error) {
      throw new Error(`OAuth callback failed: ${error.message}`);
    }
  }

  async revokeAuthentication(): Promise<void> {
    try {
      await api.delete('/api/zendesk/auth');
    } catch (error) {
      throw new Error(`Failed to revoke authentication: ${error.message}`);
    }
  }

  // Ticket methods
  async getTickets(options: ZendeskListOptions = {}): Promise<{
    tickets: ZendeskTicket[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);

      const response = await api.get(`${this.baseUrl}/tickets?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get tickets: ${error.message}`);
    }
  }

  async getTicket(ticketId: number): Promise<ZendeskTicket> {
    try {
      const response = await api.get(`${this.baseUrl}/tickets/${ticketId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get ticket: ${error.message}`);
    }
  }

  async createTicket(ticketData: ZendeskCreateOptions & {
    subject: string;
    description: string;
    priority?: string;
    type?: string;
    status?: string;
    requester_id?: number;
    assignee_id?: number;
    group_id?: number;
    organization_id?: number;
    tags?: string[];
  }): Promise<ZendeskTicket> {
    try {
      const response = await api.post(`${this.baseUrl}/tickets`, ticketData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create ticket: ${error.message}`);
    }
  }

  async updateTicket(ticketId: number, updateData: ZendeskUpdateOptions): Promise<ZendeskTicket> {
    try {
      const response = await api.put(`${this.baseUrl}/tickets/${ticketId}`, updateData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update ticket: ${error.message}`);
    }
  }

  async deleteTicket(ticketId: number): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/tickets/${ticketId}`);
    } catch (error) {
      throw new Error(`Failed to delete ticket: ${error.message}`);
    }
  }

  async addTicketComment(ticketId: number, comment: {
    body: string;
    html_body?: string;
    public?: boolean;
    author_id?: number;
    uploads?: number[];
  }): Promise<ZendeskTicket> {
    try {
      const response = await api.put(`${this.baseUrl}/tickets/${ticketId}/comment`, comment);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to add comment: ${error.message}`);
    }
  }

  async addTicketInternalNote(ticketId: number, note: {
    body: string;
    html_body?: string;
    author_id?: number;
    uploads?: number[];
  }): Promise<ZendeskTicket> {
    try {
      const response = await api.put(`${this.baseUrl}/tickets/${ticketId}/note`, {
        ...note,
        public: false
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to add internal note: ${error.message}`);
    }
  }

  async searchTickets(options: ZendeskSearchOptions): Promise<{
    tickets: ZendeskTicket[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.query) params.append('query', options.query);
      if (options.type) params.append('type', options.type);
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);

      const response = await api.get(`${this.baseUrl}/tickets/search?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search tickets: ${error.message}`);
    }
  }

  // User methods
  async getUsers(options: ZendeskListOptions = {}): Promise<{
    users: ZendeskUser[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);

      const response = await api.get(`${this.baseUrl}/users?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get users: ${error.message}`);
    }
  }

  async getUser(userId: number): Promise<ZendeskUser> {
    try {
      const response = await api.get(`${this.baseUrl}/users/${userId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get user: ${error.message}`);
    }
  }

  async createUser(userData: {
    name: string;
    email: string;
    role?: string;
    phone?: string;
    notes?: string;
    active?: boolean;
    verified?: boolean;
    tags?: string[];
    custom_fields?: Array<{
      id: number;
      value: any;
    }>;
  }): Promise<ZendeskUser> {
    try {
      const response = await api.post(`${this.baseUrl}/users`, userData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create user: ${error.message}`);
    }
  }

  async updateUser(userId: number, userData: Partial<ZendeskUser>): Promise<ZendeskUser> {
    try {
      const response = await api.put(`${this.baseUrl}/users/${userId}`, userData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update user: ${error.message}`);
    }
  }

  async deleteUser(userId: number): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/users/${userId}`);
    } catch (error) {
      throw new Error(`Failed to delete user: ${error.message}`);
    }
  }

  async suspendUser(userId: number, suspend = true): Promise<ZendeskUser> {
    try {
      const response = await api.put(`${this.baseUrl}/users/${userId}/suspend`, { suspend });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to suspend user: ${error.message}`);
    }
  }

  async searchUsers(options: ZendeskSearchOptions): Promise<{
    users: ZendeskUser[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.query) params.append('query', options.query);
      if (options.type) params.append('type', options.type);
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());

      const response = await api.get(`${this.baseUrl}/users/search?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search users: ${error.message}`);
    }
  }

  // Group methods
  async getGroups(): Promise<{
    groups: ZendeskGroup[];
    count: number;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/groups`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get groups: ${error.message}`);
    }
  }

  async getGroup(groupId: number): Promise<ZendeskGroup> {
    try {
      const response = await api.get(`${this.baseUrl}/groups/${groupId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get group: ${error.message}`);
    }
  }

  async createGroup(groupData: {
    name: string;
    description?: string;
    is_public?: boolean;
    default?: boolean;
  }): Promise<ZendeskGroup> {
    try {
      const response = await api.post(`${this.baseUrl}/groups`, groupData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create group: ${error.message}`);
    }
  }

  async updateGroup(groupId: number, groupData: Partial<ZendeskGroup>): Promise<ZendeskGroup> {
    try {
      const response = await api.put(`${this.baseUrl}/groups/${groupId}`, groupData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update group: ${error.message}`);
    }
  }

  async deleteGroup(groupId: number): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/groups/${groupId}`);
    } catch (error) {
      throw new Error(`Failed to delete group: ${error.message}`);
    }
  }

  // Organization methods
  async getOrganizations(options: ZendeskListOptions = {}): Promise<{
    organizations: ZendeskOrganization[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);

      const response = await api.get(`${this.baseUrl}/organizations?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get organizations: ${error.message}`);
    }
  }

  async getOrganization(organizationId: number): Promise<ZendeskOrganization> {
    try {
      const response = await api.get(`${this.baseUrl}/organizations/${organizationId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get organization: ${error.message}`);
    }
  }

  async createOrganization(orgData: {
    name: string;
    notes?: string;
    shared_tickets?: boolean;
    shared_comments?: boolean;
    domain_names?: string[];
    group_id?: number;
    tags?: string[];
    custom_fields?: Array<{
      id: number;
      value: any;
    }>;
  }): Promise<ZendeskOrganization> {
    try {
      const response = await api.post(`${this.baseUrl}/organizations`, orgData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create organization: ${error.message}`);
    }
  }

  async updateOrganization(organizationId: number, orgData: Partial<ZendeskOrganization>): Promise<ZendeskOrganization> {
    try {
      const response = await api.put(`${this.baseUrl}/organizations/${organizationId}`, orgData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update organization: ${error.message}`);
    }
  }

  async deleteOrganization(organizationId: number): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/organizations/${organizationId}`);
    } catch (error) {
      throw new Error(`Failed to delete organization: ${error.message}`);
    }
  }

  async searchOrganizations(options: ZendeskSearchOptions): Promise<{
    organizations: ZendeskOrganization[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.query) params.append('query', options.query);
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());

      const response = await api.get(`${this.baseUrl}/organizations/search?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search organizations: ${error.message}`);
    }
  }

  // Macros methods
  async getMacros(options: ZendeskListOptions = {}): Promise<{
    macros: ZendeskMacro[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());

      const response = await api.get(`${this.baseUrl}/macros?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get macros: ${error.message}`);
    }
  }

  async applyMacro(ticketId: number, macroId: number): Promise<ZendeskTicket> {
    try {
      const response = await api.put(`${this.baseUrl}/tickets/${ticketId}/macros/${macroId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to apply macro: ${error.message}`);
    }
  }

  // Triggers methods
  async getTriggers(options: ZendeskListOptions = {}): Promise<{
    triggers: ZendeskTrigger[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());

      const response = await api.get(`${this.baseUrl}/triggers?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get triggers: ${error.message}`);
    }
  }

  // Automations methods
  async getAutomations(options: ZendeskListOptions = {}): Promise<{
    automations: ZendeskAutomation[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());

      const response = await api.get(`${this.baseUrl}/automations?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get automations: ${error.message}`);
    }
  }

  // Metrics methods
  async getMetrics(dateRange?: { from: string; to: string }): Promise<ZendeskMetric> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/metrics?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get metrics: ${error.message}`);
    }
  }

  async getTicketMetrics(ticketId: number): Promise<{
    satisfaction_score?: number;
    first_resolution_time?: number;
    full_resolution_time?: number;
    agent_wait_time?: number;
    requester_wait_time?: number;
    assignments?: number;
    comments?: number;
    internal_comments?: number;
    attachments?: number;
    business_hours_elapsed?: number;
    calendar_hours_elapsed?: number;
    group_stations?: number;
    reopens?: number;
    stale?: boolean;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/tickets/${ticketId}/metrics`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get ticket metrics: ${error.message}`);
    }
  }

  // Satisfaction methods
  async getSatisfactionRating(ticketId: number): Promise<{
    score?: 'good' | 'bad' | 'offered';
    comment?: string;
    created_at?: string;
    updated_at?: string;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/tickets/${ticketId}/satisfaction`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get satisfaction rating: ${error.message}`);
    }
  }

  async submitSatisfactionRating(ticketId: number, rating: {
    score: 'good' | 'bad';
    comment?: string;
  }): Promise<void> {
    try {
      await api.post(`${this.baseUrl}/tickets/${ticketId}/satisfaction`, rating);
    } catch (error) {
      throw new Error(`Failed to submit satisfaction rating: ${error.message}`);
    }
  }

  // Attachment methods
  async uploadAttachment(file: File): Promise<{
    token: string;
    expires_at: string;
    content_type: string;
    filename: string;
    size: number;
  }> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post(`${this.baseUrl}/uploads`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to upload attachment: ${error.message}`);
    }
  }

  // Health check
  async getHealthStatus(): Promise<{
    status: 'healthy' | 'unhealthy';
    authenticated: boolean;
    lastSync?: string;
    message?: string;
    version: string;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/health`);
      return response.data;
    } catch (error) {
      return {
        status: 'unhealthy',
        authenticated: false,
        message: error.message,
        version: 'unknown'
      };
    }
  }

  // Utility methods
  getStatusColor(status: string): string {
    const colors: { [key: string]: string } = {
      'new': 'green',
      'open': 'blue',
      'pending': 'yellow',
      'hold': 'orange',
      'solved': 'purple',
      'closed': 'gray'
    };
    return colors[status?.toLowerCase()] || 'gray';
  }

  getPriorityColor(priority: string): string {
    const colors: { [key: string]: string } = {
      'urgent': 'red',
      'high': 'orange',
      'normal': 'blue',
      'low': 'green'
    };
    return colors[priority?.toLowerCase()] || 'gray';
  }

  getTypeColor(type: string): string {
    const colors: { [key: string]: string } = {
      'question': 'blue',
      'incident': 'red',
      'problem': 'orange',
      'task': 'green'
    };
    return colors[type?.toLowerCase()] || 'gray';
  }

  getRoleColor(role: string): string {
    const colors: { [key: string]: string } = {
      'admin': 'red',
      'agent': 'blue',
      'end-user': 'gray'
    };
    return colors[role?.toLowerCase()] || 'gray';
  }

  formatDate(dateString: string): string {
    if (!dateString) return '';
    return new Date(dateString).toLocaleString();
  }

  getRelativeTime(dateString: string): string {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    const minutes = Math.floor(diff / (1000 * 60));
    
    if (days > 0) {
      return `${days} day${days > 1 ? 's' : ''} ago`;
    } else if (hours > 0) {
      return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else if (minutes > 0) {
      return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    } else {
      return 'Just now';
    }
  }

  formatDuration(minutes: number): string {
    if (!minutes) return '0m';
    
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    } else {
      return `${mins}m`;
    }
  }

  validateEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  validateTicket(ticket: Partial<ZendeskTicket>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (!ticket.subject || ticket.subject.trim().length === 0) {
      errors.push('Subject is required');
    }
    
    if (!ticket.description || ticket.description.trim().length === 0) {
      errors.push('Description is required');
    }
    
    if (ticket.requester_id && typeof ticket.requester_id !== 'number') {
      errors.push('Valid requester ID is required');
    }
    
    if (ticket.email_ccs && !Array.isArray(ticket.email_ccs)) {
      errors.push('Email CCs must be an array');
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }

  validateUser(user: Partial<ZendeskUser>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (!user.name || user.name.trim().length === 0) {
      errors.push('Name is required');
    }
    
    if (!user.email || user.email.trim().length === 0) {
      errors.push('Email is required');
    } else if (!this.validateEmail(user.email)) {
      errors.push('Invalid email format');
    }
    
    if (user.role && !['admin', 'agent', 'end-user'].includes(user.role)) {
      errors.push('Invalid role. Must be admin, agent, or end-user');
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }
}

// Export singleton instance
export const zendeskSkills = new ZendeskSkills();
export default zendeskSkills;