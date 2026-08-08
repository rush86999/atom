/**
 * API Service Tests
 *
 * Tests for the axios wrapper:
 * - Token lifecycle (set/get/clear, secure storage persistence)
 * - Request interceptor (Bearer header injection)
 * - Response interceptor (401 token clearing)
 * - Generic get/post/put/delete with success + error mapping
 * - Error fallbacks (detail -> message -> generic)
 */

import { apiService } from '../../services/api';
import {
  secureSet,
  secureGet,
  secureDelete,
} from '../../storage/secureTokenStorage';

jest.mock('../../storage/secureTokenStorage', () => ({
  secureSet: jest.fn(),
  secureGet: jest.fn(),
  secureDelete: jest.fn(),
}));

jest.mock('axios', () => {
  const axiosInstance: any = {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };
  const create = jest.fn((config) => {
    axiosInstance.defaults = { ...config };
    return axiosInstance;
  });
  return {
    __esModule: true,
    default: { create },
    create,
  };
});

const mockSecureSet = secureSet as jest.Mock;
const mockSecureGet = secureGet as jest.Mock;
const mockSecureDelete = secureDelete as jest.Mock;

const mockedAxios = jest.requireMock('axios');
const mockClient = mockedAxios.create.mock.results[0].value;

// The ApiService constructor registers these handlers at import time.
// Capture the function references NOW — jest.clearAllMocks() wipes the
// interceptor `use` call history but not these references.
const requestHandler = mockClient.interceptors.request.use.mock.calls[0][0];
const requestErrorHandler = mockClient.interceptors.request.use.mock.calls[0][1];
const responseHandler = mockClient.interceptors.response.use.mock.calls[0][0];
const responseErrorHandler = mockClient.interceptors.response.use.mock.calls[0][1];

