/**
 * useLiveKnowledge Hook Unit Tests
 *
 * The real useLiveKnowledge hook calls apiClient.get() for
 * /api/intelligence/entities and /api/intelligence/insights (both run on mount
 * via refresh()) and returns { items, insights, loading, insightsLoading,
 * refresh }.
 *
 * The old suite relied on MSW handlers with relative paths (/api/...), but
 * axios resolves those against apiClient's baseURL (http://127.0.0.1:8000 in
 * the test env) while MSW resolves relative paths against jsdom's origin
 * (http://localhost), so no request was ever intercepted and every test timed
 * out. We mock @/lib/api directly to test the hook's real mapping/loading/
 * error behavior.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveKnowledge } from '../useLiveKnowledge';

// Mock sonner toast
jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

import { toast } from 'sonner';

// Mock the apiClient the hook imports from @/lib/api
jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
  },
}));

import { apiClient } from '@/lib/api';
const mockGet = apiClient.get as jest.Mock;

describe('useLiveKnowledge Hook', () => {
  const mockEntities = [
    {
      id: 'entity-1',
      name: 'Project Alpha',
      platforms: ['jira', 'slack'],
      type: 'task',
      status: 'in_progress',
      value: 1000,
      modified_at: '2026-03-04T10:00:00Z',
    },
    {
      id: 'entity-2',
      name: 'Client Deal',
      platforms: ['salesforce'],
      type: 'deal',
      status: 'active',
      value: 5000,
      modified_at: '2026-03-04T09:00:00Z',
    },
  ];

  const mockInsights = [
    {
      anomaly_id: 'anomaly-1',
      severity: 'warning',
      title: 'High Task Volume',
      description: 'Unusual spike in task creation detected',
      affected_entities: ['entity-1', 'entity-2'],
      platforms: ['jira'],
      recommendation: 'Review recent task assignments',
      timestamp: '2026-03-04T10:30:00Z',
    },
    {
      anomaly_id: 'anomaly-2',
      severity: 'info',
      title: 'New Integration Active',
      description: 'Slack integration successfully connected',
      affected_entities: ['workspace-1'],
      platforms: ['slack'],
      recommendation: 'Monitor integration performance',
      timestamp: '2026-03-04T09:30:00Z',
    },
  ];

  // Configure apiClient.get to answer per-endpoint with the given payloads.
  const mockApi = (
    entities: any,
    insights: any,
    options: { entitiesReject?: boolean; insightsReject?: boolean } = {}
  ) => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/api/intelligence/entities') {
        return options.entitiesReject
          ? Promise.reject(new Error('Network error'))
          : Promise.resolve({ data: entities });
      }
      if (url === '/api/intelligence/insights') {
        return options.insightsReject
          ? Promise.reject(new Error('Network error'))
          : Promise.resolve({ data: insights });
      }
      return Promise.resolve({ data: {} });
    });
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockReset();
    // Default: both endpoints succeed with empty payloads.
    mockApi(
      { status: 'success', entities: [] },
      { status: 'success', insights: [] }
    );
  });

  describe('1. Fetch Knowledge Tests', () => {
    test('fetches knowledge items on mount', async () => {
      mockApi({ status: 'success', entities: mockEntities }, { status: 'success', insights: [] });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items).toHaveLength(2);
      });
      expect(mockGet).toHaveBeenCalledWith('/api/intelligence/entities');
    });

    test('maps API entities to KnowledgeItem format', async () => {
      mockApi({ status: 'success', entities: mockEntities }, { status: 'success', insights: [] });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items[0]).toMatchObject({
          id: 'entity-1',
          name: 'Project Alpha',
          platform: 'jira',
          type: 'task',
        });
      });
    });

    test('sets items state correctly', async () => {
      mockApi({ status: 'success', entities: mockEntities }, { status: 'success', insights: [] });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items).toEqual([
          {
            id: 'entity-1',
            name: 'Project Alpha',
            platform: 'jira',
            type: 'task',
            status: 'in_progress',
            value: 1000,
            modified_at: '2026-03-04T10:00:00Z',
          },
          {
            id: 'entity-2',
            name: 'Client Deal',
            platform: 'salesforce',
            type: 'deal',
            status: 'active',
            value: 5000,
            modified_at: '2026-03-04T09:00:00Z',
          },
        ]);
      });
    });

    test('handles loading states', async () => {
      const { result } = renderHook(() => useLiveKnowledge());

      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });
  });

  describe('2. Fetch Insights Tests', () => {
    test('fetches smart insights', async () => {
      mockApi({ status: 'success', entities: [] }, { status: 'success', insights: mockInsights });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.insights).toEqual(mockInsights);
      });
    });

    test('sets insights state', async () => {
      mockApi({ status: 'success', entities: [] }, { status: 'success', insights: mockInsights });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.insights).toHaveLength(2);
        expect(result.current.insights[0].severity).toBe('warning');
      });
    });

    test('sets insightsLoading correctly', async () => {
      const { result } = renderHook(() => useLiveKnowledge());

      expect(result.current.insightsLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.insightsLoading).toBe(false);
      });
    });
  });

  describe('3. Refresh Function Tests', () => {
    test('calls both fetchKnowledge and fetchInsights', async () => {
      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(mockGet).toHaveBeenCalledWith('/api/intelligence/entities');
        expect(mockGet).toHaveBeenCalledWith('/api/intelligence/insights');
      });

      const callsBefore = mockGet.mock.calls.length;

      await act(async () => {
        await result.current.refresh();
      });

      expect(mockGet.mock.calls.length).toBe(callsBefore + 2);
    });

    test('updates both states on refresh', async () => {
      mockApi(
        { status: 'success', entities: mockEntities },
        { status: 'success', insights: mockInsights }
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await act(async () => {
        await result.current.refresh();
      });

      expect(result.current.items).toHaveLength(2);
      expect(result.current.insights).toHaveLength(2);
    });
  });

  describe('4. Error Handling Tests', () => {
    test('shows a toast error when the entities fetch fails', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const toastSpy = jest.spyOn(toast, 'error').mockImplementation();

      mockApi({ status: 'success', entities: [] }, { status: 'success', insights: [] }, { entitiesReject: true });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(toastSpy).toHaveBeenCalledWith(
          'Failed to fetch real-time intelligence data'
        );
      });

      toastSpy.mockRestore();
      consoleSpy.mockRestore();
    });

    test('does not toast on an insights failure (only console.error)', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const toastSpy = jest.spyOn(toast, 'error').mockImplementation();

      mockApi({ status: 'success', entities: [] }, { status: 'success', insights: [] }, { insightsReject: true });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.insightsLoading).toBe(false);
      });

      expect(toastSpy).not.toHaveBeenCalled();

      toastSpy.mockRestore();
      consoleSpy.mockRestore();
    });

    test('sets loading states to false in finally', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      mockApi({ status: 'success', entities: [] }, { status: 'success', insights: [] }, {
        entitiesReject: true,
        insightsReject: true,
      });

      const { result } = renderHook(() => useLiveKnowledge());

      expect(result.current.loading).toBe(true);
      expect(result.current.insightsLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.insightsLoading).toBe(false);
      });

      consoleSpy.mockRestore();
    });
  });

  describe('5. Data Mapping Tests', () => {
    test('correctly maps entity fields', async () => {
      mockApi(
        {
          status: 'success',
          entities: [
            {
              id: 'test-1',
              name: 'Test Entity',
              platforms: ['platform1', 'platform2'],
              type: 'file',
              status: 'active',
              value: 999,
              modified_at: '2026-03-04T12:00:00Z',
              extra_field: 'should be ignored',
            },
          ],
        },
        { status: 'success', insights: [] }
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items[0]).toEqual({
          id: 'test-1',
          name: 'Test Entity',
          platform: 'platform1', // First platform from array
          type: 'file',
          status: 'active',
          value: 999,
          modified_at: '2026-03-04T12:00:00Z',
        });
      });
    });

    test('handles missing fields gracefully', async () => {
      mockApi(
        {
          status: 'success',
          entities: [
            {
              id: 'minimal-1',
              name: 'Minimal Entity',
              platforms: [],
              type: 'task',
            },
          ],
        },
        { status: 'success', insights: [] }
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items[0]).toMatchObject({
          id: 'minimal-1',
          name: 'Minimal Entity',
          platform: 'unknown', // Fallback when platforms array is empty
          type: 'task',
        });
      });
    });

    test('uses first platform when multiple exist', async () => {
      mockApi(
        {
          status: 'success',
          entities: [
            {
              id: 'multi-1',
              name: 'Multi Platform',
              platforms: ['jira', 'slack', 'teams'],
              type: 'task',
            },
          ],
        },
        { status: 'success', insights: [] }
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items[0].platform).toBe('jira');
      });
    });
  });

  describe('6. Empty State Tests', () => {
    test('handles empty entities response', async () => {
      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items).toEqual([]);
        expect(result.current.insights).toEqual([]);
      });
    });

    test('handles failed status response', async () => {
      mockApi({ status: 'error', entities: [] }, { status: 'success', insights: [] });

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        // Items should be empty when status is not success
        expect(result.current.items).toEqual([]);
      });
    });
  });
});
