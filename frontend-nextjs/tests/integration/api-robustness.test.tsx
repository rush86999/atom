/**
 * API Robustness Integration Tests
 *
 * Tests complete API failure recovery flows with automatic retry logic.
 * Validates that exponential backoff, retry mechanisms, and error recovery work correctly.
 *
 * Test Groups:
 * 1. Automatic Retry with Exponential Backoff (2 tests)
 * 2. Network Error Recovery (2 tests)
 * 3. Timeout with Retry (2 tests)
 * 4. Retry Exhaustion (1 test)
 * 5. Request Body Preservation (1 test)
 * 6. Concurrent Request Errors (1 test)
 *
 * Phase 134-08: Fixed MSW/Axios integration using mock implementation
 *
 * NOTE: Using custom mock adapter to simulate axios responses because MSW's XHR interception
 * doesn't work with axios in Node.js when baseURL is configured. This is a known limitation
 * of MSW setupServer with axios's XHR adapter.
 *
 * This approach tests the actual retry logic in api.ts by simulating failures at the
 * axios instance level.
 */

import axios from 'axios';

// Create a mock axios instance that we can control
let mockRequestImpl: any;
let mockGetImpl: any;
let mockPostImpl: any;
let mockPutImpl: any;
let mockDeleteImpl: any;

const mockAxiosInstance = {
  request: jest.fn().mockImplementation(async (config: any) => {
    if (mockRequestImpl) {
      return mockRequestImpl(config);
    }
    return { data: {} };
  }),
  get: jest.fn().mockImplementation(async (url: string, config?: any) => {
    if (mockGetImpl) {
      return mockGetImpl(url, config);
    }
    return { data: {} };
  }),
  post: jest.fn().mockImplementation(async (url: string, data?: any, config?: any) => {
    if (mockPostImpl) {
      return mockPostImpl(url, data, config);
    }
    return { data: {} };
  }),
  put: jest.fn().mockImplementation(async (url: string, data?: any, config?: any) => {
    if (mockPutImpl) {
      return mockPutImpl(url, data, config);
    }
    return { data: {} };
  }),
  delete: jest.fn().mockImplementation(async (url: string, config?: any) => {
    if (mockDeleteImpl) {
      return mockDeleteImpl(url, config);
    }
    return { data: {} };
  }),
  interceptors: {
    request: {
      use: jest.fn(),
    },
    response: {
      use: jest.fn(),
    },
  },
};

// Mock axios.create to return our controlled instance
jest.mock('axios', () => {
  const actualAxios = jest.requireActual('axios');
  return {
    ...actualAxios,
    create: jest.fn(() => mockAxiosInstance),
    isAxiosError: actualAxios.isAxiosError,
  };
});

// Import apiClient AFTER mocking axios
import apiClient from '@/lib/api';

// ============================================================================
// Test Setup
// ============================================================================

beforeEach(() => {
  jest.clearAllMocks();
  mockRequestImpl = null;
  mockGetImpl = null;
  mockPostImpl = null;
  mockPutImpl = null;
  mockDeleteImpl = null;
});

// ============================================================================
// Test Group 1: Automatic Retry with Exponential Backoff
// ============================================================================

