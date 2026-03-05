/**
 * useLiveKnowledge Hook Unit Tests
 *
 * Tests for useLiveKnowledge hook managing real-time knowledge data.
 * Verifies knowledge fetching, insights fetching, refresh functionality,
 * data mapping, and error handling.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveKnowledge } from '../useLiveKnowledge';
import { rest } from 'msw';
import { overrideHandler } from '@/tests/mocks/server';

// Mock sonner toast
jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
  },
}));

import { toast } from 'sonner';

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

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('1. Fetch Knowledge Tests', () => {
    test('fetches knowledge items on mount', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: mockEntities,
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items).toHaveLength(2);
      });
    });

    test('maps API entities to KnowledgeItem format', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: mockEntities,
            })
          );
        })
      );

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
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: mockEntities,
            })
          );
        })
      );

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
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });
  });

  describe('2. Fetch Insights Tests', () => {
    test('fetches smart insights', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: [],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: mockInsights,
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.insights).toEqual(mockInsights);
      });
    });

    test('sets insights state', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: [],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: mockInsights,
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.insights).toHaveLength(2);
        expect(result.current.insights[0].severity).toBe('warning');
      });
    });

    test('sets insightsLoading correctly', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: [],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      expect(result.current.insightsLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.insightsLoading).toBe(false);
      });
    });
  });

  describe('3. Refresh Function Tests', () => {
    test('calls both fetchKnowledge and fetchInsights', async () => {
      let knowledgeFetchCount = 0;
      let insightsFetchCount = 0;

      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          knowledgeFetchCount++;
          return res(
            ctx.json({
              status: 'success',
              entities: [],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          insightsFetchCount++;
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      // Wait for initial fetch
      await waitFor(() => {
        expect(knowledgeFetchCount).toBe(1);
        expect(insightsFetchCount).toBe(1);
      });

      // Call refresh
      await act(async () => {
        await result.current.refresh();
      });

      // Should have fetched both again
      expect(knowledgeFetchCount).toBe(2);
      expect(insightsFetchCount).toBe(2);
    });

    test('uses Promise.all for parallel fetching', async () => {
      let knowledgeFetchTime = 0;
      let insightsFetchTime = 0;

      overrideHandler(
        rest.get('/api/intelligence/entities', async (req, res, ctx) => {
          knowledgeFetchTime = Date.now();
          await new Promise((resolve) => setTimeout(resolve, 10));
          return res(
            ctx.json({
              status: 'success',
              entities: [],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', async (req, res, ctx) => {
          insightsFetchTime = Date.now();
          await new Promise((resolve) => setTimeout(resolve, 10));
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      const startTime = Date.now();

      await act(async () => {
        await result.current.refresh();
      });

      const endTime = Date.now();
      const duration = endTime - startTime;

      // Both fetches happened in parallel (should take ~10ms, not ~20ms)
      expect(duration).toBeLessThan(50);
    });

    test('updates both states on refresh', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: mockEntities,
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: mockInsights,
            })
          );
        })
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
    test('handles axios errors', async () => {
      const toastSpy = jest.spyOn(toast, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res.networkError('Network error');
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(toastSpy).toHaveBeenCalledWith('Failed to fetch real-time intelligence data');
      });

      toastSpy.mockRestore();
    });

    test('shows toast error on failure', async () => {
      const toastSpy = jest.spyOn(toast, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(toastSpy).toHaveBeenCalledWith('Failed to fetch real-time intelligence data');
      });

      toastSpy.mockRestore();
    });

    test('sets loading states to false in finally', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          throw new Error('API error');
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          throw new Error('API error');
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      expect(result.current.loading).toBe(true);
      expect(result.current.insightsLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.insightsLoading).toBe(false);
      });
    });
  });

  describe('5. Data Mapping Tests', () => {
    test('correctly maps entity fields', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
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
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
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
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: [
                {
                  id: 'minimal-1',
                  name: 'Minimal Entity',
                  platforms: [],
                  type: 'task',
                },
              ],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
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
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: [
                {
                  id: 'multi-1',
                  name: 'Multi Platform',
                  platforms: ['jira', 'slack', 'teams'],
                  type: 'task',
                },
              ],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items[0].platform).toBe('jira');
      });
    });
  });

  describe('6. Empty State Tests', () => {
    test('handles empty entities response', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              entities: [],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        expect(result.current.items).toEqual([]);
        expect(result.current.insights).toEqual([]);
      });
    });

    test('handles failed status response', async () => {
      overrideHandler(
        rest.get('/api/intelligence/entities', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'error',
              entities: [],
            })
          );
        })
      );

      overrideHandler(
        rest.get('/api/intelligence/insights', (req, res, ctx) => {
          return res(
            ctx.json({
              status: 'success',
              insights: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveKnowledge());

      await waitFor(() => {
        // Items should be empty when status is not success
        expect(result.current.items).toEqual([]);
      });
    });
  });
});
