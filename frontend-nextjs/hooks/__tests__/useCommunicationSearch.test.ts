/**
 * useCommunicationSearch Hook Unit Tests
 *
 * Tests for useCommunicationSearch hook handling message search functionality.
 * Verifies search queries, query encoding, result state management, loading states,
 * empty query handling, error handling, and API integration.
 */

import { renderHook, act, waitFor } from '@testing-library/react';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods
import { useCommunicationSearch } from '../useCommunicationSearch';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods

// Mock toast from 'sonner'
jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

describe('useCommunicationSearch Hook', () => {
  const mockFetch = global.fetch as jest.MockedFunction<typeof global.fetch>;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('1. Search Functionality Tests', () => {
    test('searchMessages calls API with encoded query', async () => {
      const mockResults = [
        {
          id: 'msg-1',
          content: 'Test message',
          sender: 'user@example.com',
          timestamp: '2026-03-04T10:00:00Z',
          app_type: 'slack',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: mockResults,
        }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test query');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('query=' + encodeURIComponent('test query')),
        expect.any(Object)
      );
    });

    test('sets results state from response', async () => {
      const mockResults = [
        {
          id: 'msg-1',
          content: 'Test message',
          sender: 'user@example.com',
          timestamp: '2026-03-04T10:00:00Z',
          app_type: 'slack',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: mockResults,
        }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      // State should be updated after act completes
      expect(result.current.results).toEqual(mockResults);
    });

    test('sets isSearching during request', async () => {
      let resolveFetch: (value: any) => void;
      const fetchPromise = new Promise((resolve) => {
        resolveFetch = resolve;
      });

      mockFetch.mockReturnValueOnce(fetchPromise);

      const { result } = renderHook(() => useCommunicationSearch());

      act(() => {
        result.current.searchMessages('test');
      });

      // isSearching should be true during the request
      expect(result.current.isSearching).toBe(true);

      // Resolve the fetch
      await act(async () => {
        resolveFetch!({
          ok: true,
          json: async () => ({ success: true, results: [] }),
        });
      });
    });

    test('resets isSearching after completion', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.isSearching).toBe(false);
    });
  });

  describe('2. Empty Query Handling Tests', () => {
    test('returns early when query is empty', async () => {
      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('');
      });

      expect(mockFetch).not.toHaveBeenCalled();
    });

    test('returns early when query is whitespace only', async () => {
      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('   ');
      });

      expect(mockFetch).not.toHaveBeenCalled();
    });

    test('clears results for empty query', async () => {
      const { result } = renderHook(() => useCommunicationSearch());

      // First set some results
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [{ id: 'msg-1', content: 'Test', sender: 'test', timestamp: '2026-03-04T10:00:00Z', app_type: 'slack' }],
        }),
      });

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.results.length).toBe(1);

      // Now search with empty query
      await act(async () => {
        await result.current.searchMessages('');
      });

      expect(result.current.results).toEqual([]);
    });

    test('does not call API for empty query', async () => {
      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('');
      });

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('3. Search Result Structure Tests', () => {
    test('handles SearchResult interface fields', async () => {
      const mockResult = {
        id: 'msg-1',
        content: 'Test message content',
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

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.results[0]).toEqual(mockResult);
      expect(result.current.results[0].id).toBe('msg-1');
      expect(result.current.results[0].content).toBe('Test message content');
      expect(result.current.results[0].sender).toBe('user@example.com');
      expect(result.current.results[0].timestamp).toBe('2026-03-04T10:00:00Z');
      expect(result.current.results[0].app_type).toBe('slack');
    });

    test('handles data.success and data.results structure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [
            { id: 'msg-1', content: 'Test', sender: 'test', timestamp: '2026-03-04T10:00:00Z', app_type: 'slack' },
          ],
        }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.results).toHaveLength(1);
    });

    test('clears results when API returns success but no results', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          results: [],
        }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.results).toEqual([]);
    });

    test('clears results when API returns success false', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: false,
          results: null,
        }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.results).toEqual([]);
    });
  });

  describe('4. Error Handling Tests', () => {
    test('handles fetch errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.results).toEqual([]);
      expect(result.current.isSearching).toBe(false);
    });

    test('shows toast error on fetch failure', async () => {
      const { toast } = require('sonner');
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(toast.error).toHaveBeenCalledWith('Error searching messages');
    });

    test('shows toast error on API error response', async () => {
      const { toast } = require('sonner');
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(toast.error).toHaveBeenCalledWith('Failed to search messages');
    });

    test('sets isSearching to false on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(result.current.isSearching).toBe(false);
    });
  });

  describe('5. API URL Construction Tests', () => {
    test('uses correct endpoint /api/atom/communication/memory/search', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/atom/communication/memory/search?query=test&limit=20',
        expect.any(Object)
      );
    });

    test('encodes query parameter correctly', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test query with spaces');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/atom/communication/memory/search?query=' +
          encodeURIComponent('test query with spaces') +
          '&limit=20',
        expect.any(Object)
      );
    });

    test('encodes special characters in query', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test & query + special');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining(encodeURIComponent('test & query + special')),
        expect.any(Object)
      );
    });

    test('includes limit parameter as 20', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, results: [] }),
      });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('test');
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=20'),
        expect.any(Object)
      );
    });
  });

  describe('6. Multiple Sequential Searches Tests', () => {
    test('handles multiple searches in sequence', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            success: true,
            results: [{ id: 'msg-1', content: 'First', sender: 'test', timestamp: '2026-03-04T10:00:00Z', app_type: 'slack' }],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            success: true,
            results: [{ id: 'msg-2', content: 'Second', sender: 'test', timestamp: '2026-03-04T10:01:00Z', app_type: 'slack' }],
          }),
        });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('first');
      });

      expect(result.current.results[0].content).toBe('First');

      await act(async () => {
        await result.current.searchMessages('second');
      });

      expect(result.current.results[0].content).toBe('Second');
    });

    test('updates results on new search', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            success: true,
            results: [{ id: 'msg-1', content: 'Old', sender: 'test', timestamp: '2026-03-04T10:00:00Z', app_type: 'slack' }],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            success: true,
            results: [{ id: 'msg-2', content: 'New', sender: 'test', timestamp: '2026-03-04T10:01:00Z', app_type: 'slack' }],
          }),
        });

      const { result } = renderHook(() => useCommunicationSearch());

      await act(async () => {
        await result.current.searchMessages('old');
      });

      expect(result.current.results.length).toBe(1);

      await act(async () => {
        await result.current.searchMessages('new');
      });

      expect(result.current.results.length).toBe(1);
      expect(result.current.results[0].content).toBe('New');
    });
  });
});
