/**
 * Salesforce CRM Skills Service
 * Complete API client for Salesforce CRM operations
 */

import { 
  SalesforceUser, SalesforceAccount, SalesforceContact, SalesforceLead,
  SalesforceOpportunity, SalesforceCase, SalesforceCampaign,
  SalesforceConfig
} from '../components/SalesforceManager';

// API Configuration
const API_BASE_URL = '/api/salesforce';
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
export class SalesforceApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public endpoint?: string,
    public details?: any
  ) {
    super(message);
    this.name = 'SalesforceApiError';
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
    throw new SalesforceApiError(errorMessage, response.status, response.url);
  }

  const data = await response.json();
  if (!data.success) {
    throw new SalesforceApiError(data.error || 'API request failed', undefined, response.url, data);
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
export class SalesforceSkillsService {
  private config: SalesforceConfig;
  private apiBase: string;

  constructor(config: SalesforceConfig) {
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
  async registerIntegration(config: SalesforceConfig): Promise<ApiResponse> {
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

  /**
   * Refresh access token
   */
  async refreshToken(): Promise<ApiResponse> {
    return makeRequest('/auth/refresh', {
      method: 'POST',
    });
  }

  // ==============================
  // USER OPERATIONS
  // ==============================

  /**
   * Get users
   */
  async getUsers(limit: number = 50, offset: number = 0): Promise<PaginatedResponse<SalesforceUser[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    return makeRequest(`/users?${params}`);
  }

  /**
   * Get user by ID
   */
  async getUser(userId: string): Promise<ApiResponse<SalesforceUser>> {
    return makeRequest(`/users/${userId}`);
  }

  /**
   * Create user
   */
  async createUser(userData: Partial<SalesforceUser>): Promise<ApiResponse<SalesforceUser>> {
    return makeRequest('/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  /**
   * Update user
   */
  async updateUser(userId: string, userData: Partial<SalesforceUser>): Promise<ApiResponse<SalesforceUser>> {
    return makeRequest(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    });
  }

  /**
   * Delete user
   */
  async deleteUser(userId: string): Promise<ApiResponse> {
    return makeRequest(`/users/${userId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Get current user
   */
  async getCurrentUser(): Promise<ApiResponse<SalesforceUser>> {
    return makeRequest('/users/me');
  }

  /**
   * Search users
   */
  async searchUsers(query: string, limit: number = 20): Promise<PaginatedResponse<SalesforceUser[]>> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString()
    });
    return makeRequest(`/users/search?${params}`);
  }

  // ==============================
  // ACCOUNT OPERATIONS
  // ==============================

  /**
   * Get accounts
   */
  async getAccounts(limit: number = 50, offset: number = 0): Promise<PaginatedResponse<SalesforceAccount[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    return makeRequest(`/accounts?${params}`);
  }

  /**
   * Get account by ID
   */
  async getAccount(accountId: string): Promise<ApiResponse<SalesforceAccount>> {
    return makeRequest(`/accounts/${accountId}`);
  }

  /**
   * Create account
   */
  async createAccount(accountData: Partial<SalesforceAccount>): Promise<ApiResponse<SalesforceAccount>> {
    return makeRequest('/accounts', {
      method: 'POST',
      body: JSON.stringify(accountData),
    });
  }

  /**
   * Update account
   */
  async updateAccount(accountId: string, accountData: Partial<SalesforceAccount>): Promise<ApiResponse<SalesforceAccount>> {
    return makeRequest(`/accounts/${accountId}`, {
      method: 'PUT',
      body: JSON.stringify(accountData),
    });
  }

  /**
   * Delete account
   */
  async deleteAccount(accountId: string): Promise<ApiResponse> {
    return makeRequest(`/accounts/${accountId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Search accounts
   */
  async searchAccounts(query: string, limit: number = 20): Promise<PaginatedResponse<SalesforceAccount[]>> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString()
    });
    return makeRequest(`/accounts/search?${params}`);
  }

  /**
   * Get account contacts
   */
  async getAccountContacts(accountId: string): Promise<PaginatedResponse<SalesforceContact[]>> {
    return makeRequest(`/accounts/${accountId}/contacts`);
  }

  /**
   * Get account opportunities
   */
  async getAccountOpportunities(accountId: string): Promise<PaginatedResponse<SalesforceOpportunity[]>> {
    return makeRequest(`/accounts/${accountId}/opportunities`);
  }

  /**
   * Get account cases
   */
  async getAccountCases(accountId: string): Promise<PaginatedResponse<SalesforceCase[]>> {
    return makeRequest(`/accounts/${accountId}/cases`);
  }

  // ==============================
  // CONTACT OPERATIONS
  // ==============================

  /**
   * Get contacts
   */
  async getContacts(limit: number = 50, offset: number = 0): Promise<PaginatedResponse<SalesforceContact[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    return makeRequest(`/contacts?${params}`);
  }

  /**
   * Get contact by ID
   */
  async getContact(contactId: string): Promise<ApiResponse<SalesforceContact>> {
    return makeRequest(`/contacts/${contactId}`);
  }

  /**
   * Create contact
   */
  async createContact(contactData: Partial<SalesforceContact>): Promise<ApiResponse<SalesforceContact>> {
    return makeRequest('/contacts', {
      method: 'POST',
      body: JSON.stringify(contactData),
    });
  }

  /**
   * Update contact
   */
  async updateContact(contactId: string, contactData: Partial<SalesforceContact>): Promise<ApiResponse<SalesforceContact>> {
    return makeRequest(`/contacts/${contactId}`, {
      method: 'PUT',
      body: JSON.stringify(contactData),
    });
  }

  /**
   * Delete contact
   */
  async deleteContact(contactId: string): Promise<ApiResponse> {
    return makeRequest(`/contacts/${contactId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Search contacts
   */
  async searchContacts(query: string, limit: number = 20): Promise<PaginatedResponse<SalesforceContact[]>> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString()
    });
    return makeRequest(`/contacts/search?${params}`);
  }

  /**
   * Get contact opportunities
   */
  async getContactOpportunities(contactId: string): Promise<PaginatedResponse<SalesforceOpportunity[]>> {
    return makeRequest(`/contacts/${contactId}/opportunities`);
  }

  /**
   * Get contact cases
   */
  async getContactCases(contactId: string): Promise<PaginatedResponse<SalesforceCase[]>> {
    return makeRequest(`/contacts/${contactId}/cases`);
  }

  // ==============================
  // LEAD OPERATIONS
  // ==============================

  /**
   * Get leads
   */
  async getLeads(limit: number = 50, offset: number = 0): Promise<PaginatedResponse<SalesforceLead[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    return makeRequest(`/leads?${params}`);
  }

  /**
   * Get lead by ID
   */
  async getLead(leadId: string): Promise<ApiResponse<SalesforceLead>> {
    return makeRequest(`/leads/${leadId}`);
  }

  /**
   * Create lead
   */
  async createLead(leadData: Partial<SalesforceLead>): Promise<ApiResponse<SalesforceLead>> {
    return makeRequest('/leads', {
      method: 'POST',
      body: JSON.stringify(leadData),
    });
  }

  /**
   * Update lead
   */
  async updateLead(leadId: string, leadData: Partial<SalesforceLead>): Promise<ApiResponse<SalesforceLead>> {
    return makeRequest(`/leads/${leadId}`, {
      method: 'PUT',
      body: JSON.stringify(leadData),
    });
  }

  /**
   * Delete lead
   */
  async deleteLead(leadId: string): Promise<ApiResponse> {
    return makeRequest(`/leads/${leadId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Convert lead
   */
  async convertLead(leadId: string, conversionData: {
    accountId?: string;
    contactId?: string;
    opportunityName?: string;
    ownerId?: string;
    doNotCreateOpportunity?: boolean;
    overwriteExistingAccount?: boolean;
    sendNotificationEmail?: boolean;
  }): Promise<ApiResponse> {
    return makeRequest(`/leads/${leadId}/convert`, {
      method: 'POST',
      body: JSON.stringify(conversionData),
    });
  }

  /**
   * Search leads
   */
  async searchLeads(query: string, limit: number = 20): Promise<PaginatedResponse<SalesforceLead[]>> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString()
    });
    return makeRequest(`/leads/search?${params}`);
  }

  // ==============================
  // OPPORTUNITY OPERATIONS
  // ==============================

  /**
   * Get opportunities
   */
  async getOpportunities(limit: number = 50, offset: number = 0): Promise<PaginatedResponse<SalesforceOpportunity[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    return makeRequest(`/opportunities?${params}`);
  }

  /**
   * Get opportunity by ID
   */
  async getOpportunity(opportunityId: string): Promise<ApiResponse<SalesforceOpportunity>> {
    return makeRequest(`/opportunities/${opportunityId}`);
  }

  /**
   * Create opportunity
   */
  async createOpportunity(opportunityData: Partial<SalesforceOpportunity>): Promise<ApiResponse<SalesforceOpportunity>> {
    return makeRequest('/opportunities', {
      method: 'POST',
      body: JSON.stringify(opportunityData),
    });
  }

  /**
   * Update opportunity
   */
  async updateOpportunity(opportunityId: string, opportunityData: Partial<SalesforceOpportunity>): Promise<ApiResponse<SalesforceOpportunity>> {
    return makeRequest(`/opportunities/${opportunityId}`, {
      method: 'PUT',
      body: JSON.stringify(opportunityData),
    });
  }

  /**
   * Delete opportunity
   */
  async deleteOpportunity(opportunityId: string): Promise<ApiResponse> {
    return makeRequest(`/opportunities/${opportunityId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Search opportunities
   */
  async searchOpportunities(query: string, limit: number = 20): Promise<PaginatedResponse<SalesforceOpportunity[]>> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString()
    });
    return makeRequest(`/opportunities/search?${params}`);
  }

  /**
   * Get opportunity line items
   */
  async getOpportunityLineItems(opportunityId: string): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/opportunities/${opportunityId}/lineItems`);
  }

  /**
   * Update opportunity stage
   */
  async updateOpportunityStage(opportunityId: string, stageName: string): Promise<ApiResponse<SalesforceOpportunity>> {
    return makeRequest(`/opportunities/${opportunityId}/stage`, {
      method: 'PUT',
      body: JSON.stringify({ stageName }),
    });
  }

  /**
   * Close opportunity
   */
  async closeOpportunity(opportunityId: string, closeData: {
    isWon: boolean;
    amount?: number;
    closeDate?: string;
    description?: string;
  }): Promise<ApiResponse> {
    return makeRequest(`/opportunities/${opportunityId}/close`, {
      method: 'POST',
      body: JSON.stringify(closeData),
    });
  }

  // ==============================
  // CASE OPERATIONS
  // ==============================

  /**
   * Get cases
   */
  async getCases(limit: number = 50, offset: number = 0): Promise<PaginatedResponse<SalesforceCase[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    return makeRequest(`/cases?${params}`);
  }

  /**
   * Get case by ID
   */
  async getCase(caseId: string): Promise<ApiResponse<SalesforceCase>> {
    return makeRequest(`/cases/${caseId}`);
  }

  /**
   * Create case
   */
  async createCase(caseData: Partial<SalesforceCase>): Promise<ApiResponse<SalesforceCase>> {
    return makeRequest('/cases', {
      method: 'POST',
      body: JSON.stringify(caseData),
    });
  }

  /**
   * Update case
   */
  async updateCase(caseId: string, caseData: Partial<SalesforceCase>): Promise<ApiResponse<SalesforceCase>> {
    return makeRequest(`/cases/${caseId}`, {
      method: 'PUT',
      body: JSON.stringify(caseData),
    });
  }

  /**
   * Delete case
   */
  async deleteCase(caseId: string): Promise<ApiResponse> {
    return makeRequest(`/cases/${caseId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Search cases
   */
  async searchCases(query: string, limit: number = 20): Promise<PaginatedResponse<SalesforceCase[]>> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString()
    });
    return makeRequest(`/cases/search?${params}`);
  }

  /**
   * Get case comments
   */
  async getCaseComments(caseId: string): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/cases/${caseId}/comments`);
  }

  /**
   * Add case comment
   */
  async addCaseComment(caseId: string, commentData: {
    commentBody: string;
    isPublished: boolean;
    parentCommentId?: string;
  }): Promise<ApiResponse> {
    return makeRequest(`/cases/${caseId}/comments`, {
      method: 'POST',
      body: JSON.stringify(commentData),
    });
  }

  /**
   * Update case status
   */
  async updateCaseStatus(caseId: string, status: string, comment?: string): Promise<ApiResponse<SalesforceCase>> {
    return makeRequest(`/cases/${caseId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status, comment }),
    });
  }

  /**
   * Escalate case
   */
  async escalateCase(caseId: string, escalationData: {
    reason: string;
    escalatedTo: string;
    comment?: string;
  }): Promise<ApiResponse> {
    return makeRequest(`/cases/${caseId}/escalate`, {
      method: 'POST',
      body: JSON.stringify(escalationData),
    });
  }

  /**
   * Close case
   */
  async closeCase(caseId: string, closeData: {
    status: string;
    reason: string;
    comment?: string;
  }): Promise<ApiResponse> {
    return makeRequest(`/cases/${caseId}/close`, {
      method: 'POST',
      body: JSON.stringify(closeData),
    });
  }

  // ==============================
  // CAMPAIGN OPERATIONS
  // ==============================

  /**
   * Get campaigns
   */
  async getCampaigns(limit: number = 50, offset: number = 0): Promise<PaginatedResponse<SalesforceCampaign[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    return makeRequest(`/campaigns?${params}`);
  }

  /**
   * Get campaign by ID
   */
  async getCampaign(campaignId: string): Promise<ApiResponse<SalesforceCampaign>> {
    return makeRequest(`/campaigns/${campaignId}`);
  }

  /**
   * Create campaign
   */
  async createCampaign(campaignData: Partial<SalesforceCampaign>): Promise<ApiResponse<SalesforceCampaign>> {
    return makeRequest('/campaigns', {
      method: 'POST',
      body: JSON.stringify(campaignData),
    });
  }

  /**
   * Update campaign
   */
  async updateCampaign(campaignId: string, campaignData: Partial<SalesforceCampaign>): Promise<ApiResponse<SalesforceCampaign>> {
    return makeRequest(`/campaigns/${campaignId}`, {
      method: 'PUT',
      body: JSON.stringify(campaignData),
    });
  }

  /**
   * Delete campaign
   */
  async deleteCampaign(campaignId: string): Promise<ApiResponse> {
    return makeRequest(`/campaigns/${campaignId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Search campaigns
   */
  async searchCampaigns(query: string, limit: number = 20): Promise<PaginatedResponse<SalesforceCampaign[]>> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString()
    });
    return makeRequest(`/campaigns/search?${params}`);
  }

  /**
   * Get campaign members
   */
  async getCampaignMembers(campaignId: string): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/campaigns/${campaignId}/members`);
  }

  /**
   * Add campaign members
   */
  async addCampaignMembers(campaignId: string, memberData: {
    leadIds?: string[];
    contactIds?: string[];
    accountIds?: string[];
  }): Promise<ApiResponse> {
    return makeRequest(`/campaigns/${campaignId}/members`, {
      method: 'POST',
      body: JSON.stringify(memberData),
    });
  }

  /**
   * Remove campaign members
   */
  async removeCampaignMembers(campaignId: string, memberIds: string[]): Promise<ApiResponse> {
    return makeRequest(`/campaigns/${campaignId}/members`, {
      method: 'DELETE',
      body: JSON.stringify({ memberIds }),
    });
  }

  /**
   * Start campaign
   */
  async startCampaign(campaignId: string): Promise<ApiResponse> {
    return makeRequest(`/campaigns/${campaignId}/start`, {
      method: 'POST',
    });
  }

  /**
   * Pause campaign
   */
  async pauseCampaign(campaignId: string): Promise<ApiResponse> {
    return makeRequest(`/campaigns/${campaignId}/pause`, {
      method: 'POST',
    });
  }

  /**
   * Stop campaign
   */
  async stopCampaign(campaignId: string): Promise<ApiResponse> {
    return makeRequest(`/campaigns/${campaignId}/stop`, {
      method: 'POST',
    });
  }

  // ==============================
  // SEARCH OPERATIONS
  // ==============================

  /**
   * Global search
   */
  async globalSearch(query: string, options: {
    objectType?: string[];
    limit?: number;
    offset?: number;
  } = {}): Promise<ApiResponse> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (options.objectType) params.append('objectTypes', options.objectType.join(','));
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());

    return makeRequest(`/search/global?${params}`);
  }

  /**
   * SOSL search
   */
  async soslSearch(query: string, objectTypes: string[]): Promise<ApiResponse> {
    return makeRequest('/search/sosl', {
      method: 'POST',
      body: JSON.stringify({
        query,
        objectTypes
      }),
    });
  }

  /**
   * SOQL query
   */
  async soqlQuery(query: string, options: {
    limit?: number;
    offset?: number;
    includeDeleted?: boolean;
  } = {}): Promise<ApiResponse> {
    const params = new URLSearchParams();
    params.append('q', query);
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());
    if (options.includeDeleted) params.append('includeDeleted', 'true');

    return makeRequest(`/search/soql?${params}`);
  }

  // ==============================
  // WEBHOOK OPERATIONS
  // ==============================

  /**
   * Subscribe to webhook
   */
  async subscribeToWebhook(webhookData: {
    name: string;
    object: string;
    events: string[];
    active: boolean;
    callbackUrl: string;
    endpoint?: string;
  }): Promise<ApiResponse> {
    return makeRequest('/webhooks/subscribe', {
      method: 'POST',
      body: JSON.stringify(webhookData),
    });
  }

  /**
   * Get webhooks
   */
  async getWebhooks(): Promise<PaginatedResponse<any[]>> {
    return makeRequest('/webhooks');
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
  // REPORTING OPERATIONS
  // ==============================

  /**
   * Generate report
   */
  async generateReport(reportData: {
    type: string;
    format: 'CSV' | 'XLSX' | 'PDF' | 'JSON';
    filters?: Record<string, any>;
    dateRange?: {
      start: string;
      end: string;
    };
    objectTypes?: string[];
    fields?: string[];
  }): Promise<ApiResponse<{ url: string; id: string }>> {
    return makeRequest('/reports/generate', {
      method: 'POST',
      body: JSON.stringify(reportData),
    });
  }

  /**
   * Get reports
   */
  async getReports(): Promise<PaginatedResponse<any[]>> {
    return makeRequest('/reports');
  }

  /**
   * Download report
   */
  async downloadReport(reportId: string): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/reports/${reportId}/download`);
    if (!response.ok) {
      throw new SalesforceApiError(`Download failed: ${response.statusText}`, response.status);
    }
    return response.blob();
  }

  /**
   * Get dashboard data
   */
  async getDashboardData(options: {
    startDate?: string;
    endDate?: string;
    objectTypes?: string[];
    metrics?: string[];
  } = {}): Promise<ApiResponse> {
    const params = new URLSearchParams();
    if (options.startDate) params.append('startDate', options.startDate);
    if (options.endDate) params.append('endDate', options.endDate);
    if (options.objectTypes) params.append('objectTypes', options.objectTypes.join(','));
    if (options.metrics) params.append('metrics', options.metrics.join(','));

    return makeRequest(`/dashboard/data?${params}`);
  }

  // ==============================
  // AUTOMATION OPERATIONS
  // ==============================

  /**
   * Get automation rules
   */
  async getAutomationRules(objectType: string): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/automation/rules?objectType=${objectType}`);
  }

  /**
   * Create automation rule
   */
  async createAutomationRule(ruleData: {
    name: string;
    description: string;
    objectType: string;
    conditions: any[];
    actions: any[];
    isActive: boolean;
    evaluationCriteria: string;
    executionOrder: number;
  }): Promise<ApiResponse> {
    return makeRequest('/automation/rules', {
      method: 'POST',
      body: JSON.stringify(ruleData),
    });
  }

  /**
   * Update automation rule
   */
  async updateAutomationRule(ruleId: string, ruleData: Partial<any>): Promise<ApiResponse> {
    return makeRequest(`/automation/rules/${ruleId}`, {
      method: 'PUT',
      body: JSON.stringify(ruleData),
    });
  }

  /**
   * Delete automation rule
   */
  async deleteAutomationRule(ruleId: string): Promise<ApiResponse> {
    return makeRequest(`/automation/rules/${ruleId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Test automation rule
   */
  async testAutomationRule(ruleId: string, testData: any): Promise<ApiResponse> {
    return makeRequest(`/automation/rules/${ruleId}/test`, {
      method: 'POST',
      body: JSON.stringify(testData),
    });
  }

  // ==============================
  // CUSTOMIZATION OPERATIONS
  // ==============================

  /**
   * Get custom objects
   */
  async getCustomObjects(): Promise<PaginatedResponse<any[]>> {
    return makeRequest('/custom/objects');
  }

  /**
   * Create custom object
   */
  async createCustomObject(objectData: {
    label: string;
    pluralLabel: string;
    name: string;
    description: string;
    fields: any[];
  }): Promise<ApiResponse> {
    return makeRequest('/custom/objects', {
      method: 'POST',
      body: JSON.stringify(objectData),
    });
  }

  /**
   * Get custom fields
   */
  async getCustomFields(objectType: string): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/custom/fields?objectType=${objectType}`);
  }

  /**
   * Create custom field
   */
  async createCustomField(fieldData: {
    label: string;
    name: string;
    type: string;
    objectType: string;
    required: boolean;
    defaultValue?: any;
    description?: string;
    helpText?: string;
  }): Promise<ApiResponse> {
    return makeRequest('/custom/fields', {
      method: 'POST',
      body: JSON.stringify(fieldData),
    });
  }

  // ==============================
  // UTILITY OPERATIONS
  // ==============================

  /**
   * Get API usage
   */
  async getApiUsage(): Promise<ApiResponse> {
    return makeRequest('/usage');
  }

  /**
   * Get org limits
   */
  async getOrgLimits(): Promise<ApiResponse> {
    return makeRequest('/limits');
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

  /**
   * Bulk create records
   */
  async bulkCreateRecords(objectType: string, records: any[]): Promise<ApiResponse<{ successCount: number; errorCount: number; errors: any[] }>> {
    return makeRequest('/bulk/create', {
      method: 'POST',
      body: JSON.stringify({
        objectType,
        records
      }),
    });
  }

  /**
   * Bulk update records
   */
  async bulkUpdateRecords(objectType: string, records: any[]): Promise<ApiResponse<{ successCount: number; errorCount: number; errors: any[] }>> {
    return makeRequest('/bulk/update', {
      method: 'POST',
      body: JSON.stringify({
        objectType,
        records
      }),
    });
  }

  /**
   * Bulk delete records
   */
  async bulkDeleteRecords(objectType: string, recordIds: string[]): Promise<ApiResponse<{ successCount: number; errorCount: number; errors: any[] }>> {
    return makeRequest('/bulk/delete', {
      method: 'POST',
      body: JSON.stringify({
        objectType,
        recordIds
      }),
    });
  }

  /**
   * Get workflow rules
   */
  async getWorkflowRules(): Promise<PaginatedResponse<any[]>> {
    return makeRequest('/workflows/rules');
  }

  /**
   * Execute workflow
   */
  async executeWorkflow(workflowId: string, context: any): Promise<ApiResponse> {
    return makeRequest(`/workflows/${workflowId}/execute`, {
      method: 'POST',
      body: JSON.stringify({ context }),
    });
  }

  /**
   * Get duplicate rules
   */
  async getDuplicateRules(objectType: string): Promise<PaginatedResponse<any[]>> {
    return makeRequest(`/duplicate/rules?objectType=${objectType}`);
  }

  /**
   * Find duplicates
   */
  async findDuplicates(objectType: string, recordId: string): Promise<ApiResponse> {
    return makeRequest(`/duplicate/find?objectType=${objectType}&recordId=${recordId}`);
  }

  /**
   * Merge duplicates
   */
  async mergeDuplicates(objectType: string, masterRecordId: string, duplicateRecordIds: string[]): Promise<ApiResponse> {
    return makeRequest('/duplicate/merge', {
      method: 'POST',
      body: JSON.stringify({
        objectType,
        masterRecordId,
        duplicateRecordIds
      }),
    });
  }
}

// Factory function to create service instance
export const createSalesforceSkillsService = (config: SalesforceConfig): SalesforceSkillsService => {
  return new SalesforceSkillsService(config);
};

// Default export
export default SalesforceSkillsService;

// Export service instance with default configuration
export const salesforceSkills = createSalesforceSkillsService({
  clientId: '',
  clientSecret: '',
  redirectUri: '',
  environment: 'sandbox',
  apiVersion: '56.0',
  timeout: 30000,
  maxRetries: 3
});

// Export types and error class
export { SalesforceApiError };
export type { ApiResponse, PaginatedResponse };