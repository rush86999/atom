/**
 * useMemorySearch Branch Coverage Tests (wave 119)
 *
 * Closes the remaining gaps in useMemorySearch.ts:
 * - `res.ok` false branch (toast "Failed to search historical data")
 * - `data.success`/`data.results` falsy branch (clears results)
 * - stale-response guard: out-of-order fetch must not overwrite newer results
 *   (requestIdRef token, BUG-040), including the finally-block isSearching
 *   guard
 */

import { renderHook, act } from '@testing-library/react';

import { useMemorySearch } from '../useMemorySearch';

jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

describe('useMemorySearch - Branch Coverage', () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = global.fetch = jest.fn();
    jest.clearAllMocks();
  });

  test('clears results when response has success but no results', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });

    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.searchMemory('test');
    });

    expect(result.current.results).toEqual([]);
  });

  test('clears results when response success is false', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: false, results: [{ id: 'x' }] }),
    });

    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.searchMemory('test');
    });

    expect(result.current.results).toEqual([]);
  });

  test('shows "failed" toast on non-ok HTTP response', async () => {
    const { toast } = require('sonner');
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.searchMemory('test');
    });

    expect(toast.error).toHaveBeenCalledWith('Failed to search historical data');
    expect(result.current.results).toEqual([]);
    expect(result.current.isSearching).toBe(false);
  });

  test('out-of-order stale response does not overwrite newer results', async () => {
    let resolveFirst: (v: any) => void;
    const firstResponse = new Promise<any>(res => {
      resolveFirst = res;
    });

    mockFetch
      .mockReturnValueOnce(firstResponse)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'new-result' }],
        }),
      });

    const { result } = renderHook(() => useMemorySearch());

    let firstSearch: Promise<void>;
    await act(async () => {
      firstSearch = result.current.searchMemory('stale');
      await result.current.searchMemory('fresh');
    });

    expect(result.current.results).toEqual([{ id: 'new-result' }]);

    // Now the stale (first) request resolves — must be discarded
    await act(async () => {
      resolveFirst!({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'stale-result' }],
        }),
      });
      await firstSearch;
    });

    expect(result.current.results).toEqual([{ id: 'new-result' }]);
    expect(result.current.isSearching).toBe(false);
  });

  test('stale response superseded during json() parse is discarded', async () => {
    let resolveJson: (v: any) => void;
    const jsonPromise = new Promise<any>(res => {
      resolveJson = res;
    });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => jsonPromise,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'newer-result' }],
        }),
      });

    const { result } = renderHook(() => useMemorySearch());

    let firstSearch: Promise<void>;
    await act(async () => {
      firstSearch = result.current.searchMemory('stale');
      // Yield one macrotask so the stale search passes its post-fetch guard
      // and suspends inside res.json() while the token is still 1.
      await new Promise(res => setTimeout(res, 0));
      await result.current.searchMemory('fresh');
    });

    // json of the stale response settles after the newer search finished
    await act(async () => {
      resolveJson!({
        success: true,
        results: [{ id: 'stale-result' }],
      });
      await firstSearch;
    });

    expect(result.current.results).toEqual([{ id: 'newer-result' }]);
    expect(result.current.isSearching).toBe(false);
  });

  test('stale request failure does not clear newer results or toast', async () => {
    const { toast } = require('sonner');
    let rejectFirst: (v: any) => void;
    const firstResponse = new Promise<any>((_, rej) => {
      rejectFirst = rej;
    });

    mockFetch
      .mockReturnValueOnce(firstResponse)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'fresh-result' }],
        }),
      });

    const { result } = renderHook(() => useMemorySearch());

    let firstSearch: Promise<void>;
    await act(async () => {
      firstSearch = result.current.searchMemory('stale');
      await result.current.searchMemory('fresh');
    });

    expect(result.current.results).toEqual([{ id: 'fresh-result' }]);

    await act(async () => {
      rejectFirst!(new Error('stale network error'));
      await firstSearch.catch(() => {});
    });

    expect(result.current.results).toEqual([{ id: 'fresh-result' }]);
    expect(toast.error).not.toHaveBeenCalledWith(
      'Error searching historical data'
    );
    expect(result.current.isSearching).toBe(false);
  });

  test('isSearching stays true while a newer request is in flight', async () => {
    let resolveSecond: (v: any) => void;
    const secondResponse = new Promise<any>(res => {
      resolveSecond = res;
    });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [{ id: 'first' }] }),
      })
      .mockReturnValueOnce(secondResponse);

    const { result } = renderHook(() => useMemorySearch());

    await act(async () => {
      await result.current.searchMemory('one');
    });

    let secondSearch: Promise<void>;
    await act(async () => {
      secondSearch = result.current.searchMemory('two');
    });

    // First request settled, second in flight → still searching
    expect(result.current.isSearching).toBe(true);

    await act(async () => {
      resolveSecond!({
        ok: true,
        json: async () => ({ success: true, results: [{ id: 'second' }] }),
      });
      await secondSearch;
    });

    expect(result.current.results).toEqual([{ id: 'second' }]);
    expect(result.current.isSearching).toBe(false);
  });
});
