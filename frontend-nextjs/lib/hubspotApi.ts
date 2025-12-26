// Simple HubSpot API service to fix import errors
import { HubSpotContact, HubSpotCompany, HubSpotDeal, HubSpotActivity } from '../components/integrations/hubspot/HubSpotSearch'

export interface HubSpotAuthStatus {
  connected: boolean
  portal?: {
    id: string
    name: string
  }
}

export interface HubSpotAnalytics {
  contacts: number
  companies: number
  deals: number
  monthlyGrowth: number
  quarterlyGrowth: number
}

export interface HubSpotCampaign {
  id: string
  name: string
  status: string
  createdAt: string
}

export interface HubSpotPipeline {
  id: string
  label: string
  displayOrder: number
  stages: HubSpotPipelineStage[]
}

export interface HubSpotPipelineStage {
  id: string
  label: string
  displayOrder: number
  probability: number
}

export interface HubSpotList {
  id: string
  name: string
  listType: string
  createdAt: string
}

export interface HubSpotEmailTemplate {
  id: string
  name: string
  subject: string
  createdAt: string
}

// API endpoints
const API_BASE = '/api/hubspot'
const INTEGRATION_BASE = '/api/integrations/hubspot'

class HubSpotApiService {
  private async fetchWithErrorHandling(url: string, options: RequestInit = {}) {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error(`HubSpot API error for ${url}:`, error)
      throw error
    }
  }

  // Authentication methods
  async getAuthStatus(): Promise<HubSpotAuthStatus> {
    try {
      const data = await this.fetchWithErrorHandling(`${INTEGRATION_BASE}/health`)
      return {
        connected: data.connected || false,
        portal: data.portal,
      }
    } catch (error) {
      return { connected: false }
    }
  }

  async connectHubSpot(): Promise<{ success: boolean; authUrl?: string; error?: string }> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/oauth/start`, {
        method: 'POST',
      })
      return data
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      }
    }
  }

  async disconnectHubSpot(): Promise<{ success: boolean; error?: string }> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/oauth/revoke`, {
        method: 'POST',
      })
      return data
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      }
    }
  }

  // Contact methods
  async getContacts(params?: {
    limit?: number
    after?: string
    properties?: string[]
  }): Promise<{ contacts: HubSpotContact[]; total: number; hasMore: boolean }> {
    try {
      const queryParams = new URLSearchParams()
      if (params?.limit) {
        queryParams.append('limit', params.limit.toString())
      }
      if (params?.after) {
        queryParams.append('after', params.after)
      }
      if (params?.properties) {
        queryParams.append('properties', params.properties.join(','))
      }

      const url = `${API_BASE}/contacts${queryParams.toString() ? `?${queryParams}` : ''}`
      const data = await this.fetchWithErrorHandling(url)

      return {
        contacts: data.contacts || [],
        total: data.total || 0,
        hasMore: data.hasMore || false,
      }
    } catch (error) {
      return { contacts: [], total: 0, hasMore: false }
    }
  }

  async getContact(contactId: string): Promise<HubSpotContact | null> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/contacts/${contactId}`)
      return data.contact || null
    } catch (error) {
      return null
    }
  }

  async createContact(contactData: Partial<HubSpotContact>): Promise<{ success: boolean; contact?: HubSpotContact; error?: string }> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/contacts`, {
        method: 'POST',
        body: JSON.stringify(contactData),
      })
      return { success: true, contact: data.contact }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to create contact',
      }
    }
  }

  async updateContact(contactId: string, updates: Partial<HubSpotContact>): Promise<{ success: boolean; contact?: HubSpotContact; error?: string }> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/contacts/${contactId}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
      })
      return { success: true, contact: data.contact }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to update contact',
      }
    }
  }

  async deleteContact(contactId: string): Promise<{ success: boolean; error?: string }> {
    try {
      await this.fetchWithErrorHandling(`${API_BASE}/contacts/${contactId}`, {
        method: 'DELETE',
      })
      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to delete contact',
      }
    }
  }

  // Company methods
  async getCompanies(params?: {
    limit?: number
    after?: string
    properties?: string[]
  }): Promise<{ companies: HubSpotCompany[]; total: number; hasMore: boolean }> {
    try {
      const queryParams = new URLSearchParams()
      if (params?.limit) {
        queryParams.append('limit', params.limit.toString())
      }
      if (params?.after) {
        queryParams.append('after', params.after)
      }
      if (params?.properties) {
        queryParams.append('properties', params.properties.join(','))
      }

      const url = `${API_BASE}/companies${queryParams.toString() ? `?${queryParams}` : ''}`
      const data = await this.fetchWithErrorHandling(url)

      return {
        companies: data.companies || [],
        total: data.total || 0,
        hasMore: data.hasMore || false,
      }
    } catch (error) {
      return { companies: [], total: 0, hasMore: false }
    }
  }

  async getCompany(companyId: string): Promise<HubSpotCompany | null> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/companies/${companyId}`)
      return data.company || null
    } catch (error) {
      return null
    }
  }

  // Deal methods
  async getDeals(params?: {
    limit?: number
    after?: string
    properties?: string[]
  }): Promise<{ deals: HubSpotDeal[]; total: number; hasMore: boolean }> {
    try {
      const queryParams = new URLSearchParams()
      if (params?.limit) {
        queryParams.append('limit', params.limit.toString())
      }
      if (params?.after) {
        queryParams.append('after', params.after)
      }
      if (params?.properties) {
        queryParams.append('properties', params.properties.join(','))
      }

      const url = `${API_BASE}/deals${queryParams.toString() ? `?${queryParams}` : ''}`
      const data = await this.fetchWithErrorHandling(url)

      return {
        deals: data.deals || [],
        total: data.total || 0,
        hasMore: data.hasMore || false,
      }
    } catch (error) {
      return { deals: [], total: 0, hasMore: false }
    }
  }

  async getDeal(dealId: string): Promise<HubSpotDeal | null> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/deals/${dealId}`)
      return data.deal || null
    } catch (error) {
      return null
    }
  }

  async createDeal(dealData: Partial<HubSpotDeal>): Promise<{ success: boolean; deal?: HubSpotDeal; error?: string }> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/deals`, {
        method: 'POST',
        body: JSON.stringify(dealData),
      })
      return { success: true, deal: data.deal }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to create deal',
      }
    }
  }

  async updateDeal(dealId: string, updates: Partial<HubSpotDeal>): Promise<{ success: boolean; deal?: HubSpotDeal; error?: string }> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/deals/${dealId}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
      })
      return { success: true, deal: data.deal }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to update deal',
      }
    }
  }

  // Campaign methods
  async getCampaigns(): Promise<HubSpotCampaign[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/campaigns`)
      return data.campaigns || []
    } catch (error) {
      return []
    }
  }

  async getCampaign(campaignId: string): Promise<HubSpotCampaign | null> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/campaigns/${campaignId}`)
      return data.campaign || null
    } catch (error) {
      return null
    }
  }

  // Pipeline methods
  async getPipelines(): Promise<HubSpotPipeline[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/pipelines`)
      return data.pipelines || []
    } catch (error) {
      return []
    }
  }

  async getPipelineStages(pipelineId: string): Promise<HubSpotPipelineStage[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/pipelines/${pipelineId}/stages`)
      return data.stages || []
    } catch (error) {
      return []
    }
  }

  // Analytics methods
  async getAnalytics(): Promise<HubSpotAnalytics> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/analytics`)
      return data
    } catch (error) {
      return {
        contacts: 0,
        companies: 0,
        deals: 0,
        monthlyGrowth: 0,
        quarterlyGrowth: 0,
      }
    }
  }

  async getDealAnalytics(): Promise<any> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/analytics/deals`)
      return data
    } catch (error) {
      return {}
    }
  }

  async getContactAnalytics(): Promise<any> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/analytics/contacts`)
      return data
    } catch (error) {
      return {}
    }
  }

  async getCampaignAnalytics(): Promise<any> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/analytics/campaigns`)
      return data
    } catch (error) {
      return {}
    }
  }

  // List methods
  async getLists(): Promise<HubSpotList[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/lists`)
      return data.lists || []
    } catch (error) {
      return []
    }
  }

  async createList(listData: { name: string; type: string }): Promise<{ success: boolean; list?: HubSpotList; error?: string }> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/lists`, {
        method: 'POST',
        body: JSON.stringify(listData),
      })
      return { success: true, list: data.list }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to create list',
      }
    }
  }

  // Email methods
  async getEmailTemplates(): Promise<HubSpotEmailTemplate[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/templates`)
      return data.templates || []
    } catch (error) {
      return []
    }
  }

  async sendEmail(templateId: string, contactIds: string[]): Promise<{ success: boolean; error?: string }> {
    try {
      await this.fetchWithErrorHandling(`${API_BASE}/email/send`, {
        method: 'POST',
        body: JSON.stringify({ templateId, contactIds }),
      })
      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to send email',
      }
    }
  }

  // Search methods
  async searchContacts(query: string, filters?: any): Promise<HubSpotContact[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/contacts/search`, {
        method: 'POST',
        body: JSON.stringify({ query, filters }),
      })
      return data.contacts || []
    } catch (error) {
      return []
    }
  }

  async searchCompanies(query: string, filters?: any): Promise<HubSpotCompany[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/companies/search`, {
        method: 'POST',
        body: JSON.stringify({ query, filters }),
      })
      return data.companies || []
    } catch (error) {
      return []
    }
  }

  async searchDeals(query: string, filters?: any): Promise<HubSpotDeal[]> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/deals/search`, {
        method: 'POST',
        body: JSON.stringify({ query, filters }),
      })
      return data.deals || []
    } catch (error) {
      return []
    }
  }

  async getAIPredictions(): Promise<any> {
    try {
      const data = await this.fetchWithErrorHandling(`${API_BASE}/ai/predictions`)
      return data
    } catch (error) {
      return {
        models: [],
        predictions: [],
        forecast: [],
      }
    }
  }
}

export const hubspotApi = new HubSpotApiService()
