/**
 * useMemorySearch Hook Unit Tests
 *
 * Tests for useMemorySearch hook handling historical data search functionality.
 * Verifies search options (tag, appId, limit), URL construction, result state,
 * clearSearch function, and error handling.
 */

import { renderHook, act } from '@testing-library/react';
import { useMemorySearch } from '../useMemorySearch';

// Mock toast from 'sonner'
jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

describe('useMemorySearch Hook', () => {
  const mockFetch = global.fetch as jest.MockedFunction<typeof global.fetch>;

  beforeEach(() => {
    jest.clearAllMocks();
    // Ensure fetch is a Jest mock
    if (!jest.isMockFunction(global.fetch)) {
      global.fetch = jest.fn() as any;
    }
  });

  describe('1. Search Functionality Tests', () => {
    test('searchMemory calls API with query', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'mem-1', content: 'Test', sender: 'test', timestamp: '2026-03-04T10:00:00Z', app_type: 'slack' }],
        }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test query');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('query=test+query'),
        expect.any(Object)
      );
    });

    test('includes tag parameter when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch({ tag: 'important' }));

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('tag=important'),
        expect.any(Object)
      );
    });

    test('includes appId parameter when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch({ appId: 'app-123' }));

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('app_id=app-123'),
        expect.any(Object)
      );
    });

    test('includes limit parameter (default 20)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=20'),
        expect.any(Object)
      );
    });

    test('sets results state from response', async () => {
      const mockResults = [
        {
          id: 'mem-1',
          content: 'Test memory',
          sender: 'user@example.com',
          timestamp: '2026-03-04T10:00:00Z',
          app_type: 'email',
          subject: 'Test Subject',
          tags: ['important'],
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: mockResults,
        }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(result.current.results).toEqual(mockResults);
    });
  });

  describe('2. Options Handling Tests', () => {
    test('tag option is appended to URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch({ tag: 'urgent' }));

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('tag=urgent'),
        expect.any(Object)
      );
    });

    test('appId option is appended to URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch({ appId: 'slack-app' }));

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('app_id=slack-app'),
        expect.any(Object)
      );
    });

    test('custom limit value is used', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch({ limit: 50 }));

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=50'),
        expect.any(Object)
      );
    });

    test('default limit is 20', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=20'),
        expect.any(Object)
      );
    });
  });

  describe('3. Empty Query Handling Tests', () => {
    test('clears results for empty query', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'mem-1', content: 'Test', sender: 'test', timestamp: '2026-03-04T10:00:00Z', app_type: 'slack' }],
        }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(result.current.results.length).toBe(1);

      await act(async () => {
        await result.current.searchMemory('');
      });

      expect(result.current.results).toEqual([]);
    });

    test('does not call API for empty query', async () => {
      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('');
      });

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('4. Clear Search Tests', () => {
    test('clearSearch() clears results array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'mem-1', content: 'Test', sender: 'test', timestamp: '2026-03-04T10:00:00Z', app_type: 'slack' }],
        }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(result.current.results.length).toBe(1);

      act(() => {
        result.current.clearSearch();
      });

      expect(result.current.results).toEqual([]);
    });

    test('clearSearch() does not call API', async () => {
      const callCountBefore = mockFetch.mock.calls.length;

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      act(() => {
        result.current.clearSearch();
      });

      // fetch should only be called once for searchMemory, not for clearSearch
      expect(mockFetch.mock.calls.length).toBe(callCountBefore + 1);
    });
  });

  describe('5. Result Structure Tests', () => {
    test('MemorySearchResult interface fields - optional fields', async () => {
      const mockResult = {
        id: 'mem-1',
        content: 'Test content',
        sender: 'user@example.com',
        timestamp: '2026-03-04T10:00:00Z',
        app_type: 'slack',
        subject: 'Optional Subject',
        tags: ['tag1', 'tag2'],
        metadata: { key: 'value' },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [mockResult],
        }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(result.current.results[0].subject).toBe('Optional Subject');
      expect(result.current.results[0].tags).toEqual(['tag1', 'tag2']);
      expect(result.current.results[0].metadata).toEqual({ key: 'value' });
    });

    test('handles missing optional fields', async () => {
      const mockResult = {
        id: 'mem-1',
        content: 'Test content',
        sender: 'user@example.com',
        timestamp: '2026-03-04T10:00:00Z',
        app_type: 'slack',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [mockResult],
        }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(result.current.results[0].subject).toBeUndefined();
      expect(result.current.results[0].tags).toBeUndefined();
      expect(result.current.results[0].metadata).toBeUndefined();
    });
  });

  describe('6. Error Handling Tests', () => {
    test('handles fetch errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(result.current.results).toEqual([]);
      expect(result.current.isSearching).toBe(false);
    });

    test('shows toast error on failure', async () => {
      const { toast } = require('sonner');
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(toast.error).toHaveBeenCalledWith('Error searching historical data');
    });

    test('sets isSearching to false on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test');
      });

      expect(result.current.isSearching).toBe(false);
    });
  });

  describe('7. URL Construction Tests', () => {
    test('constructs URL with multiple options', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch({
        tag: 'important',
        appId: 'slack',
        limit: 30,
      }));

      await act(async () => {
        await result.current.searchMemory('test query');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('tag=important'),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('app_id=slack'),
        expect.any(Object)
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=30'),
        expect.any(Object)
      );
    });

    test('encodes query parameter correctly', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useMemorySearch());

      await act(async () => {
        await result.current.searchMemory('test query with spaces');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining(encodeURIComponent('test query with spaces')),
        expect.any(Object)
      );
    });
  });
});
