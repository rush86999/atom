/**
 * Tests for HubSpot API Service
 *
 * Tests the HubSpot API client wrapper
 */

import { hubspotApi } from '../hubspotApi';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods

// Mock fetch

describe('HubSpot API Service', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    global.mockFetch = global.fetch;
    jest.clearAllMocks();
  });

  describe('exports', () => {
    it('should export hubspotApi instance', () => {
      expect(hubspotApi).toBeDefined();
      expect(typeof hubspotApi).toBe('object');
    });

    it('should have getAuthStatus method', () => {
      expect(hubspotApi.getAuthStatus).toBeDefined();
      expect(typeof hubspotApi.getAuthStatus).toBe('function');
    });

    it('should have connectHubSpot method', () => {
      expect(hubspotApi.connectHubSpot).toBeDefined();
      expect(typeof hubspotApi.connectHubSpot).toBe('function');
    });

    it('should have disconnectHubSpot method', () => {
      expect(hubspotApi.disconnectHubSpot).toBeDefined();
      expect(typeof hubspotApi.disconnectHubSpot).toBe('function');
    });

    it('should have getContacts method', () => {
      expect(hubspotApi.getContacts).toBeDefined();
      expect(typeof hubspotApi.getContacts).toBe('function');
    });

    it('should have getContact method', () => {
      expect(hubspotApi.getContact).toBeDefined();
      expect(typeof hubspotApi.getContact).toBe('function');
    });

    it('should have createContact method', () => {
      expect(hubspotApi.createContact).toBeDefined();
      expect(typeof hubspotApi.createContact).toBe('function');
    });

    it('should have updateContact method', () => {
      expect(hubspotApi.updateContact).toBeDefined();
      expect(typeof hubspotApi.updateContact).toBe('function');
    });

    it('should have deleteContact method', () => {
      expect(hubspotApi.deleteContact).toBeDefined();
      expect(typeof hubspotApi.deleteContact).toBe('function');
    });

    it('should have getAnalytics method', () => {
      expect(hubspotApi.getAnalytics).toBeDefined();
      expect(typeof hubspotApi.getAnalytics).toBe('function');
    });

    it('should have getCampaigns method', () => {
      expect(hubspotApi.getCampaigns).toBeDefined();
      expect(typeof hubspotApi.getCampaigns).toBe('function');
    });

    it('should have getPipelines method', () => {
      expect(hubspotApi.getPipelines).toBeDefined();
      expect(typeof hubspotApi.getPipelines).toBe('function');
    });

    it('should have getLists method', () => {
      expect(hubspotApi.getLists).toBeDefined();
      expect(typeof hubspotApi.getLists).toBe('function');
    });

    it('should have getAIPredictions method', () => {
      expect(hubspotApi.getAIPredictions).toBeDefined();
      expect(typeof hubspotApi.getAIPredictions).toBe('function');
    });
  });

  describe('getAuthStatus', () => {
    it('should return connected status when authenticated', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          connected: true,
          portal: { id: '12345', name: 'Test Portal' },
        }),
      });

      const result = await hubspotApi.getAuthStatus();

      expect(result).toEqual({
        connected: true,
        portal: { id: '12345', name: 'Test Portal' },
      });
    });

    it('should return disconnected status when not authenticated', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      });

      const result = await hubspotApi.getAuthStatus();

      expect(result).toEqual({ connected: false });
    });

    it('should return disconnected status on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      const result = await hubspotApi.getAuthStatus();

      expect(result).toEqual({ connected: false });
    });
  });

  describe('connectHubSpot', () => {
    it('should return auth URL on success', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          authUrl: 'https://app.hubspot.com/oauth/authorize',
        }),
      });

      const result = await hubspotApi.connectHubSpot();

      expect(result).toEqual({
        success: true,
        authUrl: 'https://app.hubspot.com/oauth/authorize',
      });
    });

    it('should return error on failure', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Connection failed'));

      const result = await hubspotApi.connectHubSpot();

      expect(result).toEqual({
        success: false,
        error: 'Connection failed',
      });
    });
  });

  describe('disconnectHubSpot', () => {
    it('should return success on disconnect', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

      const result = await hubspotApi.disconnectHubSpot();

      expect(result).toEqual({ success: true });
    });

    it('should return error on disconnect failure', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Disconnect failed'));

      const result = await hubspotApi.disconnectHubSpot();

      expect(result).toEqual({
        success: false,
        error: 'Disconnect failed',
      });
    });
  });

  describe('getContacts', () => {
    it('should return contacts list', async () => {
      const mockContacts = [
        { id: '1', email: 'test1@example.com' },
        { id: '2', email: 'test2@example.com' },
      ];

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          contacts: mockContacts,
          total: 2,
          hasMore: false,
        }),
      });

      const result = await hubspotApi.getContacts();

      expect(result).toEqual({
        contacts: mockContacts,
        total: 2,
        hasMore: false,
      });
    });

    it('should build query string with params', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ contacts: [], total: 0, hasMore: false }),
      });

      await hubspotApi.getContacts({
        limit: 10,
        after: 'cursor123',
        properties: ['email', 'name'],
      });

      const fetchCall = (global.mockFetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toContain('limit=10');
      expect(fetchCall[0]).toContain('after=cursor123');
      expect(fetchCall[0]).toContain('properties=email%2Cname');
    });

    it('should handle missing response data gracefully', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const result = await hubspotApi.getContacts();

      expect(result).toEqual({
        contacts: [],
        total: 0,
        hasMore: false,
      });
    });

    it('should return empty list on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

      const result = await hubspotApi.getContacts();

      expect(result).toEqual({
        contacts: [],
        total: 0,
        hasMore: false,
      });
    });
  });

  describe('getContact', () => {
    it('should return contact by ID', async () => {
      const mockContact = { id: '123', email: 'contact@example.com' };

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ contact: mockContact }),
      });

      const result = await hubspotApi.getContact('123');

      expect(result).toEqual(mockContact);
    });

    it('should return null on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Not found'));

      const result = await hubspotApi.getContact('123');

      expect(result).toBeNull();
    });

    it('should return null when contact not in response', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const result = await hubspotApi.getContact('123');

      expect(result).toBeNull();
    });
  });

  describe('createContact', () => {
    it('should create contact successfully', async () => {
      const contactData = { email: 'new@example.com', name: 'New Contact' };
      const createdContact = { id: '456', ...contactData };

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ contact: createdContact }),
      });

      const result = await hubspotApi.createContact(contactData);

      expect(result).toEqual({
        success: true,
        contact: createdContact,
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/contacts',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(contactData),
        })
      );
    });

    it('should return error on failure', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Creation failed'));

      const result = await hubspotApi.createContact({ email: 'test@example.com' });

      expect(result).toEqual({
        success: false,
        error: 'Creation failed',
      });
    });
  });

  describe('updateContact', () => {
    it('should update contact successfully', async () => {
      const updates = { email: 'updated@example.com' };
      const updatedContact = { id: '123', ...updates };

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ contact: updatedContact }),
      });

      const result = await hubspotApi.updateContact('123', updates);

      expect(result).toEqual({
        success: true,
        contact: updatedContact,
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/contacts/123',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(updates),
        })
      );
    });

    it('should return error on failure', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Update failed'));

      const result = await hubspotApi.updateContact('123', { email: 'test@example.com' });

      expect(result).toEqual({
        success: false,
        error: 'Update failed',
      });
    });
  });

  describe('deleteContact', () => {
    it('should delete contact successfully', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const result = await hubspotApi.deleteContact('123');

      expect(result).toEqual({ success: true });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/contacts/123',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });

    it('should return error on failure', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Delete failed'));

      const result = await hubspotApi.deleteContact('123');

      expect(result).toEqual({
        success: false,
        error: 'Delete failed',
      });
    });
  });

  describe('getAnalytics', () => {
    it('should return analytics data', async () => {
      const mockAnalytics = {
        contacts: 100,
        companies: 50,
        deals: 25,
        monthlyGrowth: 10.5,
        quarterlyGrowth: 25.3,
      };

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAnalytics,
      });

      const result = await hubspotApi.getAnalytics();

      expect(result).toEqual(mockAnalytics);
    });

    it('should return default values on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Analytics error'));

      const result = await hubspotApi.getAnalytics();

      expect(result).toEqual({
        contacts: 0,
        companies: 0,
        deals: 0,
        monthlyGrowth: 0,
        quarterlyGrowth: 0,
      });
    });
  });

  describe('getCampaigns', () => {
    it('should return campaigns list', async () => {
      const mockCampaigns = [
        { id: '1', name: 'Campaign 1', status: 'active', createdAt: '2024-01-01' },
        { id: '2', name: 'Campaign 2', status: 'paused', createdAt: '2024-01-02' },
      ];

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ campaigns: mockCampaigns }),
      });

      const result = await hubspotApi.getCampaigns();

      expect(result).toEqual(mockCampaigns);
    });

    it('should return empty array on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Campaigns error'));

      const result = await hubspotApi.getCampaigns();

      expect(result).toEqual([]);
    });
  });

  describe('getPipelines', () => {
    it('should return pipelines list', async () => {
      const mockPipelines = [
        {
          id: '1',
          label: 'Sales Pipeline',
          displayOrder: 1,
          stages: [
            { id: 's1', label: 'Prospecting', displayOrder: 1, probability: 10 },
            { id: 's2', label: 'Qualification', displayOrder: 2, probability: 30 },
          ],
        },
      ];

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pipelines: mockPipelines }),
      });

      const result = await hubspotApi.getPipelines();

      expect(result).toEqual(mockPipelines);
    });

    it('should return empty array on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Pipelines error'));

      const result = await hubspotApi.getPipelines();

      expect(result).toEqual([]);
    });
  });

  describe('getLists', () => {
    it('should return lists', async () => {
      const mockLists = [
        { id: '1', name: 'Active Customers', listType: 'STATIC', createdAt: '2024-01-01' },
        { id: '2', name: 'Hot Leads', listType: 'DYNAMIC', createdAt: '2024-01-02' },
      ];

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ lists: mockLists }),
      });

      const result = await hubspotApi.getLists();

      expect(result).toEqual(mockLists);
    });

    it('should return empty array on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Lists error'));

      const result = await hubspotApi.getLists();

      expect(result).toEqual([]);
    });
  });

  describe('getAIPredictions', () => {
    it('should return AI predictions', async () => {
      const mockPredictions = {
        models: ['model1', 'model2'],
        predictions: [{ score: 0.85 }, { score: 0.92 }],
        forecast: [100, 110, 120],
      };

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPredictions,
      });

      const result = await hubspotApi.getAIPredictions();

      expect(result).toEqual(mockPredictions);
    });

    it('should return default structure on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('AI error'));

      const result = await hubspotApi.getAIPredictions();

      expect(result).toEqual({
        models: [],
        predictions: [],
        forecast: [],
      });
    });
  });

  // Additional tests for extended coverage
  describe('getCompanies', () => {
    it('should return companies list', async () => {
      const mockCompanies = [
        { id: '1', name: 'Company 1', domain: 'company1.com' },
        { id: '2', name: 'Company 2', domain: 'company2.com' },
      ];

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          companies: mockCompanies,
          total: 2,
          hasMore: false,
        }),
      });

      const result = await hubspotApi.getCompanies();

      expect(result).toEqual({
        companies: mockCompanies,
        total: 2,
        hasMore: false,
      });
    });

    it('should handle empty companies list', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ companies: [], total: 0, hasMore: false }),
      });

      const result = await hubspotApi.getCompanies();

      expect(result.companies).toEqual([]);
    });

    it('should return empty list on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

      const result = await hubspotApi.getCompanies();

      expect(result).toEqual({
        companies: [],
        total: 0,
        hasMore: false,
      });
    });
  });

  describe('getDeals', () => {
    it('should return deals list', async () => {
      const mockDeals = [
        { id: '1', amount: 10000, stage: 'proposal' },
        { id: '2', amount: 25000, stage: 'negotiation' },
      ];

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          deals: mockDeals,
          total: 2,
          hasMore: false,
        }),
      });

      const result = await hubspotApi.getDeals();

      expect(result).toEqual({
        deals: mockDeals,
        total: 2,
        hasMore: false,
      });
    });

    it('should return an empty list on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

      const result = await hubspotApi.getDeals();

      expect(result).toEqual({ deals: [], total: 0, hasMore: false });
    });

    it('should handle pagination parameters', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ deals: [], total: 0, hasMore: false }),
      });

      await hubspotApi.getDeals({
        limit: 50,
        after: 'cursor123',
        properties: ['amount', 'stage'],
      });

      const fetchCall = (global.mockFetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toContain('limit=50');
      expect(fetchCall[0]).toContain('after=cursor123');
      expect(fetchCall[0]).toContain('properties=amount%2Cstage');
    });
  });

  describe('createDeal', () => {
    it('should create deal successfully', async () => {
      const dealData = { amount: 50000, stage: 'proposal' };
      const createdDeal = { id: '789', ...dealData };

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ deal: createdDeal }),
      });

      const result = await hubspotApi.createDeal(dealData);

      expect(result).toEqual({
        success: true,
        deal: createdDeal,
      });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/deals',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(dealData),
        })
      );
    });
  });

  describe('updateDeal', () => {
    it('should update deal successfully', async () => {
      const updates = { amount: 75000 };
      const updatedDeal = { id: '123', ...updates };

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ deal: updatedDeal }),
      });

      const result = await hubspotApi.updateDeal('123', updates);

      expect(result).toEqual({
        success: true,
        deal: updatedDeal,
      });
    });
  });

  describe('searchContacts', () => {
    it('should search contacts successfully', async () => {
      const mockContacts = [
        { id: '1', email: 'john@example.com', firstName: 'John' },
      ];

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ contacts: mockContacts }),
      });

      const result = await hubspotApi.searchContacts('john');

      expect(result).toEqual(mockContacts);
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/contacts/search',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ query: 'john', filters: undefined }),
        })
      );
    });

    it('should return empty array on search error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('Search error'));

      const result = await hubspotApi.searchContacts('test');

      expect(result).toEqual([]);
    });
  });

  describe('HTTP error handling', () => {
    it('should log and throw on HTTP errors', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(hubspotApi.getContact('123')).resolves.toBeNull();

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('HubSpot API error'),
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe('fetchWithErrorHandling', () => {
    it('should merge custom headers with defaults', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: 'test' }),
      });

      await hubspotApi.connectHubSpot();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });
  });

  // ==========================================================================
  // Extended coverage: company/deal lookups, pipelines, analytics, lists,
  // templates, email, searches, and error paths
  // ==========================================================================
  describe('getCompany', () => {
    it('should return the company when found', async () => {
      const company = { id: 'c1', name: 'Acme', domain: 'acme.com' };
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ company }),
      });

      const result = await hubspotApi.getCompany('c1');

      expect(result).toEqual(company);
      expect(global.fetch).toHaveBeenCalledWith('/api/hubspot/companies/c1', expect.anything());
    });

    it('should return null when the company is missing', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await expect(hubspotApi.getCompany('c1')).resolves.toBeNull();
    });

    it('should return null on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));

      await expect(hubspotApi.getCompany('c1')).resolves.toBeNull();
    });
  });

  describe('getCompanies with params', () => {
    it('should append limit/after/properties query parameters', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ companies: [], total: 0, hasMore: false }),
      });

      await hubspotApi.getCompanies({
        limit: 25,
        after: 'cur',
        properties: ['domain', 'name'],
      });

      const url = (global.mockFetch as jest.Mock).mock.calls[0][0];
      expect(url).toContain('limit=25');
      expect(url).toContain('after=cur');
      expect(url).toContain('properties=domain%2Cname');
    });
  });

  describe('getDeal', () => {
    it('should return the deal when found', async () => {
      const deal = { id: 'd1', amount: 1000 };
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ deal }),
      });

      const result = await hubspotApi.getDeal('d1');

      expect(result).toEqual(deal);
      expect(global.fetch).toHaveBeenCalledWith('/api/hubspot/deals/d1', expect.anything());
    });

    it('should return null when the deal is missing or on error', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
      await expect(hubspotApi.getDeal('d1')).resolves.toBeNull();

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.getDeal('d1')).resolves.toBeNull();
    });
  });

  describe('createDeal / updateDeal error paths', () => {
    it('createDeal should return a failure payload on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('create failed'));

      const result = await hubspotApi.createDeal({ amount: 1 });

      expect(result).toEqual({ success: false, error: 'create failed' });
    });

    it('updateDeal should return a failure payload on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('update failed'));

      const result = await hubspotApi.updateDeal('d1', { amount: 2 });

      expect(result).toEqual({ success: false, error: 'update failed' });
    });
  });

  describe('getCampaign', () => {
    it('should return the campaign when found', async () => {
      const campaign = { id: 'cp1', name: 'Launch' };
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ campaign }),
      });

      const result = await hubspotApi.getCampaign('cp1');

      expect(result).toEqual(campaign);
    });

    it('should return null when missing or on error', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
      await expect(hubspotApi.getCampaign('cp1')).resolves.toBeNull();

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.getCampaign('cp1')).resolves.toBeNull();
    });
  });

  describe('getPipelineStages', () => {
    it('should return stages when present', async () => {
      const stages = [{ id: 's1', label: 'Open' }];
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ stages }),
      });

      const result = await hubspotApi.getPipelineStages('p1');

      expect(result).toEqual(stages);
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/pipelines/p1/stages',
        expect.anything()
      );
    });

    it('should return an empty array when missing or on error', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
      await expect(hubspotApi.getPipelineStages('p1')).resolves.toEqual([]);

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.getPipelineStages('p1')).resolves.toEqual([]);
    });
  });

  describe('analytics endpoints', () => {
    it('getDealAnalytics should return the payload or an empty object on error', async () => {
      const payload = { deals: [], revenue: 0 };
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => payload });
      await expect(hubspotApi.getDealAnalytics()).resolves.toEqual(payload);

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.getDealAnalytics()).resolves.toEqual({});
    });

    it('getContactAnalytics should return the payload or an empty object on error', async () => {
      const payload = { contacts: 5 };
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => payload });
      await expect(hubspotApi.getContactAnalytics()).resolves.toEqual(payload);

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.getContactAnalytics()).resolves.toEqual({});
    });

    it('getCampaignAnalytics should return the payload or an empty object on error', async () => {
      const payload = { campaigns: [] };
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => payload });
      await expect(hubspotApi.getCampaignAnalytics()).resolves.toEqual(payload);

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.getCampaignAnalytics()).resolves.toEqual({});
    });
  });

  describe('createList', () => {
    it('should create a list successfully', async () => {
      const list = { id: 'l1', name: 'VIP', type: 'static' };
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ list }),
      });

      const result = await hubspotApi.createList({ name: 'VIP', type: 'static' });

      expect(result).toEqual({ success: true, list });
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/lists',
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('should return a failure payload on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('list failed'));

      const result = await hubspotApi.createList({ name: 'X', type: 'static' });

      expect(result).toEqual({ success: false, error: 'list failed' });
    });
  });

  describe('getEmailTemplates', () => {
    it('should return templates or an empty array on error', async () => {
      const templates = [{ id: 't1', name: 'Intro' }];
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ templates }),
      });
      await expect(hubspotApi.getEmailTemplates()).resolves.toEqual(templates);

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.getEmailTemplates()).resolves.toEqual([]);
    });
  });

  describe('sendEmail', () => {
    it('should send successfully', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({}) });

      const result = await hubspotApi.sendEmail('t1', ['c1', 'c2']);

      expect(result).toEqual({ success: true });
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/hubspot/email/send',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ templateId: 't1', contactIds: ['c1', 'c2'] }),
        })
      );
    });

    it('should return a failure payload on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('send failed'));

      const result = await hubspotApi.sendEmail('t1', []);

      expect(result).toEqual({ success: false, error: 'send failed' });
    });
  });

  describe('searchCompanies / searchDeals', () => {
    it('searchCompanies should return matches or an empty array on error', async () => {
      const companies = [{ id: 'c1', name: 'Acme' }];
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ companies }),
      });
      await expect(hubspotApi.searchCompanies('acme')).resolves.toEqual(companies);

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.searchCompanies('acme')).resolves.toEqual([]);
    });

    it('searchDeals should return matches or an empty array on error', async () => {
      const deals = [{ id: 'd1' }];
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ deals }),
      });
      await expect(hubspotApi.searchDeals('acme')).resolves.toEqual(deals);

      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));
      await expect(hubspotApi.searchDeals('acme')).resolves.toEqual([]);
    });
  });

  describe('getAIPredictions error path', () => {
    it('should return an empty predictions payload on error', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('ai down'));

      const result = await hubspotApi.getAIPredictions();

      expect(result).toEqual({ models: [], predictions: [], forecast: [] });
    });
  });
});
