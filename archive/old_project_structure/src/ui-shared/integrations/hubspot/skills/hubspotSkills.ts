/**
 * HubSpot Integration Skills
 * Frontend service for HubSpot API interactions
 * Following ATOM patterns for integration services
 */

import { api } from '../../../services/api';

export interface HubSpotTokens {
  accessToken: string;
  refreshToken: string;
  hubId: string;
  environment: 'production' | 'sandbox';
  expiresAt?: string;
  scopes: string[];
}

export interface HubSpotContact {
  id: string;
  properties: {
    email?: string;
    firstname?: string;
    lastname?: string;
    phone?: string;
    company?: string;
    lifecyclestage?: string;
    createdate?: string;
    lastmodifieddate?: string;
  };
  createdAt?: string;
  updatedAt?: string;
}

export interface HubSpotCompany {
  id: string;
  properties: {
    name?: string;
    domain?: string;
    phone?: string;
    address?: string;
    city?: string;
    state?: string;
    country?: string;
    industry?: string;
    annualrevenue?: string;
    description?: string;
    createdate?: string;
  };
}

export interface HubSpotDeal {
  id: string;
  properties: {
    dealname?: string;
    amount?: string;
    closedate?: string;
    dealstage?: string;
    pipeline?: string;
    hubspot_owner_id?: string;
    createdate?: string;
    closed_won?: string;
  };
}

export interface HubSpotCampaign {
  id: string;
  name: string;
  status: string;
  type: string;
  createdAt: string;
  updatedAt: string;
  metrics: {
    sent: number;
    delivered: number;
    opened: number;
    clicked: number;
    converted: number;
  };
}

export interface HubSpotAnalytics {
  totalContacts: number;
  totalCompanies: number;
  totalDeals: number;
  totalRevenue: number;
  conversionRate: number;
  dealStageBreakdown: { [stage: string]: number };
  contactLifecycleBreakdown: { [stage: string]: number };
  monthlyRevenue: { month: string; revenue: number }[];
  topPerformingCampaigns: HubSpotCampaign[];
}

export interface HubSpotListOptions {
  limit?: number;
  offset?: number;
  search?: string;
  sort?: string;
  properties?: string[];
  filters?: {
    property: string;
    operator: string;
    value: string | number;
  }[];
}

export interface HubSpotCreateOptions {
  properties: { [key: string]: any };
  associations?: {
    to: { id: string };
    types: { category: string; type: string }[];
  }[];
}

export interface HubSpotSearchOptions {
  query?: string;
  entities?: string[];
  limit?: number;
  offset?: number;
  filters?: {
    value: string;
    propertyName: string;
    operator: string;
  }[];
}

class HubSpotSkills {
  private readonly baseUrl = '/api/hubspot';
  private readonly authUrl = '/api/hubspot/oauth';

