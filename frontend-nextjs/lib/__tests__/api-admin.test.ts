/**
 * Admin API Client Tests
 *
 * Test suite for admin-specific API endpoints (JIT verification, business facts)
 */

// Mock localStorage FIRST (before any imports). Plain assignment
// (global.localStorage = ...) silently fails — jsdom exposes localStorage as
// a getter-only accessor — so defineProperty is required.
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: mockLocalStorage,
});

// Mock axios with proper interceptors
const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPut = jest.fn();
const mockDelete = jest.fn();

// Captured interceptor handlers: the axios mock records the handlers passed
// to interceptors.request.use / interceptors.response.use so tests can invoke
// them directly (request auth-token injection, error enhancement).
let mockRequestInterceptor: any;
let mockRequestErrorInterceptor: any;
let mockResponseInterceptor: any;
let mockResponseErrorInterceptor: any;

const mockAxiosInstance = {
  get: mockGet,
  post: mockPost,
  put: mockPut,
  delete: mockDelete,
  interceptors: {
    request: {
      use: jest.fn((handler: any, errorHandler?: any) => {
        mockRequestInterceptor = handler;
        mockRequestErrorInterceptor = errorHandler;
      })
    },
    response: {
      use: jest.fn((handler: any, errorHandler?: any) => {
        mockResponseInterceptor = handler;
        mockResponseErrorInterceptor = errorHandler;
      })
    }
  }
};

jest.mock('axios', () => ({
  create: jest.fn(() => mockAxiosInstance),
  default: jest.fn(() => mockAxiosInstance)
}));

// Import after mocking
import {
  jitVerificationAPI,
  businessFactsAPI,
  AdminPoller,
  getAuthToken,
  setAuthToken,
  clearAuthToken,
  isAuthenticated
} from '../api-admin';

