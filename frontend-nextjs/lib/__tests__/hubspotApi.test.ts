/**
 * Tests for HubSpot API Service
 *
 * Tests the HubSpot API client wrapper
 */

import { hubspotApi } from '../hubspotApi';

// Mock fetch
global.fetch = jest.fn();

describe('HubSpot API Service', () => {
  beforeEach(() => {
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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      });

      const result = await hubspotApi.getAuthStatus();

      expect(result).toEqual({ connected: false });
    });

    it('should return disconnected status on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      const result = await hubspotApi.getAuthStatus();

      expect(result).toEqual({ connected: false });
    });
  });

  describe('connectHubSpot', () => {
    it('should return auth URL on success', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Connection failed'));

      const result = await hubspotApi.connectHubSpot();

      expect(result).toEqual({
        success: false,
        error: 'Connection failed',
      });
    });
  });

  describe('disconnectHubSpot', () => {
    it('should return success on disconnect', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

      const result = await hubspotApi.disconnectHubSpot();

      expect(result).toEqual({ success: true });
    });

    it('should return error on disconnect failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Disconnect failed'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ contacts: [], total: 0, hasMore: false }),
      });

      await hubspotApi.getContacts({
        limit: 10,
        after: 'cursor123',
        properties: ['email', 'name'],
      });

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      expect(fetchCall[0]).toContain('limit=10');
      expect(fetchCall[0]).toContain('after=cursor123');
      expect(fetchCall[0]).toContain('properties=email%2Cname');
    });

    it('should handle missing response data gracefully', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ contact: mockContact }),
      });

      const result = await hubspotApi.getContact('123');

      expect(result).toEqual(mockContact);
    });

    it('should return null on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Not found'));

      const result = await hubspotApi.getContact('123');

      expect(result).toBeNull();
    });

    it('should return null when contact not in response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Creation failed'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Update failed'));

      const result = await hubspotApi.updateContact('123', { email: 'test@example.com' });

      expect(result).toEqual({
        success: false,
        error: 'Update failed',
      });
    });
  });

  describe('deleteContact', () => {
    it('should delete contact successfully', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Delete failed'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAnalytics,
      });

      const result = await hubspotApi.getAnalytics();

      expect(result).toEqual(mockAnalytics);
    });

    it('should return default values on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Analytics error'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ campaigns: mockCampaigns }),
      });

      const result = await hubspotApi.getCampaigns();

      expect(result).toEqual(mockCampaigns);
    });

    it('should return empty array on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Campaigns error'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ pipelines: mockPipelines }),
      });

      const result = await hubspotApi.getPipelines();

      expect(result).toEqual(mockPipelines);
    });

    it('should return empty array on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Pipelines error'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ lists: mockLists }),
      });

      const result = await hubspotApi.getLists();

      expect(result).toEqual(mockLists);
    });

    it('should return empty array on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Lists error'));

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

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPredictions,
      });

      const result = await hubspotApi.getAIPredictions();

      expect(result).toEqual(mockPredictions);
    });

    it('should return default structure on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('AI error'));

      const result = await hubspotApi.getAIPredictions();

      expect(result).toEqual({
        models: [],
        predictions: [],
        forecast: [],
      });
    });
  });

  describe('HTTP error handling', () => {
    it('should log and throw on HTTP errors', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
});