  // Authentication methods
  async getStoredTokens(): Promise<HubSpotTokens | null> {
    try {
      const response = await api.get('/api/integrations/hubspot/health');
      if (response.data.status === 'healthy') {
        // For now, we'll assume tokens are stored in the backend
        // This would need to be enhanced to retrieve actual token data
        return {
          accessToken: 'stored',
          refreshToken: 'stored',
          hubId: 'stored',
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

  async handleOAuthCallback(code: string, state: string): Promise<HubSpotTokens> {
    try {
      const response = await api.post(`${this.authUrl}/callback`, { code });
      return response.data.tokens;
    } catch (error) {
      throw new Error(`OAuth callback failed: ${error.message}`);
    }
  }

  async revokeAuthentication(): Promise<void> {
    try {
      await api.delete('/api/hubspot/auth');
    } catch (error) {
      throw new Error(`Failed to revoke authentication: ${error.message}`);
    }
  }

  // Contact methods
  async getContacts(options: HubSpotListOptions = {}): Promise<{
    results: HubSpotContact[];
    total: number;
    hasMore: boolean;
    offset: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.sort) params.append('sort', options.sort);
      if (options.properties) params.append('properties', options.properties.join(','));
      if (options.filters) {
        params.append('filters', JSON.stringify(options.filters));
      }

      const response = await api.get(`${this.baseUrl}/contacts?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get contacts: ${error.message}`);
    }
  }

  async getContact(contactId: string): Promise<HubSpotContact> {
    try {
      const response = await api.get(`${this.baseUrl}/contacts/${contactId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get contact: ${error.message}`);
    }
  }

  async createContact(contactData: HubSpotCreateOptions | { [key: string]: any }): Promise<HubSpotContact> {
    try {
      const payload = contactData.properties ? contactData : {
        properties: contactData
      };
      const response = await api.post(`${this.baseUrl}/contacts`, payload);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create contact: ${error.message}`);
    }
  }

  async updateContact(contactId: string, contactData: HubSpotCreateOptions | { [key: string]: any }): Promise<HubSpotContact> {
    try {
      const payload = contactData.properties ? contactData : {
        properties: contactData
      };
      const response = await api.put(`${this.baseUrl}/contacts/${contactId}`, payload);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update contact: ${error.message}`);
    }
  }

  async deleteContact(contactId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/contacts/${contactId}`);
    } catch (error) {
      throw new Error(`Failed to delete contact: ${error.message}`);
    }
  }

  async searchContacts(searchOptions: HubSpotSearchOptions): Promise<{
    results: HubSpotContact[];
    total: number;
    hasMore: boolean;
  }> {
    try {
      const response = await api.post(`${this.baseUrl}/contacts/search`, searchOptions);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search contacts: ${error.message}`);
    }
  }

  async getContactCount(): Promise<number> {
    try {
      const response = await api.get(`${this.baseUrl}/contacts/count`);
      return response.data.count || 0;
    } catch (error) {
      console.error('Failed to get contact count:', error);
      return 0;
    }
  }

  // Company methods
  async getCompanies(options: HubSpotListOptions = {}): Promise<{
    results: HubSpotCompany[];
    total: number;
    hasMore: boolean;
    offset: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.sort) params.append('sort', options.sort);
      if (options.properties) params.append('properties', options.properties.join(','));
      if (options.filters) {
        params.append('filters', JSON.stringify(options.filters));
      }

      const response = await api.get(`${this.baseUrl}/companies?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get companies: ${error.message}`);
    }
  }

  async getCompany(companyId: string): Promise<HubSpotCompany> {
    try {
      const response = await api.get(`${this.baseUrl}/companies/${companyId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get company: ${error.message}`);
    }
  }

  async createCompany(companyData: HubSpotCreateOptions | { [key: string]: any }): Promise<HubSpotCompany> {
    try {
      const payload = companyData.properties ? companyData : {
        properties: companyData
      };
      const response = await api.post(`${this.baseUrl}/companies`, payload);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create company: ${error.message}`);
    }
  }

  async updateCompany(companyId: string, companyData: HubSpotCreateOptions | { [key: string]: any }): Promise<HubSpotCompany> {
    try {
      const payload = companyData.properties ? companyData : {
        properties: companyData
      };
      const response = await api.put(`${this.baseUrl}/companies/${companyId}`, payload);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update company: ${error.message}`);
    }
  }

  async deleteCompany(companyId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/companies/${companyId}`);
    } catch (error) {
      throw new Error(`Failed to delete company: ${error.message}`);
    }
  }

  async searchCompanies(searchOptions: HubSpotSearchOptions): Promise<{
    results: HubSpotCompany[];
    total: number;
    hasMore: boolean;
  }> {
    try {
      const response = await api.post(`${this.baseUrl}/companies/search`, searchOptions);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search companies: ${error.message}`);
    }
  }

  async getCompanyCount(): Promise<number> {
    try {
      const response = await api.get(`${this.baseUrl}/companies/count`);
      return response.data.count || 0;
    } catch (error) {
      console.error('Failed to get company count:', error);
      return 0;
    }
  }

  // Deal methods
  async getDeals(options: HubSpotListOptions = {}): Promise<{
    results: HubSpotDeal[];
    total: number;
    hasMore: boolean;
    offset: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.sort) params.append('sort', options.sort);
      if (options.properties) params.append('properties', options.properties.join(','));
      if (options.filters) {
        params.append('filters', JSON.stringify(options.filters));
      }

      const response = await api.get(`${this.baseUrl}/deals?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get deals: ${error.message}`);
    }
  }

  async getDeal(dealId: string): Promise<HubSpotDeal> {
    try {
      const response = await api.get(`${this.baseUrl}/deals/${dealId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get deal: ${error.message}`);
    }
  }

  async createDeal(dealData: HubSpotCreateOptions | { [key: string]: any }): Promise<HubSpotDeal> {
    try {
      const payload = dealData.properties ? dealData : {
        properties: dealData
      };
      const response = await api.post(`${this.baseUrl}/deals`, payload);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create deal: ${error.message}`);
    }
  }

  async updateDeal(dealId: string, dealData: HubSpotCreateOptions | { [key: string]: any }): Promise<HubSpotDeal> {
    try {
      const payload = dealData.properties ? dealData : {
        properties: dealData
      };
      const response = await api.put(`${this.baseUrl}/deals/${dealId}`, payload);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update deal: ${error.message}`);
    }
  }

  async deleteDeal(dealId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/deals/${dealId}`);
    } catch (error) {
      throw new Error(`Failed to delete deal: ${error.message}`);
    }
  }

  async searchDeals(searchOptions: HubSpotSearchOptions): Promise<{
    results: HubSpotDeal[];
    total: number;
    hasMore: boolean;
  }> {
    try {
      const response = await api.post(`${this.baseUrl}/deals/search`, searchOptions);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search deals: ${error.message}`);
    }
  }

  async getDealCount(): Promise<number> {
    try {
      const response = await api.get(`${this.baseUrl}/deals/count`);
      return response.data.count || 0;
    } catch (error) {
      console.error('Failed to get deal count:', error);
      return 0;
    }
  }

  // Deal Pipeline methods
  async getDealPipelines(): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/deals/pipelines`);
      return response.data.results || [];
    } catch (error) {
      throw new Error(`Failed to get deal pipelines: ${error.message}`);
    }
  }

  async getDealStages(pipelineId: string): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/deals/pipelines/${pipelineId}/stages`);
      return response.data.results || [];
    } catch (error) {
      throw new Error(`Failed to get deal stages: ${error.message}`);
    }
  }

  // Campaign methods
  async getCampaigns(options: HubSpotListOptions = {}): Promise<{
    results: HubSpotCampaign[];
    total: number;
    hasMore: boolean;
    offset: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.sort) params.append('sort', options.sort);

      const response = await api.get(`${this.baseUrl}/campaigns?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get campaigns: ${error.message}`);
    }
  }

  async getCampaign(campaignId: string): Promise<HubSpotCampaign> {
    try {
      const response = await api.get(`${this.baseUrl}/campaigns/${campaignId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get campaign: ${error.message}`);
    }
  }

  async createCampaign(campaignData: any): Promise<HubSpotCampaign> {
    try {
      const response = await api.post(`${this.baseUrl}/campaigns`, campaignData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create campaign: ${error.message}`);
    }
  }

  async updateCampaign(campaignId: string, campaignData: any): Promise<HubSpotCampaign> {
    try {
      const response = await api.put(`${this.baseUrl}/campaigns/${campaignId}`, campaignData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update campaign: ${error.message}`);
    }
  }

  async deleteCampaign(campaignId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/campaigns/${campaignId}`);
    } catch (error) {
      throw new Error(`Failed to delete campaign: ${error.message}`);
    }
  }

  // Analytics methods
  async getAnalytics(dateRange?: { from: string; to: string }): Promise<HubSpotAnalytics> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/analytics?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get analytics: ${error.message}`);
    }
  }

  async getDealAnalytics(dateRange?: { from: string; to: string }): Promise<{
    totalRevenue: number;
    conversionRate: number;
    averageDealSize: number;
    dealCycleLength: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/analytics/deals?${params}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get deal analytics:', error);
      return {
        totalRevenue: 0,
        conversionRate: 0,
        averageDealSize: 0,
        dealCycleLength: 0
      };
    }
  }

  async getContactAnalytics(dateRange?: { from: string; to: string }): Promise<{
    newContacts: number;
    conversionRate: number;
    sourceBreakdown: { [source: string]: number };
    lifecycleBreakdown: { [stage: string]: number };
  }> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/analytics/contacts?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get contact analytics: ${error.message}`);
    }
  }

  async getCampaignAnalytics(dateRange?: { from: string; to: string }): Promise<{
    totalCampaigns: number;
    averageOpenRate: number;
    averageClickRate: number;
    topPerformingCampaigns: HubSpotCampaign[];
  }> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/analytics/campaigns?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get campaign analytics: ${error.message}`);
    }
  }

  // Lead List methods
  async getLeadLists(options: HubSpotListOptions = {}): Promise<any> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);

      const response = await api.get(`${this.baseUrl}/lists?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get lead lists: ${error.message}`);
    }
  }

  async createLeadList(listData: any): Promise<any> {
    try {
      const response = await api.post(`${this.baseUrl}/lists`, listData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create lead list: ${error.message}`);
    }
  }

  async getLeadListMembers(listId: string, options: HubSpotListOptions = {}): Promise<any> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());

      const response = await api.get(`${this.baseUrl}/lists/${listId}/members?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get lead list members: ${error.message}`);
    }
  }

  // Email Marketing methods
  async sendEmail(emailData: {
    to: { email: string; name?: string }[];
    from: { email: string; name?: string };
    subject: string;
    html?: string;
    text?: string;
    templateId?: string;
  }): Promise<any> {
    try {
      const response = await api.post(`${this.baseUrl}/emails/send`, emailData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to send email: ${error.message}`);
    }
  }

  async getEmailTemplates(): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/emails/templates`);
      return response.data.results || [];
    } catch (error) {
      throw new Error(`Failed to get email templates: ${error.message}`);
    }
  }

  async getEmailAnalytics(dateRange?: { from: string; to: string }): Promise<any> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/emails/analytics?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get email analytics: ${error.message}`);
    }
  }

  // Property methods
  async getContactProperties(): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/properties/contacts`);
      return response.data.results || [];
    } catch (error) {
      throw new Error(`Failed to get contact properties: ${error.message}`);
    }
  }

  async getCompanyProperties(): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/properties/companies`);
      return response.data.results || [];
    } catch (error) {
      throw new Error(`Failed to get company properties: ${error.message}`);
    }
  }

  async getDealProperties(): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/properties/deals`);
      return response.data.results || [];
    } catch (error) {
      throw new Error(`Failed to get deal properties: ${error.message}`);
    }
  }

  // Webhook methods
  async getWebhooks(): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/webhooks`);
      return response.data.results || [];
    } catch (error) {
      throw new Error(`Failed to get webhooks: ${error.message}`);
    }
  }

  async createWebhook(webhookData: any): Promise<any> {
    try {
      const response = await api.post(`${this.baseUrl}/webhooks`, webhookData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create webhook: ${error.message}`);
    }
  }

  async deleteWebhook(webhookId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/webhooks/${webhookId}`);
    } catch (error) {
      throw new Error(`Failed to delete webhook: ${error.message}`);
    }
  }

  // Health check
  async getHealthStatus(): Promise<{
    status: 'healthy' | 'unhealthy';
    authenticated: boolean;
    lastSync?: string;
    message?: string;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/health`);
      return response.data;
    } catch (error) {
      return {
        status: 'unhealthy',
        authenticated: false,
        message: error.message
      };
    }
  }

  // Utility methods
  formatLifecycleStage(stage: string): string {
    if (!stage) return 'Unknown';
    return stage.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim();
  }

  formatDealStage(stage: string): string {
    if (!stage) return 'Unknown';
    return stage.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim();
  }

  formatDate(dateString: string): string {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString();
  }

  formatCurrency(amount: string | number): string {
    if (!amount) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(typeof amount === 'string' ? parseFloat(amount) : amount);
  }

  getLifecycleStageColor(stage: string): string {
    const colors: { [key: string]: string } = {
      subscriber: 'gray',
      lead: 'blue',
      marketingqualifiedlead: 'purple',
      salesqualifiedlead: 'orange',
      opportunity: 'yellow',
      customer: 'green',
      evangelist: 'red'
    };
    return colors[stage?.toLowerCase()] || 'gray';
  }

  getDealStageColor(stage: string): string {
    const colors: { [key: string]: string } = {
      appointmentscheduled: 'gray',
      qualifiedtobuy: 'blue',
      presentationscheduled: 'purple',
      decisionmakerboughtin: 'orange',
      contractsent: 'yellow',
      closedwon: 'green',
      closedlost: 'red'
    };
    return colors[stage?.toLowerCase()] || 'gray';
  }
}

// Export singleton instance
export const hubspotSkills = new HubSpotSkills();
export default hubspotSkills;