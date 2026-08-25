/**
 * useLiveSupport Branch Coverage Tests (wave 119)
 *
 * Closes the remaining branch gaps in useLiveSupport.ts:
 * - auth_token → token localStorage fallback chain
 * - no-token → empty headers
 * - response shape fallbacks (data.tickets / data array / neither)
 * - non-ok HTTP response error path
 * - non-Error rejection → generic message
 */

import { renderHook, act } from '@testing-library/react';
import { useLiveSupport } from '../useLiveSupport';

const API_BASE = '';

// jsdom exposes localStorage as a getter-only accessor — plain assignment
// silently fails; defineProperty is required (same pattern as api-admin.test).
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

describe('useLiveSupport - Branch Coverage', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = global.fetch = jest.fn();
    jest.clearAllMocks();
    // clearMocks wipes implementations; give getItem a backing store
    const store: Record<string, string> = {};
    (mockLocalStorage.getItem as jest.Mock).mockImplementation(
      (key: string) => store[key] ?? null
    );
    (global as any).__lsStore = store;
  });

  test('falls back to the token key when auth_token is absent', async () => {
    const store = (global as any).__lsStore;
    store['token'] = 'fallback-token';
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ tickets: [] }),
    });

    renderHook(() => useLiveSupport());
    await act(async () => {});

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/atom/communication/live/support/tickets`,
      { headers: { Authorization: 'Bearer fallback-token' } }
    );
  });

  test('sends no Authorization header when no token exists', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ tickets: [] }),
    });

    renderHook(() => useLiveSupport());
    await act(async () => {});

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/atom/communication/live/support/tickets`,
      { headers: {} }
    );
  });

  test('accepts a bare array response body', async () => {
    const store = (global as any).__lsStore; store['auth_token'] = 'tok';
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: 't1' }],
    });

    const { result } = renderHook(() => useLiveSupport());
    await act(async () => {});

    expect(result.current.tickets).toHaveLength(1);
    expect(result.current.isLoading).toBe(false);
  });

  test('falls back to an empty list for an unexpected body shape', async () => {
    const store = (global as any).__lsStore; store['auth_token'] = 'tok';
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ unexpected: true }),
    });

    const { result } = renderHook(() => useLiveSupport());
    await act(async () => {});

    expect(result.current.tickets).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  test('sets an HTTP error and clears tickets on a non-ok response', async () => {
    const store = (global as any).__lsStore; store['auth_token'] = 'tok';
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({}),
    });

    const { result } = renderHook(() => useLiveSupport());
    await act(async () => {});

    expect(result.current.error).toBe('HTTP 503');
    expect(result.current.tickets).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  test('uses a generic message for non-Error rejections', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    const store = (global as any).__lsStore; store['auth_token'] = 'tok';
    mockFetch.mockRejectedValueOnce('network-broke-string');

    const { result } = renderHook(() => useLiveSupport());
    await act(async () => {});

    expect(result.current.error).toBe('Failed to load');
    expect(result.current.tickets).toEqual([]);
    consoleSpy.mockRestore();
  });
});
