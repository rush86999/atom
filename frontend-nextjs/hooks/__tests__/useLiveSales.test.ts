/**
 * useLiveSales Hook Unit Tests
 *
 * Tests for useLiveSales hook managing live sales pipeline polling.
 * Verifies data fetching, polling behavior, API response parsing,
 * deal data structure validation, and provider tracking.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveSales } from '../useLiveSales';
import { rest } from 'msw';
import { overrideHandler } from '@/tests/mocks/server';

describe('useLiveSales Hook', () => {
  const mockDeals = [
    {
      id: 'deal-1',
      deal_name: 'Enterprise Software License',
      value: 50000.00,
      status: 'Open',
      stage: 'Negotiation',
      platform: 'salesforce',
      company: 'Acme Corporation',
      close_date: '2025-02-15',
      owner: 'John Smith',
      probability: 75,
      url: 'https://salesforce.com/deal-1'
    },
    {
      id: 'deal-2',
      deal_name: 'Cloud Migration Project',
      value: 120000.00,
      status: 'Open',
      stage: 'Proposal',
      platform: 'hubspot',
      company: 'Tech Solutions Inc',
      close_date: '2025-03-01',
      owner: 'Jane Doe',
      probability: 50,
      url: 'https://hubspot.com/deal-2'
    },
    {
      id: 'deal-3',
      deal_name: 'Annual Support Contract',
      value: 25000.00,
      status: 'Closed Won',
      stage: 'Closed',
      platform: 'zoho',
      company: 'Global Industries',
      close_date: '2025-01-20',
      owner: 'Bob Johnson',
      probability: 100,
      url: 'https://zoho.com/deal-3'
    }
  ];

  const mockStats = {
    total_pipeline_value: 195000.00,
    active_deal_count: 2,
    win_rate: 65.5,
    avg_deal_size: 65000.00
  };

  const mockProviders = {
    salesforce: true,
    hubspot: true,
    zoho: true,
    dynamics: false
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('1. Data Fetching Tests', () => {
    test('fetches sales pipeline on mount', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.deals).toEqual(mockDeals);
      });
    });

    test('sets deals state', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.deals).toHaveLength(3);
        expect(result.current.deals[0].deal_name).toBe('Enterprise Software License');
      });
    });

    test('sets stats state', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.stats).toEqual(mockStats);
        expect(result.current.stats.total_pipeline_value).toBe(195000.00);
        expect(result.current.stats.active_deal_count).toBe(2);
        expect(result.current.stats.win_rate).toBe(65.5);
        expect(result.current.stats.avg_deal_size).toBe(65000.00);
      });
    });

    test('sets activeProviders state', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(mockProviders);
        expect(result.current.activeProviders.salesforce).toBe(true);
        expect(result.current.activeProviders.dynamics).toBe(false);
      });
    });

    test('parses LivePipelineResponse correctly', async () => {
      const mockResponse = {
        ok: true,
        stats: mockStats,
        deals: mockDeals,
        providers: mockProviders
      };

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.deals).toEqual(mockResponse.deals);
        expect(result.current.stats).toEqual(mockResponse.stats);
        expect(result.current.activeProviders).toEqual(mockResponse.providers);
      });
    });

    test('sets loading to false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('2. Data Structure Tests', () => {
    test('UnifiedDeal interface fields', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        result.current.deals.forEach(deal => {
          expect(deal).toHaveProperty('id');
          expect(deal).toHaveProperty('deal_name');
          expect(deal).toHaveProperty('value');
          expect(deal).toHaveProperty('status');
          expect(deal).toHaveProperty('stage');
          expect(deal).toHaveProperty('platform');
          expect(deal).toHaveProperty('company');
          expect(deal).toHaveProperty('close_date');
          expect(deal).toHaveProperty('owner');
          expect(deal).toHaveProperty('probability');
          expect(deal).toHaveProperty('url');

          expect(typeof deal.id).toBe('string');
          expect(typeof deal.deal_name).toBe('string');
          expect(typeof deal.value).toBe('number');
          expect(typeof deal.status).toBe('string');
          expect(typeof deal.stage).toBe('string');
          expect(typeof deal.platform).toBe('string');
          expect(typeof deal.probability).toBe('number');
        });
      });
    });

    test('platform types: salesforce, hubspot, zoho, dynamics', async () => {
      const multiPlatformDeals = [
        { ...mockDeals[0], platform: 'salesforce' },
        { ...mockDeals[1], platform: 'hubspot' },
        { ...mockDeals[2], platform: 'zoho' },
        {
          id: 'deal-4',
          deal_name: 'Dynamics Deal',
          value: 75000.00,
          status: 'Open',
          stage: 'Qualification',
          platform: 'dynamics',
          company: 'Company D',
          close_date: '2025-04-01',
          owner: 'Alice',
          probability: 25,
          url: 'https://dynamics.com/deal-4'
        }
      ];

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: multiPlatformDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        const platforms = result.current.deals.map(d => d.platform);
        expect(platforms).toContain('salesforce');
        expect(platforms).toContain('hubspot');
        expect(platforms).toContain('zoho');
        expect(platforms).toContain('dynamics');
      });
    });

    test('SalesStats structure', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.stats).toHaveProperty('total_pipeline_value');
        expect(result.current.stats).toHaveProperty('active_deal_count');
        expect(result.current.stats).toHaveProperty('win_rate');
        expect(result.current.stats).toHaveProperty('avg_deal_size');

        expect(typeof result.current.stats.total_pipeline_value).toBe('number');
        expect(typeof result.current.stats.active_deal_count).toBe('number');
        expect(typeof result.current.stats.win_rate).toBe('number');
        expect(typeof result.current.stats.avg_deal_size).toBe('number');
      });
    });

    test('optional fields in UnifiedDeal', async () => {
      const dealsWithOptionals = [
        {
          id: 'deal-1',
          deal_name: 'Deal without optionals',
          value: 10000.00,
          status: 'Open',
          stage: 'Lead',
          platform: 'salesforce'
          // company, close_date, owner, probability, url are optional
        }
      ];

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: dealsWithOptionals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.deals[0].company).toBeUndefined();
        expect(result.current.deals[0].close_date).toBeUndefined();
        expect(result.current.deals[0].owner).toBeUndefined();
        expect(result.current.deals[0].probability).toBeUndefined();
      });
    });
  });

  describe('3. Polling Behavior Tests', () => {
    test('sets up 60-second interval', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveSales());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward 60 seconds
      act(() => {
        jest.advanceTimersByTime(60000);
      });

      // Should have fetched again
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });
    });

    test('cleans up interval on unmount', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveSales());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Unmount the hook
      unmount();

      // Fast-forward past the interval time
      act(() => {
        jest.advanceTimersByTime(60000);
      });

      // Should not have fetched again after unmount
      expect(fetchCount).toBe(1);
    });

    test('clears interval in cleanup function', async () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: [],
              providers: {}
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveSales());

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });

    test('polls multiple times over time', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveSales());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward through multiple intervals
      act(() => {
        jest.advanceTimersByTime(60000); // 1st interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });

      act(() => {
        jest.advanceTimersByTime(60000); // 2nd interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(3);
      });

      act(() => {
        jest.advanceTimersByTime(60000); // 3rd interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(4);
      });
    });
  });

  describe('4. Refresh Function Tests', () => {
    test('re-fetches pipeline data when called', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Call refresh
      act(() => {
        result.current.refresh();
      });

      // Should have fetched again
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });
    });

    test('updates all states on refresh', async () => {
      let callCount = 0;

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              stats: {
                total_pipeline_value: callCount * 100000,
                active_deal_count: callCount * 2,
                win_rate: callCount * 30,
                avg_deal_size: callCount * 50000
              },
              deals: callCount === 1 ? mockDeals : [],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      // Initial fetch
      await waitFor(() => {
        expect(result.current.stats.total_pipeline_value).toBe(100000);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      await waitFor(() => {
        expect(result.current.stats.total_pipeline_value).toBe(200000);
        expect(result.current.deals).toEqual([]);
      });
    });
  });

  describe('5. Loading States Tests', () => {
    test('initial isLoading is true', () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      expect(result.current.isLoading).toBe(true);
    });

    test('becomes false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('handles loading state on error', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveSales());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('6. Error Handling Tests', () => {
    test('handles fetch errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch live sales pipeline:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });

    test('console.error called with error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          throw new Error('Network error');
        })
      );

      renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to fetch live sales pipeline:',
          expect.any(Error)
        );
      });
      consoleSpy.mockRestore();
    });

    test('handles non-OK response', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.deals).toEqual([]);
      });
    });
  });

  describe('7. Provider Tracking Tests', () => {
    test('tracks active providers correctly', async () => {
      const customProviders = {
        salesforce: true,
        hubspot: false,
        zoho: true,
        dynamics: true
      };

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: customProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(customProviders);
        expect(Object.keys(result.current.activeProviders)).toHaveLength(4);
      });
    });

    test('updates providers on refresh', async () => {
      let callCount = 0;

      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: callCount === 1
                ? { salesforce: true, hubspot: false, zoho: false, dynamics: false }
                : { salesforce: true, hubspot: true, zoho: true, dynamics: true }
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      // Initial state
      await waitFor(() => {
        expect(result.current.activeProviders.hubspot).toBe(false);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      // Updated state
      await waitFor(() => {
        expect(result.current.activeProviders.hubspot).toBe(true);
        expect(result.current.activeProviders.zoho).toBe(true);
      });
    });
  });

  describe('8. Deal Data Mapping Tests', () => {
    test('maps deal values correctly', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        const values = result.current.deals.map(d => d.value);
        expect(values).toContain(50000.00);
        expect(values).toContain(120000.00);
        expect(values).toContain(25000.00);
      });
    });

    test('maps deal stages correctly', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        const stages = result.current.deals.map(d => d.stage);
        expect(stages).toContain('Negotiation');
        expect(stages).toContain('Proposal');
        expect(stages).toContain('Closed');
      });
    });

    test('maps deal probabilities correctly', async () => {
      overrideHandler(
        rest.get('/api/atom/sales/live/pipeline', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              deals: mockDeals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveSales());

      await waitFor(() => {
        const probabilities = result.current.deals.map(d => d.probability);
        expect(probabilities).toContain(75);
        expect(probabilities).toContain(50);
        expect(probabilities).toContain(100);
      });
    });
  });
});