describe('apiService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (apiService as any).token = null;
    mockSecureGet.mockResolvedValue(null);
    mockSecureSet.mockResolvedValue(undefined);
    mockSecureDelete.mockResolvedValue(undefined);
    // Default: successful responses
    mockClient.get.mockResolvedValue({ data: { ok: true } });
    mockClient.post.mockResolvedValue({ data: { ok: true } });
    mockClient.put.mockResolvedValue({ data: { ok: true } });
    mockClient.delete.mockResolvedValue({ data: { ok: true } });
  });

  // ========================================================================
  // Token Lifecycle Tests
  // ========================================================================

  describe('Token Lifecycle', () => {
    test('should persist the token in memory and secure storage', async () => {
      await apiService.setToken('token-123');

      expect(mockSecureSet).toHaveBeenCalledWith('atom_access_token', 'token-123');
      expect(await apiService.getToken()).toBe('token-123');
    });

    test('should hydrate the token from secure storage on first read', async () => {
      mockSecureGet.mockResolvedValue('stored-token');

      const token = await apiService.getToken();

      expect(mockSecureGet).toHaveBeenCalledWith('atom_access_token');
      expect(token).toBe('stored-token');
    });

    test('should not re-read secure storage once token is cached', async () => {
      await apiService.setToken('cached-token');
      mockSecureGet.mockClear();

      const token = await apiService.getToken();

      expect(token).toBe('cached-token');
      expect(mockSecureGet).not.toHaveBeenCalled();
    });

    test('should clear the token and remove it from secure storage', async () => {
      await apiService.setToken('token-123');

      await apiService.clearToken();

      expect(apiService.getToken()).resolves.toBeNull();
      // Both the current key AND the legacy key are removed — otherwise a
      // subsequent getToken() resurrects the stale token from storage.
      expect(mockSecureDelete).toHaveBeenCalledWith('atom_access_token');
      expect(mockSecureDelete).toHaveBeenCalledWith('auth_token');
    });

    test('should return null when no token is stored', async () => {
      expect(await apiService.getToken()).toBeNull();
    });
  });

  // ========================================================================
  // Request Interceptor Tests
  // ========================================================================

  describe('Request Interceptor', () => {
    test('should attach the Bearer header when a token is set', async () => {
      await apiService.setToken('abc');

      const config = await requestHandler({ headers: {} });

      expect(config.headers.Authorization).toBe('Bearer abc');
    });

    test('should leave the request untouched when no token is set', async () => {
      const config = await requestHandler({ headers: {} });

      expect(config.headers.Authorization).toBeUndefined();
    });

    test('should propagate request preparation errors', async () => {
      const error = new Error('prepare failed');
      await expect(requestErrorHandler(error)).rejects.toBe(error);
    });
  });

  // ========================================================================
  // Response Interceptor Tests
  // ========================================================================

  describe('Response Interceptor', () => {
    test('should pass successful responses through unchanged', async () => {
      const response = { data: { ok: true }, status: 200 };
      expect(await responseHandler(response)).toBe(response);
    });

    test('should clear the token on a 401 response', async () => {
      await apiService.setToken('expired');

      await expect(
        responseErrorHandler({ response: { status: 401 } })
      ).rejects.toBeTruthy();

      expect(mockSecureDelete).toHaveBeenCalled();
      expect(await apiService.getToken()).toBeNull();
    });

    test('should reject non-401 errors without clearing the token', async () => {
      await apiService.setToken('keep-me');
      mockSecureDelete.mockClear();

      const error = { response: { status: 500 } };
      await expect(responseErrorHandler(error)).rejects.toBe(error);

      expect(mockSecureDelete).not.toHaveBeenCalled();
      expect(await apiService.getToken()).toBe('keep-me');
    });
  });

  // ========================================================================
  // Generic Request Tests
  // ========================================================================

  describe('Generic Requests', () => {
    test('should GET and unwrap the response data', async () => {
      mockClient.get.mockResolvedValue({ data: { workflows: [] } });

      const result = await apiService.get('/api/workflows');

      expect(mockClient.get).toHaveBeenCalledWith('/api/workflows', undefined);
      expect(result).toEqual({ success: true, data: { workflows: [] } });
    });

    test('should POST the payload', async () => {
      mockClient.post.mockResolvedValue({ data: { id: 'x' } });

      const result = await apiService.post('/api/workflows', { input: 1 });

      expect(mockClient.post).toHaveBeenCalledWith('/api/workflows', { input: 1 }, undefined);
      expect(result).toEqual({ success: true, data: { id: 'x' } });
    });

    test('should PUT the payload', async () => {
      const result = await apiService.put('/api/workflows/wf-1', { name: 'x' });

      expect(mockClient.put).toHaveBeenCalledWith('/api/workflows/wf-1', { name: 'x' }, undefined);
      expect(result).toEqual({ success: true, data: { ok: true } });
    });

    test('should DELETE the resource', async () => {
      const result = await apiService.delete('/api/workflows/wf-1');

      expect(mockClient.delete).toHaveBeenCalledWith('/api/workflows/wf-1', undefined);
      expect(result).toEqual({ success: true, data: { ok: true } });
    });

    test('should map the backend detail on failure', async () => {
      mockClient.get.mockRejectedValue({
        response: { status: 404, data: { detail: 'Workflow not found' } },
      });

      const result = await apiService.get('/api/workflows/missing');

      expect(result).toEqual({ success: false, error: 'Workflow not found' });
    });

    test('should fall back to the error message when no detail is present', async () => {
      mockClient.post.mockRejectedValue(new Error('Network request failed'));

      const result = await apiService.post('/api/x');

      expect(result).toEqual({ success: false, error: 'Network request failed' });
    });

    test('should use a generic error when nothing else is available', async () => {
      mockClient.put.mockRejectedValue({});

      const result = await apiService.put('/api/x');

      expect(result).toEqual({ success: false, error: 'Request failed' });
    });

    // Each HTTP verb shares the same error-mapping expression. Exercise every
    // branch of `response?.data?.detail || error.message || 'Request failed'`
    // for all four verbs.
    const verbs = [
      ['get', (url: string) => apiService.get(url)],
      ['post', (url: string) => apiService.post(url)],
      ['put', (url: string) => apiService.put(url)],
      ['delete', (url: string) => apiService.delete(url)],
    ] as const;

    test('should map failure detail for every HTTP verb', async () => {
      const detailError = {
        response: { status: 400, data: { detail: 'Invalid input' } },
      };
      mockClient.get.mockRejectedValue(detailError);
      mockClient.post.mockRejectedValue(detailError);
      mockClient.put.mockRejectedValue(detailError);
      mockClient.delete.mockRejectedValue(detailError);

      for (const [, invoke] of verbs) {
        expect((await invoke('/x')).error).toBe('Invalid input');
      }
    });

    test('should fall back to the message when a response has no detail', async () => {
      const noDetailError: any = new Error('Backend said no');
      noDetailError.response = { status: 500, data: {} };
      mockClient.get.mockRejectedValue(noDetailError);
      mockClient.post.mockRejectedValue(noDetailError);
      mockClient.put.mockRejectedValue(noDetailError);
      mockClient.delete.mockRejectedValue(noDetailError);

      for (const [, invoke] of verbs) {
        expect((await invoke('/x')).error).toBe('Backend said no');
      }
    });

    test('should use the message for every verb when the request throws', async () => {
      const networkError = new Error('Connection reset');
      mockClient.get.mockRejectedValue(networkError);
      mockClient.post.mockRejectedValue(networkError);
      mockClient.put.mockRejectedValue(networkError);
      mockClient.delete.mockRejectedValue(networkError);

      for (const [, invoke] of verbs) {
        expect((await invoke('/x')).error).toBe('Connection reset');
      }
    });

    test('should use the generic fallback for every verb', async () => {
      mockClient.get.mockRejectedValue({});
      mockClient.post.mockRejectedValue({});
      mockClient.put.mockRejectedValue({});
      mockClient.delete.mockRejectedValue({});

      for (const [, invoke] of verbs) {
        expect((await invoke('/x')).error).toBe('Request failed');
      }
    });

    test('should use the production base URL outside dev builds', () => {
      jest.isolateModules(() => {
        (global as any).__DEV__ = false;
        try {
          const { apiService: prodApi } = require('../../services/api');
          expect((prodApi as any).client.defaults.baseURL).toBe(
            'https://api.atom-platform.com'
          );
        } finally {
          (global as any).__DEV__ = true;
        }
      });
    });
  });
});