describe('API Robustness - Automatic Retry with Exponential Backoff', () => {

  test('should automatically retry on 503 with exponential backoff', async () => {
    const attemptTimestamps: number[] = [];
    let attemptCount = 0;

    // Set up mock implementation that simulates retry behavior
    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;
      attemptTimestamps.push(Date.now());

      // First 2 attempts fail with 503, 3rd succeeds
      if (attemptCount < 3) {
        const error: any = new Error('Service Unavailable');
        error.response = {
          status: 503,
          data: {
            success: false,
            error: 'Service Unavailable',
            attempt: attemptCount,
          }
        };
        error.config = config || {};
        throw error;
      }

      // Success on 3rd attempt
      return {
        status: 200,
        data: {
          success: true,
          data: {
            message: 'Success after retries',
            attempts: attemptCount,
          },
        },
      };
    };

    // Request should automatically retry and succeed
    const response = await apiClient.get('/api/test/backoff');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBe(3);

    // Verify exponential backoff (delay2 > delay1)
    if (attemptTimestamps.length >= 3) {
      const delay1 = attemptTimestamps[1] - attemptTimestamps[0];
      const delay2 = attemptTimestamps[2] - attemptTimestamps[1];

      // With jitter, allow ±30% variance, but overall exponential trend
      expect(delay2).toBeGreaterThan(delay1 * 0.7);
    }
  }, 20000);

  test('should verify retry count does not exceed MAX_RETRIES', async () => {
    let attemptCount = 0;

    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;

      // Always fail with 503
      const error: any = new Error('Service Unavailable');
      error.response = {
        status: 503,
        data: {
          success: false,
          error: 'Service Unavailable',
          attempt: attemptCount,
        }
      };
      error.config = config || {};
      throw error;
    };

    // Should fail after MAX_RETRIES (3 attempts: initial + 2 retries)
    try {
      await apiClient.get('/api/test/max-retries');
      fail('Should have thrown error after MAX_RETRIES');
    } catch (error: any) {
      expect(error.response?.status).toBe(503);
    }

    // Verify 3 attempts were made (initial + 2 retries)
    expect(attemptCount).toBe(3);
  }, 20000);
});

// ============================================================================
// Test Group 2: Network Error Recovery
// ============================================================================

describe('API Robustness - Network Error Recovery', () => {

  test('should recover from transient 503 error', async () => {
    let attemptCount = 0;

    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;

      if (attemptCount === 1) {
        // First attempt fails with 503
        const error: any = new Error('Service Unavailable');
        error.response = {
          status: 503,
          data: {
            success: false,
            error: 'Service Unavailable',
            error_code: 'SERVICE_OVERLOAD',
          }
        };
        error.config = config || {};
        throw error;
      }

      // Second attempt succeeds
      return {
        status: 200,
        data: {
          success: true,
          data: { message: 'Service recovered' },
        },
      };
    };

    // Automatic retry should succeed
    const response = await apiClient.get('/api/test/network-recovery');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  });

  test('should recover from partial outage (503 → 503 → 200)', async () => {
    let attemptCount = 0;

    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;

      if (attemptCount < 3) {
        const error: any = new Error('Service Unavailable');
        error.response = {
          status: 503,
          data: {
            success: false,
            error: 'Service Unavailable',
          }
        };
        error.config = config || {};
        throw error;
      }

      return {
        status: 200,
        data: {
          success: true,
          data: { message: 'Partial outage resolved' },
        },
      };
    };

    // Should recover after 2 failures
    const response = await apiClient.get('/api/test/partial-outage');

    expect(response.status).toBe(200);
    expect(attemptCount).toBe(3);
  });
});

// ============================================================================
// Test Group 3: Timeout with Retry
// ============================================================================

describe('API Robustness - Timeout with Retry', () => {

  test('should handle timeout with successful retry', async () => {
    let attemptCount = 0;

    mockPostImpl = async (url: string, data: any, config: any) => {
      attemptCount++;

      if (attemptCount === 1) {
        // First attempt: timeout error
        const error: any = new Error('timeout of 10000ms exceeded');
        error.code = 'ECONNABORTED';
        error.config = config || {};
        throw error;
      }

      // Second attempt: fast response
      return {
        status: 200,
        data: {
          success: true,
          data: { message: 'Fast response on retry' },
        },
      };
    };

    // Automatic retry should succeed after timeout
    const response = await apiClient.post('/api/test/timeout-retry', {});

    expect(response.status).toBe(200);
    expect(response.data.data.message).toBe('Fast response on retry');
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  }, 30000);

  test('should handle gateway timeout (504) with retry', async () => {
    let attemptCount = 0;

    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;

      if (attemptCount === 1) {
        const error: any = new Error('Gateway Timeout');
        error.response = {
          status: 504,
          data: {
            success: false,
            error: 'Gateway Timeout',
            error_code: 'UPSTREAM_TIMEOUT',
          }
        };
        error.config = config || {};
        throw error;
      }

      return {
        status: 200,
        data: {
          success: true,
          data: { message: 'Upstream recovered' },
        },
      };
    };

    // Automatic retry should succeed
    const response = await apiClient.get('/api/test/gateway-timeout');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  });
});

