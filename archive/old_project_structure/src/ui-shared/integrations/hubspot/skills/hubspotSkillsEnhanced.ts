/**
 * Enhanced HubSpot Integration Skills with AI Integration
 * Advanced HubSpot API interactions with AI-powered features
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
    hs_lead_status?: string;
    createdate?: string;
    lastmodifieddate?: string;
    jobtitle?: string;
    address?: string;
    city?: string;
    state?: string;
    zip?: string;
    country?: string;
    website?: string;
    linkedinbio?: string;
    twitterhandle?: string;
    notes_last_contacted?: string;
    num_unique_conversion_events?: string;
  };
  createdAt?: string;
  updatedAt?: string;
  isArchived?: boolean;
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
    hs_lead_status?: string;
    lifecyclestage?: string;
    total_revenue?: string;
    numberofemployees?: string;
    website?: string;
    phone_number?: string;
    fax?: string;
    annualrevenue?: string;
    hubspot_owner_id?: string;
  };
  isArchived?: boolean;
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
    closed_lost?: string;
    description?: string;
    dealtype?: string;
    probability?: string;
    next_step?: string;
    days_to_close?: string;
    hs_predictive_deal_stage_probability?: string;
    hs_arr?: string;
    hs_projected_amount?: string;
  };
  isArchived?: boolean;
}

export interface HubSpotTicket {
  id: string;
  properties: {
    subject?: string;
    content?: string;
    hs_pipeline?: string;
    hs_pipeline_stage?: string;
    hs_ticket_category?: string;
    hs_ticket_priority?: string;
    createdate?: string;
    closed_date?: string;
    hs_object_id?: string;
    hs_pipeline_agent?: string;
    hs_ticket_priority?: string;
    hs_ticket_state?: string;
    associated_company?: string;
    associated_contact?: string;
  };
  isArchived?: boolean;
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
    unsubscribed: number;
    bounced: number;
    spamreported: number;
  };
  content?: {
    subject?: string;
    from_name?: string;
    reply_to?: string;
    html?: string;
    text?: string;
  };
  segmentation?: {
    contacts_count: number;
    lists_used: string[];
  };
}

export interface HubSpotAnalytics {
  totalContacts: number;
  totalCompanies: number;
  totalDeals: number;
  totalTickets: number;
  totalRevenue: number;
  conversionRate: number;
  averageDealSize: number;
  leadConversionRate: number;
  customerAcquisitionCost: number;
  monthlyRevenue: { month: string; revenue: number; deals: number }[];
  leadStageBreakdown: { [stage: string]: number };
  dealStageBreakdown: { [stage: string]: number };
  topPerformingCampaigns: HubSpotCampaign[];
  campaignPerformance: {
    openRate: number;
    clickRate: number;
    conversionRate: number;
    unsubscribeRate: number;
  };
  salesMetrics: {
    salesCycleLength: number;
    winRate: number;
    averageDealSize: number;
    totalPipelineValue: number;
  };
}

export interface HubSpotAIInsight {
  type: 'lead_scoring' | 'deal_prediction' | 'churn_risk' | 'up_sell' | 'cross_sell';
  title: string;
  description: string;
  confidence: number;
  recommendation: string;
  impact: 'high' | 'medium' | 'low';
  entityId: string;
  entityType: 'contact' | 'company' | 'deal';
  generatedAt: string;
  actionable: boolean;
}

export interface HubSpotWorkflow {
  id: string;
  name: string;
  description?: string;
  type: string;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
  enrolledContacts: number;
  executedActions: number;
  trigger: {
    type: string;
    criteria: any;
  };
  actions: {
    type: string;
    details: any;
  }[];
}

class HubSpotSkillsEnhanced {
  private readonly baseUrl = '/api/hubspot';
  private readonly authUrl = '/auth/hubspot';

  // Authentication methods
  async getStoredTokens(): Promise<HubSpotTokens | null> {
    try {
      const response = await api.get(`${this.authUrl}/status`);
      if (response.data.authenticated) {
        return response.data.tokens;
      }
      return null;
    } catch (error) {
      console.error('Failed to get stored tokens:', error);
      return null;
    }
  }

  async initiateOAuth(): Promise<void> {
    try {
      window.location.href = `${this.authUrl}`;
    } catch (error) {
      throw new Error(`Failed to initiate OAuth: ${error.message}`);
    }
  }

  async handleOAuthCallback(code: string, state: string): Promise<HubSpotTokens> {
    try {
      const response = await api.post(`${this.authUrl}/save`, { code, state });
      return response.data.tokens;
    } catch (error) {
      throw new Error(`OAuth callback failed: ${error.message}`);
    }
  }

  async revokeAuthentication(): Promise<void> {
    try {
      await api.delete(`${this.authUrl}`);
    } catch (error) {
      throw new Error(`Failed to revoke authentication: ${error.message}`);
    }
  }

  // Enhanced Contact methods with AI
  async getContacts(options: {
    limit?: number;
    offset?: number;
    search?: string;
    sort?: string;
    properties?: string[];
    filters?: Array<{
      property: string;
      operator: string;
      value: string | number;
    }>;
    includeAiInsights?: boolean;
  } = {}): Promise<{
    results: HubSpotContact[];
    total: number;
    hasMore: boolean;
    offset: number;
    aiInsights?: HubSpotAIInsight[];
  }> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.sort) params.append('sort', options.sort);
      if (options.properties) params.append('properties', options.properties.join(','));
      if (options.filters) params.append('filters', JSON.stringify(options.filters));
      if (options.includeAiInsights) params.append('ai_insights', 'true');

      const response = await api.get(`${this.baseUrl}/contacts?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get contacts: ${error.message}`);
    }
  }

  async getContact(contactId: string, includeAiInsights?: boolean): Promise<{
    contact: HubSpotContact;
    aiInsights?: HubSpotAIInsight[];
    recommendations?: string[];
    similarContacts?: HubSpotContact[];
  }> {
    try {
      const params = new URLSearchParams();
      if (includeAiInsights) params.append('ai_insights', 'true');

      const response = await api.get(`${this.baseUrl}/contacts/${contactId}?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get contact: ${error.message}`);
    }
  }

  async createContact(contactData: {
    properties: { [key: string]: any };
    associations?: Array<{
      to: { id: string };
      types: Array<{ category: string; type: string }>;
    }>;
    enrichWithAi?: boolean;
  }): Promise<HubSpotContact> {
    try {
      const params = new URLSearchParams();
      if (contactData.enrichWithAi) params.append('enrich', 'true');

      const response = await api.post(`${this.baseUrl}/contacts?${params}`, contactData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create contact: ${error.message}`);
    }
  }

  async updateContact(contactId: string, contactData: {
    properties: { [key: string]: any };
    associations?: Array<{
      to: { id: string };
      types: Array<{ category: string; type: string }>;
    }>;
  }): Promise<HubSpotContact> {
    try {
      const response = await api.put(`${this.baseUrl}/contacts/${contactId}`, contactData);
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

  async enrichContactData(contactId: string): Promise<{
    enrichedProperties: { [key: string]: any };
    confidence: number;
    sources: string[];
  }> {
    try {
      const response = await api.post(`${this.baseUrl}/contacts/${contactId}/enrich`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to enrich contact data: ${error.message}`);
    }
  }

  // Company methods
  async getCompanies(options: {
    limit?: number;
    offset?: number;
    search?: string;
    sort?: string;
    properties?: string[];
    filters?: Array<{
      property: string;
      operator: string;
      value: string | number;
    }>;
  } = {}): Promise<{
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
      if (options.filters) params.append('filters', JSON.stringify(options.filters));

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

  async createCompany(companyData: {
    properties: { [key: string]: any };
    associations?: Array<{
      to: { id: string };
      types: Array<{ category: string; type: string }>;
    }>;
  }): Promise<HubSpotCompany> {
    try {
      const response = await api.post(`${this.baseUrl}/companies`, companyData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create company: ${error.message}`);
    }
  }

  async updateCompany(companyId: string, companyData: {
    properties: { [key: string]: any };
    associations?: Array<{
      to: { id: string };
      types: Array<{ category: string; type: string }>;
    }>;
  }): Promise<HubSpotCompany> {
    try {
      const response = await api.put(`${this.baseUrl}/companies/${companyId}`, companyData);
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

  // Deal methods with AI predictions
  async getDeals(options: {
    limit?: number;
    offset?: number;
    search?: string;
    sort?: string;
    properties?: string[];
    filters?: Array<{
      property: string;
      operator: string;
      value: string | number;
    }>;
    includePredictions?: boolean;
  } = {}): Promise<{
    results: HubSpotDeal[];
    total: number;
    hasMore: boolean;
    offset: number;
    predictions?: Array<{
      dealId: string;
      winProbability: number;
      expectedCloseDate: string;
      riskFactors: string[];
      recommendations: string[];
    }>;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.sort) params.append('sort', options.sort);
      if (options.properties) params.append('properties', options.properties.join(','));
      if (options.filters) params.append('filters', JSON.stringify(options.filters));
      if (options.includePredictions) params.append('predictions', 'true');

      const response = await api.get(`${this.baseUrl}/deals?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get deals: ${error.message}`);
    }
  }

  async getDeal(dealId: string, includePredictions?: boolean): Promise<{
    deal: HubSpotDeal;
    predictions?: {
      winProbability: number;
      expectedCloseDate: string;
      riskFactors: string[];
      recommendations: string[];
      similarDeals: Array<{
        id: string;
        name: string;
        outcome: string;
        amount: number;
        closeDate: string;
      }>;
    };
  }> {
    try {
      const params = new URLSearchParams();
      if (includePredictions) params.append('predictions', 'true');

      const response = await api.get(`${this.baseUrl}/deals/${dealId}?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get deal: ${error.message}`);
    }
  }

  async createDeal(dealData: {
    properties: { [key: string]: any };
    associations?: Array<{
      to: { id: string };
      types: Array<{ category: string; type: string }>;
    }>;
    calculatePrediction?: boolean;
  }): Promise<HubSpotDeal> {
    try {
      const params = new URLSearchParams();
      if (dealData.calculatePrediction) params.append('predict', 'true');

      const response = await api.post(`${this.baseUrl}/deals?${params}`, dealData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create deal: ${error.message}`);
    }
  }

  async updateDeal(dealId: string, dealData: {
    properties: { [key: string]: any };
    associations?: Array<{
      to: { id: string };
      types: Array<{ category: string; type: string }>;
    }>;
  }): Promise<HubSpotDeal> {
    try {
      const response = await api.put(`${this.baseUrl}/deals/${dealId}`, dealData);
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

  // Ticket methods
  async getTickets(options: {
    limit?: number;
    offset?: number;
    search?: string;
    sort?: string;
    properties?: string[];
    filters?: Array<{
      property: string;
      operator: string;
      value: string | number;
    }>;
  } = {}): Promise<{
    results: HubSpotTicket[];
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
      if (options.filters) params.append('filters', JSON.stringify(options.filters));

      const response = await api.get(`${this.baseUrl}/tickets?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get tickets: ${error.message}`);
    }
  }

  async getTicket(ticketId: string): Promise<HubSpotTicket> {
    try {
      const response = await api.get(`${this.baseUrl}/tickets/${ticketId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get ticket: ${error.message}`);
    }
  }

  async createTicket(ticketData: {
    properties: { [key: string]: any };
    associations?: Array<{
      to: { id: string };
      types: Array<{ category: string; type: string }>;
    }>;
  }): Promise<HubSpotTicket> {
    try {
      const response = await api.post(`${this.baseUrl}/tickets`, ticketData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create ticket: ${error.message}`);
    }
  }

  // Campaign methods with advanced analytics
  async getCampaigns(options: {
    limit?: number;
    offset?: number;
    search?: string;
    sort?: string;
    status?: string;
    type?: string;
  } = {}): Promise<{
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
      if (options.status) params.append('status', options.status);
      if (options.type) params.append('type', options.type);

      const response = await api.get(`${this.baseUrl}/campaigns?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get campaigns: ${error.message}`);
    }
  }

  async getCampaign(campaignId: string, includeDetailedMetrics?: boolean): Promise<{
    campaign: HubSpotCampaign;
    detailedMetrics?: {
      openRate: number;
      clickRate: number;
      conversionRate: number;
      unsubscribeRate: number;
      bounceRate: number;
      spamRate: number;
      roi: number;
      costPerAcquisition: number;
    };
    audienceAnalysis?: {
      demographics: { [key: string]: any };
      engagement: { [key: string]: number };
      segments: Array<{ name: string; count: number; performance: number }>;
    };
  }> {
    try {
      const params = new URLSearchParams();
      if (includeDetailedMetrics) params.append('detailed_metrics', 'true');

      const response = await api.get(`${this.baseUrl}/campaigns/${campaignId}?${params}`);
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

  // Enhanced Analytics with AI insights
  async getAnalytics(dateRange?: { from: string; to: string }, options?: {
    includeAiInsights?: boolean;
    includePredictions?: boolean;
    segments?: string[];
  }): Promise<{
    analytics: HubSpotAnalytics;
    aiInsights?: HubSpotAIInsight[];
    predictions?: {
      nextMonthRevenue: number;
      leadsNeeded: number;
      conversionProbability: number;
      churnRisk: Array<{ contactId: string; risk: number; reasons: string[] }>;
    };
    benchmarks?: {
      industryAverage: { [metric: string]: number };
      percentileRanking: { [metric: string]: number };
    };
  }> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }
      if (options?.includeAiInsights) params.append('ai_insights', 'true');
      if (options?.includePredictions) params.append('predictions', 'true');
      if (options?.segments) params.append('segments', options.segments.join(','));

      const response = await api.get(`${this.baseUrl}/analytics?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get analytics: ${error.message}`);
    }
  }

  async getSalesAnalytics(dateRange?: { from: string; to: string }): Promise<{
    salesMetrics: {
      totalRevenue: number;
      newBusinessRevenue: number;
      recurringRevenue: number;
      averageDealSize: number;
      salesCycleLength: number;
      winRate: number;
      dealVelocity: number;
      quotaAttainment: number;
      activities: {
        calls: number;
        emails: number;
        meetings: number;
        demos: number;
      };
    };
    pipelineMetrics: {
      totalPipelineValue: number;
      weightedPipelineValue: number;
      byStage: Array<{ stage: string; count: number; value: number; probability: number }>;
      byOwner: Array<{ owner: string; deals: number; value: number; winRate: number }>;
    };
    predictions: {
        forecast: Array<{ month: string; predicted: number; confidence: number }>;
        atRiskDeals: Array<{ dealId: string; name: string; risk: number; factors: string[] }>;
        recommendedActions: string[];
    };
  }> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/analytics/sales?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get sales analytics: ${error.message}`);
    }
  }

  async getMarketingAnalytics(dateRange?: { from: string; to: string }): Promise<{
    campaignPerformance: {
      totalCampaigns: number;
      averageOpenRate: number;
      averageClickRate: number;
      averageConversionRate: number;
      costPerLead: number;
      costPerAcquisition: number;
      marketingSourcedRevenue: number;
      marketingInfluencedRevenue: number;
    };
    topPerformingCampaigns: HubSpotCampaign[];
    leadQualityMetrics: {
      mqlToSqlConversionRate: number;
      sqlToCustomerConversionRate: number;
      leadToCustomerTime: number;
      leadSourceBreakdown: { [source: string]: number };
    };
    contentPerformance: {
      topPerformingContent: Array<{ title: string; type: string; views: number; conversions: number }>;
      contentEngagement: { [type: string]: number };
    };
  }> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/analytics/marketing?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get marketing analytics: ${error.message}`);
    }
  }

  // AI-Powered Insights and Recommendations
  async getAiInsights(options?: {
    type?: 'all' | 'lead_scoring' | 'deal_prediction' | 'churn_risk' | 'up_sell' | 'cross_sell';
    entityType?: 'all' | 'contact' | 'company' | 'deal';
    limit?: number;
  }): Promise<{
    insights: HubSpotAIInsight[];
    summary: {
      highImpactCount: number;
      actionableCount: number;
      byType: { [type: string]: number };
      byEntityType: { [entityType: string]: number };
    };
  }> {
    try {
      const params = new URLSearchParams();
      if (options?.type && options.type !== 'all') params.append('type', options.type);
      if (options?.entityType && options.entityType !== 'all') params.append('entity_type', options.entityType);
      if (options?.limit) params.append('limit', options.limit.toString());

      const response = await api.get(`${this.baseUrl}/ai/insights?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get AI insights: ${error.message}`);
    }
  }

  async getLeadScoring(contactIds?: string[]): Promise<{
    scores: Array<{
      contactId: string;
      score: number;
      factors: Array<{ factor: string; weight: number; value: number }>;
      grade: 'A' | 'B' | 'C' | 'D' | 'F';
      recommendations: string[];
    }>;
    scoringModel: {
      factors: Array<{ name: string; weight: number; description: string }>;
      thresholds: { [grade: string]: number };
    };
  }> {
    try {
      const requestBody: any = {};
      if (contactIds) requestBody.contact_ids = contactIds;

      const response = await api.post(`${this.baseUrl}/ai/lead-scoring`, requestBody);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get lead scoring: ${error.message}`);
    }
  }

  async getDealPredictions(dealIds?: string[]): Promise<{
    predictions: Array<{
      dealId: string;
      winProbability: number;
      expectedCloseDate: string;
      riskFactors: string[];
      recommendedActions: string[];
      confidence: number;
      similarDeals: Array<{
        id: string;
        name: string;
        outcome: string;
        amount: number;
        closeDate: string;
        similarity: number;
      }>;
    }>;
    modelMetrics: {
      accuracy: number;
      precision: number;
      recall: number;
      features: Array<{ name: string; importance: number }>;
    };
  }> {
    try {
      const requestBody: any = {};
      if (dealIds) requestBody.deal_ids = dealIds;

      const response = await api.post(`${this.baseUrl}/ai/deal-predictions`, requestBody);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get deal predictions: ${error.message}`);
    }
  }

  // Workflow methods
  async getWorkflows(options: {
    limit?: number;
    offset?: number;
    search?: string;
    enabled?: boolean;
  } = {}): Promise<{
    results: HubSpotWorkflow[];
    total: number;
    hasMore: boolean;
    offset: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (typeof options.enabled === 'boolean') params.append('enabled', options.enabled.toString());

      const response = await api.get(`${this.baseUrl}/workflows?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get workflows: ${error.message}`);
    }
  }

  async getWorkflow(workflowId: string): Promise<HubSpotWorkflow> {
    try {
      const response = await api.get(`${this.baseUrl}/workflows/${workflowId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get workflow: ${error.message}`);
    }
  }

  // Utility methods
  formatLifecycleStage(stage: string): string {
    const stageMap: { [key: string]: string } = {
      'subscriber': 'Subscriber',
      'lead': 'Lead',
      'marketingqualifiedlead': 'MQL',
      'salesqualifiedlead': 'SQL',
      'opportunity': 'Opportunity',
      'customer': 'Customer',
      'evangelist': 'Evangelist',
      'other': 'Other'
    };
    return stageMap[stage?.toLowerCase()] || 'Unknown';
  }

  formatDealStage(stage: string): string {
    const stageMap: { [key: string]: string } = {
      'appointmentscheduled': 'Appointment Scheduled',
      'qualifiedtobuy': 'Qualified to Buy',
      'presentationscheduled': 'Presentation Scheduled',
      'decisionmakerboughtin': 'Decision Maker Bought-In',
      'contractsent': 'Contract Sent',
      'closedwon': 'Closed Won',
      'closedlost': 'Closed Lost'
    };
    return stageMap[stage?.toLowerCase()] || 'Unknown';
  }

  formatDate(dateString: string): string {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString();
  }

  formatCurrency(amount: string | number): string {
    if (!amount) return '$0';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(typeof amount === 'string' ? parseFloat(amount) : amount);
  }

  getLifecycleStageColor(stage: string): string {
    const colors: { [key: string]: string } = {
      'subscriber': 'gray',
      'lead': 'blue',
      'marketingqualifiedlead': 'purple',
      'salesqualifiedlead': 'orange',
      'opportunity': 'yellow',
      'customer': 'green',
      'evangelist': 'red'
    };
    return colors[stage?.toLowerCase()] || 'gray';
  }

  getDealStageColor(stage: string): string {
    const colors: { [key: string]: string } = {
      'appointmentscheduled': 'gray',
      'qualifiedtobuy': 'blue',
      'presentationscheduled': 'purple',
      'decisionmakerboughtin': 'orange',
      'contractsent': 'yellow',
      'closedwon': 'green',
      'closedlost': 'red'
    };
    return colors[stage?.toLowerCase()] || 'gray';
  }

  getAiInsightColor(insight: HubSpotAIInsight): string {
    const impactColors: { [key: string]: string } = {
      'high': 'red',
      'medium': 'yellow',
      'low': 'gray'
    };
    return impactColors[insight.impact] || 'gray';
  }

  getAiInsightTypeIcon(type: string): string {
    const iconMap: { [key: string]: string } = {
      'lead_scoring': '🎯',
      'deal_prediction': '💰',
      'churn_risk': '⚠️',
      'up_sell': '📈',
      'cross_sell': '🔄'
    };
    return iconMap[type] || '💡';
  }

  // Health check
  async getHealthStatus(): Promise<{
    status: 'healthy' | 'unhealthy';
    authenticated: boolean;
    lastSync?: string;
    message?: string;
    aiFeaturesEnabled: boolean;
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
        aiFeaturesEnabled: false,
        version: 'unknown'
      };
    }
  }
}

// Export singleton instance
export const hubspotSkillsEnhanced = new HubSpotSkillsEnhanced();
export default hubspotSkillsEnhanced;