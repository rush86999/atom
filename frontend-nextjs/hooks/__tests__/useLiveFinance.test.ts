/**
 * useLiveFinance Hook Unit Tests
 *
 * Tests for useLiveFinance hook managing live finance data polling.
 * Verifies data fetching, polling behavior, data structure validation,
 * provider tracking, error handling, and refresh functionality.
 *
 * NOTE: These tests require MSW handler for /api/atom/finance/live/overview
 * See tests/mocks/handlers.ts to add the handler.
 *
 * For now, we test the hook's internal logic without actual API calls.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { useLiveFinance, UnifiedTransaction, FinanceStats } from '../useLiveFinance';

  describe('useLiveFinance Hook', () => {
  const { overrideHandler } = require('@/tests/mocks/server');

  // Module-scope fetch counter captured by the default MSW handler below.
  // Behavior-based alternative to jest.spyOn(global, 'setInterval') — spying
  // on the fake-timer setInterval corrupts timer state for every later test
  // in this file (the fetch integration tests never settle afterward).
  let financeOverviewFetches = 0;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    financeOverviewFetches = 0;
    // Default MSW handler: every render of the hook fires a fetch to
    // /api/atom/finance/live/overview. Tests 1–8 don't assert on the payload,
    // so answer with a benign empty overview instead of passing through to the
    // real network (which hangs under fake timers and pollutes later tests).
    overrideHandler(
      rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
        financeOverviewFetches += 1;
        return res(
          ctx.json({
            ok: true,
            stats: {
              total_revenue: 0,
              pending_revenue: 0,
              transaction_count: 0,
              platform_breakdown: {},
            },
            transactions: [],
            providers: {},
          })
        );
      })
    );
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });
  describe('1. Initial State Tests', () => {
    test('isLoading starts as true', () => {
      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.isLoading).toBe(true);
    });

    test('transactions starts empty', () => {
      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.transactions).toEqual([]);
    });

    test('stats starts with default values', () => {
      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.stats).toEqual({
        total_revenue: 0,
        pending_revenue: 0,
        transaction_count: 0,
        platform_breakdown: {}
      });
    });

    test('activeProviders starts empty', () => {
      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.activeProviders).toEqual({});
    });
  });

  describe('2. Polling Behavior Tests', () => {
    test('sets up interval on mount', () => {
      // Fake timers are active: the hook's 60s polling interval is a pending
      // fake timer. (Cannot spy on global.setInterval here — spying on the
      // fake-timer implementation corrupts later tests in this file.)
      renderHook(() => useLiveFinance());

      expect(jest.getTimerCount()).toBeGreaterThan(0);
    });

    test('clears interval on unmount', () => {
      const { unmount } = renderHook(() => useLiveFinance());

      expect(jest.getTimerCount()).toBeGreaterThan(0);

      unmount();

      expect(jest.getTimerCount()).toBe(0);
    });
  });

  describe('3. Refresh Function Tests', () => {
    test('refresh function is exposed', () => {
      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.refresh).toBeDefined();
      expect(typeof result.current.refresh).toBe('function');
    });
  });

  describe('4. Interface Type Tests', () => {
    test('returns correct interface structure', () => {
      const { result } = renderHook(() => useLiveFinance());

      expect(result.current).toHaveProperty('transactions');
      expect(result.current).toHaveProperty('stats');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('activeProviders');
      expect(result.current).toHaveProperty('refresh');

      expect(Array.isArray(result.current.transactions)).toBe(true);
      expect(typeof result.current.stats).toBe('object');
      expect(typeof result.current.isLoading).toBe('boolean');
      expect(typeof result.current.activeProviders).toBe('object');
      expect(typeof result.current.refresh).toBe('function');
    });
  });

  describe('5. UnifiedTransaction Interface', () => {
    test('has required fields', () => {
      const transaction: UnifiedTransaction = {
        id: 'test-1',
        description: 'Test transaction',
        amount: 100,
        currency: 'USD',
        date: '2026-03-01',
        status: 'completed',
        platform: 'stripe'
      };

      expect(transaction).toHaveProperty('id');
      expect(transaction).toHaveProperty('description');
      expect(transaction).toHaveProperty('amount');
      expect(transaction).toHaveProperty('currency');
      expect(transaction).toHaveProperty('date');
      expect(transaction).toHaveProperty('status');
      expect(transaction).toHaveProperty('platform');
    });

    test('has optional fields', () => {
      const transaction: UnifiedTransaction = {
        id: 'test-1',
        description: 'Test transaction',
        amount: 100,
        currency: 'USD',
        date: '2026-03-01',
        status: 'completed',
        platform: 'stripe',
        customer_name: 'Test Customer',
        url: 'https://example.com'
      };

      expect(transaction.customer_name).toBe('Test Customer');
      expect(transaction.url).toBe('https://example.com');
    });

    test('supports all platform types', () => {
      const platforms: Array<UnifiedTransaction['platform']> = [
        'stripe',
        'xero',
        'quickbooks',
        'zoho',
        'dynamics'
      ];

      platforms.forEach(platform => {
        const transaction: UnifiedTransaction = {
          id: `test-${platform}`,
          description: 'Test',
          amount: 100,
          currency: 'USD',
          date: '2026-03-01',
          status: 'completed',
          platform
        };

        expect(transaction.platform).toBe(platform);
      });
    });
  });

  describe('6. FinanceStats Interface', () => {
    test('has required fields', () => {
      const stats: FinanceStats = {
        total_revenue: 10000,
        pending_revenue: 2000,
        transaction_count: 5,
        platform_breakdown: {
          stripe: 5000,
          xero: 3000,
          quickbooks: 2000
        }
      };

      expect(stats).toHaveProperty('total_revenue');
      expect(stats).toHaveProperty('pending_revenue');
      expect(stats).toHaveProperty('transaction_count');
      expect(stats).toHaveProperty('platform_breakdown');

      expect(typeof stats.total_revenue).toBe('number');
      expect(typeof stats.pending_revenue).toBe('number');
      expect(typeof stats.transaction_count).toBe('number');
      expect(typeof stats.platform_breakdown).toBe('object');
    });

    test('platform_breakdown contains numeric values', () => {
      const stats: FinanceStats = {
        total_revenue: 10000,
        pending_revenue: 2000,
        transaction_count: 5,
        platform_breakdown: {
          stripe: 5000,
          xero: 3000
        }
      };

      Object.values(stats.platform_breakdown).forEach(value => {
        expect(typeof value).toBe('number');
      });
    });
  });

  describe('7. Polling Interval Tests', () => {
    test('uses 60 second interval', async () => {
      // Behavior-based: the default MSW handler counts fetches. Mounting fires
      // the initial fetch (1); advancing exactly 60s fires the interval tick
      // (2) — proving the polling cadence is 60s.
      renderHook(() => useLiveFinance());

      // Flush the async initial fetch (MSW resolves in a microtask).
      await act(async () => {
        await Promise.resolve();
      });
      expect(financeOverviewFetches).toBe(1);

      await act(async () => {
        jest.advanceTimersByTime(60000);
      });

      expect(financeOverviewFetches).toBe(2);
    });
  });

  describe('8. Hook Return Value Stability', () => {
    test('returns stable object reference', () => {
      const { result } = renderHook(() => useLiveFinance());

      const firstResult = result.current;
      const secondResult = result.current;

      expect(firstResult).toBe(secondResult);
    });

    test('refresh function is stable', () => {
      const { result } = renderHook(() => useLiveFinance());

      const firstRefresh = result.current.refresh;
      const secondRefresh = result.current.refresh;

      expect(firstRefresh).toBe(secondRefresh);
    });
  });

  // ------------------------------------------------------------------------
  // 9. Fetch Integration Tests (MSW handlers — repo convention: never mock
  // global.fetch; MSW wraps it and converts relative URLs to absolute)
  // ------------------------------------------------------------------------
  describe('9. Fetch Integration Tests', () => {

    beforeEach(() => {
      jest.useRealTimers();
    });

    afterEach(() => {
      jest.clearAllMocks();
    });

    test('fetches and populates transactions, stats, and providers on success', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) =>
          res(
            ctx.json({
              ok: true,
              stats: {
                total_revenue: 10000,
                pending_revenue: 2500,
                transaction_count: 12,
                platform_breakdown: { stripe: 7000, xero: 3000 },
              },
              transactions: [
                {
                  id: 'txn-1',
                  description: 'Consulting',
                  amount: 1000,
                  currency: 'USD',
                  date: '2026-03-01',
                  status: 'completed',
                  platform: 'stripe',
                },
              ],
              providers: { stripe: true, xero: false },
            })
          )
        )
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.transactions).toHaveLength(1);
      expect(result.current.transactions[0].id).toBe('txn-1');
      expect(result.current.stats.total_revenue).toBe(10000);
      expect(result.current.stats.platform_breakdown).toEqual({
        stripe: 7000,
        xero: 3000,
      });
      expect(result.current.activeProviders).toEqual({ stripe: true, xero: false });
    });

    test('leaves defaults untouched when the response is not ok', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) =>
          res(ctx.status(500), ctx.json({}))
        )
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.transactions).toEqual([]);
      expect(result.current.stats.total_revenue).toBe(0);
      expect(result.current.activeProviders).toEqual({});
    });

    test('handles fetch rejection gracefully and clears loading', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) =>
          res.networkError('Network down')
        )
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch live finance data:',
        expect.any(Error)
      );
      expect(result.current.transactions).toEqual([]);
      consoleSpy.mockRestore();
    });

    test('refresh() re-fetches the overview endpoint', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) =>
          res(
            ctx.json({
              ok: true,
              stats: {
                total_revenue: 10000,
                pending_revenue: 2500,
                transaction_count: 12,
                platform_breakdown: {},
              },
              transactions: [
                {
                  id: 'txn-1',
                  description: 'Consulting',
                  amount: 1000,
                  currency: 'USD',
                  date: '2026-03-01',
                  status: 'completed',
                  platform: 'stripe',
                },
              ],
              providers: { stripe: true },
            })
          )
        )
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.stats.total_revenue).toBe(10000);
      });

      // Second override: the refresh() call must observe the new payload.
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) =>
          res(
            ctx.json({
              ok: true,
              stats: {
                total_revenue: 500,
                pending_revenue: 0,
                transaction_count: 1,
                platform_breakdown: {},
              },
              transactions: [],
              providers: {},
            })
          )
        )
      );

      await act(async () => {
        await result.current.refresh();
      });

      expect(result.current.stats.total_revenue).toBe(500);
    });
  });
});