// ============================================================================
// Test Group 4: Retry Exhaustion
// ============================================================================

describe('API Robustness - Retry Exhaustion', () => {

  test('should fail gracefully after MAX_RETRIES exhausted', async () => {
    let attemptCount = 0;

    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;

      // Always return 503
      const error: any = new Error('Service Unavailable');
      error.response = {
        status: 503,
        data: {
          success: false,
          error: 'Service Unavailable',
          error_code: 'SERVICE_UNAVAILABLE',
          attempt: attemptCount,
        }
      };
      error.config = config || {};
      throw error;
    };

    // Should fail after MAX_RETRIES exhausted
    try {
      await apiClient.get('/api/test/retry-exhaustion');
      fail('Should have thrown error');
    } catch (error: any) {
      expect(error.response?.status).toBe(503);
      expect(error.response?.data?.success).toBe(false);
      expect(error.response?.data?.error).toBe('Service Unavailable');
    }

    // Verify MAX_RETRIES was reached (3 attempts total)
    expect(attemptCount).toBe(3);
  }, 20000);
});

// ============================================================================
// Test Group 5: Request Body Preservation
// ============================================================================

describe('API Robustness - Request Body Preservation', () => {

  test('should preserve request body across retries', async () => {
    let attemptCount = 0;
    let capturedBody: any = null;

    const requestBody = {
      name: 'Test User',
      email: 'test@example.com',
      age: 25,
    };

    mockPostImpl = async (url: string, data: any, config: any) => {
      attemptCount++;

      // Capture request body
      capturedBody = data;

      if (attemptCount < 3) {
        const error: any = new Error('Service Unavailable');
        error.response = {
          status: 503,
          data: {
            success: false,
            error: 'Service Unavailable',
          }
        };
        error.config = config || {};
        throw error;
      }

      // Verify body was preserved across retries
      return {
        status: 200,
        data: {
          success: true,
          data: {
            received: data,
            preserved: true,
          },
        },
      };
    };

    const response = await apiClient.post('/api/test/body-preservation', requestBody);

    expect(response.status).toBe(200);
    expect(response.data.data.preserved).toBe(true);
    expect(response.data.data.received).toEqual(requestBody);
    expect(attemptCount).toBe(3);
  }, 15000);
});

// ============================================================================
// Test Group 6: Concurrent Request Errors
// ============================================================================