describe('api-admin', () => {
  beforeEach(() => {
    // Clear only axios method mocks, not localStorage
    mockGet.mockClear();
    mockPost.mockClear();
    mockPut.mockClear();
    mockDelete.mockClear();
  });

  describe('jitVerificationAPI', () => {
    it('should export jitVerificationAPI object', () => {
      expect(jitVerificationAPI).toBeDefined();
      expect(typeof jitVerificationAPI).toBe('object');
    });

    it('should have getCacheStats method', () => {
      expect(jitVerificationAPI.getCacheStats).toBeDefined();
      expect(typeof jitVerificationAPI.getCacheStats).toBe('function');
    });

    it('should call getCacheStats endpoint', () => {
      mockGet.mockResolvedValue({ data: { cache_hits: 100 } });

      jitVerificationAPI.getCacheStats();

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/jit/cache/stats');
    });

    it('should have clearCache method', () => {
      expect(jitVerificationAPI.clearCache).toBeDefined();
      expect(typeof jitVerificationAPI.clearCache).toBe('function');
    });

    it('should call clearCache endpoint', () => {
      mockPost.mockResolvedValue({ data: { success: true } });

      jitVerificationAPI.clearCache();

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/jit/cache/clear');
    });

    it('should have verifyCitations method', () => {
      expect(jitVerificationAPI.verifyCitations).toBeDefined();
      expect(typeof jitVerificationAPI.verifyCitations).toBe('function');
    });

    it('should call verifyCitations endpoint with request body', () => {
      mockPost.mockResolvedValue({ data: { verified: true } });

      const request = { citations: ['citation1', 'citation2'] };
      jitVerificationAPI.verifyCitations(request);

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/jit/verify-citations', request);
    });

    it('should have getWorkerMetrics method', () => {
      expect(jitVerificationAPI.getWorkerMetrics).toBeDefined();
      expect(typeof jitVerificationAPI.getWorkerMetrics).toBe('function');
    });

    it('should call getWorkerMetrics endpoint', () => {
      mockGet.mockResolvedValue({ data: { active: true } });

      jitVerificationAPI.getWorkerMetrics();

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/jit/worker/metrics');
    });

    it('should have startWorker method', () => {
      expect(jitVerificationAPI.startWorker).toBeDefined();
      expect(typeof jitVerificationAPI.startWorker).toBe('function');
    });

    it('should call startWorker endpoint', () => {
      mockPost.mockResolvedValue({ data: { started: true } });

      jitVerificationAPI.startWorker();

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/jit/worker/start');
    });

    it('should have stopWorker method', () => {
      expect(jitVerificationAPI.stopWorker).toBeDefined();
      expect(typeof jitVerificationAPI.stopWorker).toBe('function');
    });

    it('should call stopWorker endpoint', () => {
      mockPost.mockResolvedValue({ data: { stopped: true } });

      jitVerificationAPI.stopWorker();

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/jit/worker/stop');
    });

    it('should have verifyFactCitations method', () => {
      expect(jitVerificationAPI.verifyFactCitations).toBeDefined();
      expect(typeof jitVerificationAPI.verifyFactCitations).toBe('function');
    });

    it('should call verifyFactCitations endpoint with fact ID', () => {
      mockPost.mockResolvedValue({ data: { verified: true } });

      jitVerificationAPI.verifyFactCitations('fact-123');

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/jit/worker/verify-fact/fact-123');
    });

    it('should have getTopCitations method', () => {
      expect(jitVerificationAPI.getTopCitations).toBeDefined();
      expect(typeof jitVerificationAPI.getTopCitations).toBe('function');
    });

    it('should call getTopCitations endpoint with default limit', () => {
      mockGet.mockResolvedValue({ data: { citations: [] } });

      jitVerificationAPI.getTopCitations();

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/jit/worker/top-citations?limit=20');
    });

    it('should call getTopCitations endpoint with custom limit', () => {
      mockGet.mockResolvedValue({ data: { citations: [] } });

      jitVerificationAPI.getTopCitations(50);

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/jit/worker/top-citations?limit=50');
    });

    it('should have getHealth method', () => {
      expect(jitVerificationAPI.getHealth).toBeDefined();
      expect(typeof jitVerificationAPI.getHealth).toBe('function');
    });

    it('should call getHealth endpoint', () => {
      mockGet.mockResolvedValue({ data: { healthy: true } });

      jitVerificationAPI.getHealth();

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/jit/health');
    });

    it('should have warmCache method', () => {
      expect(jitVerificationAPI.warmCache).toBeDefined();
      expect(typeof jitVerificationAPI.warmCache).toBe('function');
    });

    it('should call warmCache endpoint with default limit', () => {
      mockPost.mockResolvedValue({ data: { warmed: true } });

      jitVerificationAPI.warmCache();

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/jit/cache/warm?limit=100');
    });

    it('should call warmCache endpoint with custom limit', () => {
      mockPost.mockResolvedValue({ data: { warmed: true } });

      jitVerificationAPI.warmCache(200);

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/jit/cache/warm?limit=200');
    });

    it('should have getConfig method', () => {
      expect(jitVerificationAPI.getConfig).toBeDefined();
      expect(typeof jitVerificationAPI.getConfig).toBe('function');
    });

    it('should call getConfig endpoint', () => {
      mockGet.mockResolvedValue({ data: { config: {} } });

      jitVerificationAPI.getConfig();

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/jit/config');
    });
  });

  describe('businessFactsAPI', () => {
    it('should export businessFactsAPI object', () => {
      expect(businessFactsAPI).toBeDefined();
      expect(typeof businessFactsAPI).toBe('object');
    });

    it('should have listFacts method', () => {
      expect(businessFactsAPI.listFacts).toBeDefined();
      expect(typeof businessFactsAPI.listFacts).toBe('function');
    });

    it('should call listFacts endpoint with no filters', () => {
      mockGet.mockResolvedValue({ data: { facts: [] } });

      businessFactsAPI.listFacts();

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/facts');
    });

    it('should call listFacts endpoint with status filter', () => {
      mockGet.mockResolvedValue({ data: { facts: [] } });

      businessFactsAPI.listFacts({ status: 'verified' });

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/facts?status=verified');
    });

    it('should call listFacts endpoint with domain filter', () => {
      mockGet.mockResolvedValue({ data: { facts: [] } });

      businessFactsAPI.listFacts({ domain: 'finance' });

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/facts?domain=finance');
    });

    it('should call listFacts endpoint with limit filter', () => {
      mockGet.mockResolvedValue({ data: { facts: [] } });

      businessFactsAPI.listFacts({ limit: 50 });

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/facts?limit=50');
    });

    it('should call listFacts endpoint with multiple filters', () => {
      mockGet.mockResolvedValue({ data: { facts: [] } });

      businessFactsAPI.listFacts({ status: 'verified', domain: 'finance', limit: 100 });

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/facts?status=verified&domain=finance&limit=100');
    });

    it('should not include "all" status in query params', () => {
      mockGet.mockResolvedValue({ data: { facts: [] } });

      businessFactsAPI.listFacts({ status: 'all' });

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/facts');
    });

    it('should have getFact method', () => {
      expect(businessFactsAPI.getFact).toBeDefined();
      expect(typeof businessFactsAPI.getFact).toBe('function');
    });

    it('should call getFact endpoint with fact ID', () => {
      mockGet.mockResolvedValue({ data: { id: 'fact-123' } });

      businessFactsAPI.getFact('fact-123');

      expect(mockGet).toHaveBeenCalledWith('/api/admin/governance/facts/fact-123');
    });

    it('should have createFact method', () => {
      expect(businessFactsAPI.createFact).toBeDefined();
      expect(typeof businessFactsAPI.createFact).toBe('function');
    });

    it('should call createFact endpoint with request body', () => {
      mockPost.mockResolvedValue({ data: { id: 'fact-123' } });

      const request = { statement: 'Test fact', citations: [] } as any;
      businessFactsAPI.createFact(request);

      expect(mockPost).toHaveBeenCalledWith('/api/admin/governance/facts', request);
    });

    it('should have updateFact method', () => {
      expect(businessFactsAPI.updateFact).toBeDefined();
      expect(typeof businessFactsAPI.updateFact).toBe('function');
    });

    it('should call updateFact endpoint with fact ID and request body', () => {
      mockPut.mockResolvedValue({ data: { id: 'fact-123' } });

      const request = { statement: 'Updated fact' } as any;
      businessFactsAPI.updateFact('fact-123', request);

      expect(mockPut).toHaveBeenCalledWith('/api/admin/governance/facts/fact-123', request);
    });

    it('should have deleteFact method', () => {
      expect(businessFactsAPI.deleteFact).toBeDefined();
      expect(typeof businessFactsAPI.deleteFact).toBe('function');
    });

    it('should call deleteFact endpoint with fact ID', () => {
      mockDelete.mockResolvedValue({ data: { deleted: true } });

      businessFactsAPI.deleteFact('fact-123');

      expect(mockDelete).toHaveBeenCalledWith('/api/admin/governance/facts/fact-123');
    });
  });

  describe('AdminPoller', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should instantiate AdminPoller', () => {
      const poller = new AdminPoller();
      expect(poller).toBeDefined();
      expect(poller.isRunning()).toBe(false);
    });

    it('should start polling', () => {
      const poller = new AdminPoller();
      const mockFetch = jest.fn().mockResolvedValue({ data: { status: 'healthy' } });
      const mockOnUpdate = jest.fn();

      poller.start(mockFetch, mockOnUpdate);

      expect(poller.isRunning()).toBe(true);
    });

    it('should stop polling', () => {
      const poller = new AdminPoller();
      const mockFetch = jest.fn().mockResolvedValue({ data: {} });
      const mockOnUpdate = jest.fn();

      poller.start(mockFetch, mockOnUpdate);
      expect(poller.isRunning()).toBe(true);

      poller.stop();
      expect(poller.isRunning()).toBe(false);
    });

    it('should unwrap { data } payloads and call onUpdate with the inner data', async () => {
      const poller = new AdminPoller();
      const mockFetch = jest.fn().mockResolvedValue({ data: { status: 'healthy' } });
      const mockOnUpdate = jest.fn();

      poller.start(mockFetch, mockOnUpdate);
      await Promise.resolve();

      expect(mockOnUpdate).toHaveBeenCalledWith({ status: 'healthy' });
      poller.stop();
    });

    it('should pass through plain payloads without unwrapping', async () => {
      const poller = new AdminPoller();
      const mockFetch = jest.fn().mockResolvedValue({ status: 'healthy' });
      const mockOnUpdate = jest.fn();

      poller.start(mockFetch, mockOnUpdate);
      await Promise.resolve();

      expect(mockOnUpdate).toHaveBeenCalledWith({ status: 'healthy' });
      poller.stop();
    });

    it('should log and continue when the initial fetch fails', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const poller = new AdminPoller();
      const mockFetch = jest.fn().mockRejectedValue(new Error('initial failed'));
      const mockOnUpdate = jest.fn();

      poller.start(mockFetch, mockOnUpdate);
      // Two microtask flushes: the rejection propagates through the .then
      // before reaching the .catch logger.
      await Promise.resolve();
      await Promise.resolve();

      expect(consoleSpy).toHaveBeenCalledWith('[AdminPoller] Initial fetch error:', expect.any(Error));
      expect(poller.isRunning()).toBe(true);
      poller.stop();
      consoleSpy.mockRestore();
    });

    it('should log and keep polling when a poll cycle fails', async () => {
      jest.useFakeTimers();
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const poller = new AdminPoller();
      const mockFetch = jest.fn()
        .mockResolvedValueOnce({ data: { ok: true } }) // initial fetch succeeds
        .mockRejectedValueOnce(new Error('poll failed')); // poll cycle fails
      const mockOnUpdate = jest.fn();

      poller.start(mockFetch, mockOnUpdate);
      await Promise.resolve();

      // Advance past the 10s default interval so the failing poll runs.
      await Promise.resolve();
      jest.advanceTimersByTime(10000);
      await Promise.resolve();

      expect(consoleSpy).toHaveBeenCalledWith('[AdminPoller] Polling error:', expect.any(Error));
      // The interval survives the error — polling continues.
      expect(poller.isRunning()).toBe(true);
      poller.stop();
      consoleSpy.mockRestore();
      jest.useRealTimers();
    });

    it('should restart polling when start is called twice', async () => {
      jest.useFakeTimers();
      const poller = new AdminPoller();
      const mockFetch = jest.fn().mockResolvedValue({ data: { n: 1 } });
      const mockOnUpdate = jest.fn();

      poller.start(mockFetch, mockOnUpdate);
      poller.start(mockFetch, mockOnUpdate);
      await Promise.resolve();

      // Exactly ONE interval: the second start cleared the first. Advancing
      // 20s (two 10s ticks) yields 2 initial fetches + 2 ticks = 4 calls.
      // With a leaked first interval it would be 6.
      jest.advanceTimersByTime(20000);
      await Promise.resolve();
      expect(mockFetch).toHaveBeenCalledTimes(4);
      poller.stop();
      jest.useRealTimers();
    });
  });

  describe('request interceptor', () => {
    test('injects Bearer token and X-Request-ID when a token exists', () => {
      (mockLocalStorage.getItem as jest.Mock).mockReturnValue('my-token');

      const config: any = { headers: {} };
      const result = mockRequestInterceptor(config);

      expect(result.headers.Authorization).toBe('Bearer my-token');
      expect(result.headers['X-Request-ID']).toMatch(/^req_\d+_/);
      expect(result).toBe(config);
    });

    test('uses token from the token key when auth_token is absent', () => {
      (mockLocalStorage.getItem as jest.Mock).mockImplementation((key: string) =>
        key === 'auth_token' ? null : 'fallback-token'
      );

      const config: any = { headers: {} };
      const result = mockRequestInterceptor(config);

      expect(result.headers.Authorization).toBe('Bearer fallback-token');
    });

    test('omits Authorization and still adds X-Request-ID when no token exists', () => {
      (mockLocalStorage.getItem as jest.Mock).mockReturnValue(null);

      const config: any = { headers: {} };
      const result = mockRequestInterceptor(config);

      expect(result.headers.Authorization).toBeUndefined();
      expect(result.headers['X-Request-ID']).toBeDefined();
    });

    test('handles config without headers', () => {
      (mockLocalStorage.getItem as jest.Mock).mockReturnValue('t');

      const config: any = {};
      const result = mockRequestInterceptor(config);

      // The interceptor guards on config.headers — no headers, no injection,
      // and no crash.
      expect(result.headers).toBeUndefined();
      expect(result).toBe(config);
    });

    test('forwards request errors to the rejection path', async () => {
      const error = new Error('request setup failed');
      await expect(mockRequestErrorInterceptor(error)).rejects.toBe(error);
    });
  });

  describe('response interceptor', () => {
    test('passes successful responses through unchanged', () => {
      const response = { data: { ok: true }, status: 200 };
      expect(mockResponseInterceptor(response)).toBe(response);
    });

    test('enhances 401 errors with auth severity and re-login action', async () => {
      const error: any = {
        code: '401',
        message: 'Unauthorized',
        response: { status: 401, data: { message: 'Token expired' } },
        config: { url: '/api/admin/governance/facts' },
      };

      await expect(mockResponseErrorInterceptor(error)).rejects.toMatchObject({
        userMessage: 'Token expired',
        severity: 'auth',
        action: 'Please log in again',
      });
    });

    test('enhances non-401 errors with error severity and no action', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const error: any = {
        code: 'ERR_BAD_RESPONSE',
        message: 'Server error',
        response: { status: 500, data: {} },
        config: { url: '/api/admin/governance/facts' },
      };

      await expect(mockResponseErrorInterceptor(error)).rejects.toMatchObject({
        userMessage: 'Server error',
        severity: 'error',
        action: undefined,
      });
      consoleSpy.mockRestore();
    });

    test('falls back to error.message when the response body has no message', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const error: any = {
        code: 'ERR_NETWORK',
        message: 'Network Error',
        config: { url: '/api/admin/governance/jit/cache/stats' },
      };

      await expect(mockResponseErrorInterceptor(error)).rejects.toMatchObject({
        userMessage: 'Network Error',
        severity: 'error',
      });
      consoleSpy.mockRestore();
    });
  });

  describe('auth token helpers', () => {
    test('getAuthToken reads auth_token from localStorage', () => {
      (mockLocalStorage.getItem as jest.Mock).mockReturnValue('stored-token');
      expect(getAuthToken()).toBe('stored-token');
      expect(mockLocalStorage.getItem).toHaveBeenCalledWith('auth_token');
    });

    test('getAuthToken returns null when nothing is stored', () => {
      (mockLocalStorage.getItem as jest.Mock).mockReturnValue(null);
      expect(getAuthToken()).toBeNull();
    });

    test('setAuthToken writes auth_token to localStorage', () => {
      setAuthToken('new-token');
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('auth_token', 'new-token');
    });

    test('clearAuthToken removes auth_token from localStorage', () => {
      clearAuthToken();
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('auth_token');
    });

    test('isAuthenticated is true when a token exists and false otherwise', () => {
      (mockLocalStorage.getItem as jest.Mock).mockReturnValue('t');
      expect(isAuthenticated()).toBe(true);

      (mockLocalStorage.getItem as jest.Mock).mockReturnValue(null);
      expect(isAuthenticated()).toBe(false);
    });
  });
});
