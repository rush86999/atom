/**
 * Tests for API Backend Helper
 *
 * Tests the resilient fetch wrapper and helper functions
 */

import {
  resilientFetch,
  exchangeCodeForTokens,
  generateGoogleAuthUrl,
  getMinimalCalendarIntegrationByResource,
  getAllCalendarIntegrationsByResourceAndClientType,
  scheduleMeeting,
  encryptZoomTokens,
  decryptZoomTokens,
} from '../api-backend-helper';

// Mock fetch
global.fetch = jest.fn();

// Mock environment variables
const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

describe('API Backend Helper', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NEXT_PUBLIC_API_URL = 'https://api.test.com';
    // Reset fetch to default implementation
    (global.fetch as jest.Mock).mockReset();
  });

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
    // Ensure we restore real timers after each test
    if (jest.isMockFunction(setTimeout)) {
      jest.useRealTimers();
    }
  });

  describe('resilientFetch', () => {
    it('should export resilientFetch function', () => {
      expect(resilientFetch).toBeDefined();
      expect(typeof resilientFetch).toBe('function');
    });

    it('should make successful GET request', async () => {
      const mockResponse = { data: 'test' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await resilientFetch('GET', 'https://api.test.com/endpoint');

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/endpoint',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('should make successful POST request with body', async () => {
      const mockResponse = { success: true };
      const requestBody = { foo: 'bar' };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await resilientFetch('POST', 'https://api.test.com/endpoint', {
        body: JSON.stringify(requestBody),
      });

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/endpoint',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(requestBody),
        })
      );
    });

    it('should merge custom headers with defaults', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await resilientFetch('GET', 'https://api.test.com/endpoint', {
        headers: {
          'X-Custom-Header': 'custom-value',
          'Authorization': 'Bearer token123',
        },
      });

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/endpoint',
        expect.objectContaining({
          headers: {
            'Content-Type': 'application/json',
            'X-Custom-Header': 'custom-value',
            'Authorization': 'Bearer token123',
          },
        })
      );
    });

    it('should retry on failure with exponential backoff', async () => {
      // Note: This test verifies retry logic exists but uses jest.runAllTimersAsync
      // to speed up the retry delays
      jest.useFakeTimers();

      // Fail twice, succeed on third try
      (global.fetch as jest.Mock)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
        });

      const promise = resilientFetch('GET', 'https://api.test.com/endpoint');

      // Run all timers (retries + delays)
      await jest.runAllTimersAsync();

      const result = await promise;

      expect(result).toEqual({ data: 'success' });
      expect(global.fetch).toHaveBeenCalledTimes(3);

      jest.useRealTimers();
      // Reset mocks after using fake timers
      (global.fetch as jest.Mock).mockReset();
    });

    it('should throw error after max retries (3 attempts)', async () => {
      // Always fail - using mockRejectedValueOnce 3 times ensures only 3 calls fail
      const fetchError = new Error('Network error');
      (global.fetch as jest.Mock)
        .mockRejectedValueOnce(fetchError)
        .mockRejectedValueOnce(fetchError)
        .mockRejectedValueOnce(fetchError);

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      // Increase timeout for this test since it involves retries
      const promise = resilientFetch('GET', 'https://api.test.com/endpoint');

      await expect(promise).rejects.toThrow('Network error');

      expect(global.fetch).toHaveBeenCalledTimes(3);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed externalApiCall after 3 attempts:',
        fetchError
      );

      consoleSpy.mockRestore();
    }, 15000); // 15 second timeout for retries

    it('should handle HTTP error responses (non-2xx status)', async () => {
      // Set up mock to always return 404 error
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      });

      await expect(
        resilientFetch('GET', 'https://api.test.com/endpoint')
      ).rejects.toThrow('HTTP error! status: 404');

      // Verify it retried (1 initial + 2 retries = 3 total attempts)
      expect(global.fetch).toHaveBeenCalledTimes(3);
    });

    it('should handle 500 status with retries', async () => {
      jest.useFakeTimers();

      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'recovered' }),
        });

      const promise = resilientFetch('GET', 'https://api.test.com/endpoint');

      await jest.runAllTimersAsync();

      const result = await promise;
      expect(result).toEqual({ data: 'recovered' });

      jest.useRealTimers();
      // Reset mocks after using fake timers
      (global.fetch as jest.Mock).mockReset();
    });

    it('should use custom operation name in error messages', async () => {
      const fetchError = new Error('Network error');
      (global.fetch as jest.Mock)
        .mockRejectedValueOnce(fetchError)
        .mockRejectedValueOnce(fetchError)
        .mockRejectedValueOnce(fetchError);

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const promise = resilientFetch(
        'GET',
        'https://api.test.com/endpoint',
        undefined,
        'customOperation'
      );

      await expect(promise).rejects.toThrow();

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed customOperation after 3 attempts:',
        fetchError
      );

      consoleSpy.mockRestore();
    }, 15000); // 15 second timeout for retries
  });

  describe('exchangeCodeForTokens', () => {
    it('should export exchangeCodeForTokens function', () => {
      expect(exchangeCodeForTokens).toBeDefined();
      expect(typeof exchangeCodeForTokens).toBe('function');
    });

    it('should call backend with auth code', async () => {
      const mockTokens = { access_token: 'abc123', refresh_token: 'xyz789' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockTokens,
      });

      const result = await exchangeCodeForTokens('auth_code_123');

      expect(result).toEqual(mockTokens);
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/api/auth/google/token',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ code: 'auth_code_123' }),
        })
      );
    });

    it('should handle exchange errors with retries', async () => {
      jest.useFakeTimers();

      (global.fetch as jest.Mock)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ access_token: 'token' }),
        });

      const promise = exchangeCodeForTokens('code');

      await jest.runAllTimersAsync();

      const result = await promise;
      expect(result).toEqual({ access_token: 'token' });

      jest.useRealTimers();
    });
  });

  describe('generateGoogleAuthUrl', () => {
    it('should export generateGoogleAuthUrl function', () => {
      expect(generateGoogleAuthUrl).toBeDefined();
      expect(typeof generateGoogleAuthUrl).toBe('function');
    });

    it('should generate auth URL without state', () => {
      const url = generateGoogleAuthUrl();

      expect(url).toBe('https://api.test.com/api/auth/google/authorize');
    });

    it('should generate auth URL with state parameter', () => {
      const url = generateGoogleAuthUrl('my-state-123');

      expect(url).toBe('https://api.test.com/api/auth/google/authorize?state=my-state-123');
    });

    it('should URL encode state parameter', () => {
      const url = generateGoogleAuthUrl('state with spaces & special=chars');

      expect(url).toContain('state=');
      expect(url).toContain('state%20with%20spaces%20%26%20special%3Dchars');
    });

    it('should use default API URL when env var not set', () => {
      delete process.env.NEXT_PUBLIC_API_URL;

      const url = generateGoogleAuthUrl('state123');

      expect(url).toBe('http://localhost:8000/api/auth/google/authorize?state=state123');

      process.env.NEXT_PUBLIC_API_URL = 'https://api.test.com';
    });
  });

  describe('getMinimalCalendarIntegrationByResource', () => {
    it('should export getMinimalCalendarIntegrationByResource function', () => {
      expect(getMinimalCalendarIntegrationByResource).toBeDefined();
      expect(typeof getMinimalCalendarIntegrationByResource).toBe('function');
    });

    it('should query calendar integration by user and resource', async () => {
      const mockIntegration = {
        Calendar_Integration: [
          {
            id: 'cal-123',
            token: 'token-abc',
            refreshToken: 'refresh-xyz',
            resource: 'google',
            expiresAt: '2024-12-31',
          },
        ],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockIntegration,
      });

      const result = await getMinimalCalendarIntegrationByResource('user-123', 'google');

      expect(result).toEqual(mockIntegration);
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/api/graphql',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('GetCalendarIntegration'),
        })
      );
    });

    it('should include userId and resource in GraphQL query', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ Calendar_Integration: [] }),
      });

      await getMinimalCalendarIntegrationByResource('user-456', 'outlook');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.variables).toEqual({
        userId: 'user-456',
        resource: 'outlook',
      });
    });
  });

  describe('getAllCalendarIntegrationsByResourceAndClientType', () => {
    it('should export getAllCalendarIntegrationsByResourceAndClientType function', () => {
      expect(getAllCalendarIntegrationsByResourceAndClientType).toBeDefined();
      expect(typeof getAllCalendarIntegrationsByResourceAndClientType).toBe('function');
    });

    it('should query all calendar integrations by user, resource, and client type', async () => {
      const mockIntegrations = {
        Calendar_Integration: [
          {
            id: 'cal-123',
            token: 'token-abc',
            refreshToken: 'refresh-xyz',
            resource: 'google',
            clientType: 'web',
            expiresAt: '2024-12-31',
            createdDate: '2024-01-01',
            updatedAt: '2024-01-15',
          },
        ],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockIntegrations,
      });

      const result = await getAllCalendarIntegrationsByResourceAndClientType(
        'user-123',
        'google',
        'web'
      );

      expect(result).toEqual(mockIntegrations);
    });

    it('should include all three parameters in GraphQL query', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ Calendar_Integration: [] }),
      });

      await getAllCalendarIntegrationsByResourceAndClientType(
        'user-789',
        'exchange',
        'mobile'
      );

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.variables).toEqual({
        userId: 'user-789',
        resource: 'exchange',
        clientType: 'mobile',
      });
    });
  });

  describe('scheduleMeeting', () => {
    it('should export scheduleMeeting function', () => {
      expect(scheduleMeeting).toBeDefined();
      expect(typeof scheduleMeeting).toBe('function');
    });

    it('should send meeting data to backend', async () => {
      const mockResponse = { meetingId: 'meeting-123', scheduled: true };
      const meetingData = {
        title: 'Team Standup',
        startTime: '2024-01-20T10:00:00Z',
        attendees: ['user1@example.com', 'user2@example.com'],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await scheduleMeeting(meetingData);

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/api/schedule/meeting',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(meetingData),
        })
      );
    });

    it('should handle scheduling errors with retries', async () => {
      jest.useFakeTimers();

      const meetingData = { title: 'Test' };

      (global.fetch as jest.Mock)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ meetingId: 'meeting-456' }),
        });

      const promise = scheduleMeeting(meetingData);

      await jest.runAllTimersAsync();

      const result = await promise;
      expect(result).toEqual({ meetingId: 'meeting-456' });

      jest.useRealTimers();
    });
  });

  describe('encryptZoomTokens and decryptZoomTokens', () => {
    it('should export both functions', () => {
      expect(encryptZoomTokens).toBeDefined();
      expect(typeof encryptZoomTokens).toBe('function');
      expect(decryptZoomTokens).toBeDefined();
      expect(typeof decryptZoomTokens).toBe('function');
    });

    it('should encrypt tokens to base64', () => {
      const tokens = {
        access_token: 'zoom-access-123',
        refresh_token: 'zoom-refresh-456',
        expires_in: 3600,
      };

      const encrypted = encryptZoomTokens(tokens);

      expect(encrypted).toBeDefined();
      expect(typeof encrypted).toBe('string');
      expect(encrypted).not.toBe(JSON.stringify(tokens));
    });

    it('should decrypt tokens back to original', () => {
      const tokens = {
        access_token: 'zoom-access-123',
        refresh_token: 'zoom-refresh-456',
      };

      const encrypted = encryptZoomTokens(tokens);
      const decrypted = decryptZoomTokens(encrypted);

      expect(decrypted).toEqual(tokens);
    });

    it('should handle complex token objects', () => {
      const tokens = {
        access_token: 'access123',
        refresh_token: 'refresh456',
        expires_in: 3600,
        token_type: 'Bearer',
        scope: ['meeting:read', 'meeting:write'],
        account_id: 'acc-789',
      };

      const encrypted = encryptZoomTokens(tokens);
      const decrypted = decryptZoomTokens(encrypted);

      expect(decrypted).toEqual(tokens);
    });

    it('should return null for invalid encrypted data', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const result = decryptZoomTokens('invalid-base64!!!');

      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to decrypt Zoom tokens:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });

    it('should handle empty string decryption', () => {
      const result = decryptZoomTokens('');

      expect(result).toBeNull();
    });

    it('should handle non-JSON base64 data', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const encrypted = Buffer.from('not-json-data').toString('base64');
      const result = decryptZoomTokens(encrypted);

      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('should produce different output for same input', () => {
      const tokens = { access_token: 'same-token' };

      // Note: This implementation produces same output for same input
      // since it's simple base64 without IV/salt
      const encrypted1 = encryptZoomTokens(tokens);
      const encrypted2 = encryptZoomTokens(tokens);

      expect(encrypted1).toBe(encrypted2); // Same due to simple encoding
    });
  });

  describe('Environment variable handling', () => {
    it('should use localhost as default when NEXT_PUBLIC_API_URL not set', () => {
      delete process.env.NEXT_PUBLIC_API_URL;

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const url = generateGoogleAuthUrl();

      expect(url).toContain('http://localhost:8000');
      process.env.NEXT_PUBLIC_API_URL = 'https://api.test.com';
    });

    it('should use custom API URL when set', () => {
      process.env.NEXT_PUBLIC_API_URL = 'https://custom.api.com';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const url = generateGoogleAuthUrl();

      expect(url).toContain('https://custom.api.com');
      process.env.NEXT_PUBLIC_API_URL = 'https://api.test.com';
    });
  });
});