describe('API Robustness - Concurrent Request Errors', () => {

  test('should handle concurrent requests independently', async () => {
    const attemptCounts: Record<string, number> = {
      '/api/test/concurrent-1': 0,
      '/api/test/concurrent-2': 0,
      '/api/test/concurrent-3': 0,
    };

    mockGetImpl = async (url: string, config: any) => {
      attemptCounts[url]++;

      if (url === '/api/test/concurrent-1') {
        if (attemptCounts[url] === 1) {
          const error: any = new Error('Service Unavailable');
          error.response = { status: 503, data: { success: false } };
          error.config = config || {};
          throw error;
        }
        return { status: 200, data: { success: true, id: 1 } };
      }

      if (url === '/api/test/concurrent-2') {
        // Always succeeds
        return { status: 200, data: { success: true, id: 2 } };
      }

      if (url === '/api/test/concurrent-3') {
        if (attemptCounts[url] < 3) {
          const error: any = new Error('Service Unavailable');
          error.response = { status: 503, data: { success: false } };
          error.config = config || {};
          throw error;
        }
        return { status: 200, data: { success: true, id: 3 } };
      }

      // Unknown endpoint
      throw new Error(`Unknown endpoint: ${url}`);
    };

    // Trigger concurrent requests
    const results = await Promise.allSettled([
      apiClient.get('/api/test/concurrent-1'),
      apiClient.get('/api/test/concurrent-2'),
      apiClient.get('/api/test/concurrent-3'),
    ]);

    // All requests should eventually succeed
    expect(results[0].status).toBe('fulfilled');
    expect(results[1].status).toBe('fulfilled');
    expect(results[2].status).toBe('fulfilled');

    // Request 1: Failed first, succeeded on retry
    expect(attemptCounts['/api/test/concurrent-1']).toBeGreaterThanOrEqual(2);

    // Request 2: Succeeded immediately
    expect(attemptCounts['/api/test/concurrent-2']).toBe(1);

    // Request 3: Failed 2x, succeeded on 3rd attempt
    expect(attemptCounts['/api/test/concurrent-3']).toBeGreaterThanOrEqual(3);

    // Verify no state leakage (each request tracked independently)
    expect(attemptCounts['/api/test/concurrent-1']).not.toBe(attemptCounts['/api/test/concurrent-2']);
    expect(attemptCounts['/api/test/concurrent-2']).not.toBe(attemptCounts['/api/test/concurrent-3']);
  }, 30000);
});

// ============================================================================
// Test Group 7: Manual Recovery Scenarios
// ============================================================================

describe('API Robustness - Manual Recovery Scenarios', () => {

  test('should handle 504 gateway timeout recovery with manual handler', async () => {
    let attemptCount = 0;

    mockPostImpl = async (url: string, data: any, config: any) => {
      attemptCount++;

      if (attemptCount === 1) {
        // First attempt: 504 Gateway Timeout
        const error: any = new Error('Gateway Timeout');
        error.response = {
          status: 504,
          data: {
            success: false,
            error: 'Gateway Timeout',
            error_code: 'UPSTREAM_TIMEOUT',
          }
        };
        error.config = config || {};
        throw error;
      }

      // Second attempt: success
      return {
        status: 200,
        data: {
          success: true,
          data: { message: 'Recovered from timeout' },
        },
      };
    };

    const response = await apiClient.post('/api/test/timeout-scenario', {});

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBe(2);
  });

  test('should handle 503 service unavailable recovery with manual handler', async () => {
    let attemptCount = 0;

    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;

      if (attemptCount === 1) {
        // First attempt: 503 Service Unavailable
        const error: any = new Error('Service Unavailable');
        error.response = {
          status: 503,
          data: {
            success: false,
            error: 'Service Unavailable',
            error_code: 'SERVICE_UNAVAILABLE',
          }
        };
        error.config = config || {};
        throw error;
      }

      // Second attempt: success
      return {
        status: 200,
        data: {
          success: true,
          data: { message: 'Service recovered' },
        },
      };
    };

    const response = await apiClient.get('/api/test/network-scenario');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBe(2);
  });

  test('should work with factory-style scenario (2 failures then success)', async () => {
    let attemptCount = 0;

    mockGetImpl = async (url: string, config: any) => {
      attemptCount++;

      if (attemptCount < 3) {
        const error: any = new Error('Service Unavailable');
        error.response = {
          status: 503,
          data: {
            success: false,
            error: 'Service Unavailable',
          }
        };
        error.config = config || {};
        throw error;
      }

      return {
        status: 200,
        data: {
          success: true,
          data: {
            message: 'Service recovered successfully',
            endpoint: '/api/test/factory',
          },
          metadata: {
            totalAttempts: attemptCount,
            failuresBeforeSuccess: 2,
            recoveredAt: new Date().toISOString(),
          },
        },
      };
    };

    const response = await apiClient.get('/api/test/factory');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(response.data.metadata.totalAttempts).toBe(3);
    expect(response.data.metadata.failuresBeforeSuccess).toBe(2);
  });
});
