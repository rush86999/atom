/**
 * useLiveFinance Hook Unit Tests
 *
 * Tests for useLiveFinance hook managing live finance data polling.
 * Verifies data fetching, polling behavior, API response parsing,
 * data structure validation, and provider tracking.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveFinance } from '../useLiveFinance';
import { rest } from 'msw';
import { overrideHandler } from '@/tests/mocks/server';

describe('useLiveFinance Hook', () => {
  const mockTransactions = [
    {
      id: 'txn-1',
      description: 'Payment for services',
      amount: 1500.00,
      currency: 'USD',
      date: '2025-01-15',
      status: 'completed',
      platform: 'stripe',
      customer_name: 'Acme Corp',
      url: 'https://stripe.com/payments/txn-1'
    },
    {
      id: 'txn-2',
      description: 'Invoice payment',
      amount: 3500.00,
      currency: 'USD',
      date: '2025-01-16',
      status: 'pending',
      platform: 'xero',
      customer_name: 'Tech Solutions Inc',
      url: 'https://xero.com/invoices/txn-2'
    }
  ];

  const mockStats = {
    total_revenue: 5000.00,
    pending_revenue: 3500.00,
    transaction_count: 2,
    platform_breakdown: {
      stripe: 1500.00,
      xero: 3500.00
    }
  };

  const mockProviders = {
    stripe: true,
    xero: true,
    quickbooks: false,
    zoho: false,
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
    test('fetches finance data on mount', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.transactions).toEqual(mockTransactions);
      });
    });

    test('sets transactions state from API response', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.transactions).toHaveLength(2);
        expect(result.current.transactions[0].description).toBe('Payment for services');
      });
    });

    test('sets stats state correctly', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.stats).toEqual(mockStats);
        expect(result.current.stats.total_revenue).toBe(5000.00);
        expect(result.current.stats.pending_revenue).toBe(3500.00);
        expect(result.current.stats.transaction_count).toBe(2);
      });
    });

    test('sets activeProviders state', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(mockProviders);
        expect(result.current.activeProviders.stripe).toBe(true);
        expect(result.current.activeProviders.quickbooks).toBe(false);
      });
    });

    test('parses LiveFinanceResponse correctly', async () => {
      const mockResponse = {
        ok: true,
        stats: mockStats,
        transactions: mockTransactions,
        providers: mockProviders
      };

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.transactions).toEqual(mockResponse.transactions);
        expect(result.current.stats).toEqual(mockResponse.stats);
        expect(result.current.activeProviders).toEqual(mockResponse.providers);
      });
    });

    test('sets loading to false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('2. Data Structure Tests', () => {
    test('UnifiedTransaction interface fields', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        result.current.transactions.forEach(txn => {
          expect(txn).toHaveProperty('id');
          expect(txn).toHaveProperty('description');
          expect(txn).toHaveProperty('amount');
          expect(txn).toHaveProperty('currency');
          expect(txn).toHaveProperty('date');
          expect(txn).toHaveProperty('status');
          expect(txn).toHaveProperty('platform');
          expect(txn).toHaveProperty('customer_name');
          expect(txn).toHaveProperty('url');

          expect(typeof txn.id).toBe('string');
          expect(typeof txn.description).toBe('string');
          expect(typeof txn.amount).toBe('number');
          expect(typeof txn.currency).toBe('string');
          expect(typeof txn.date).toBe('string');
          expect(typeof txn.status).toBe('string');
          expect(typeof txn.platform).toBe('string');
        });
      });
    });

    test('platform types: stripe, xero, quickbooks, zoho, dynamics', async () => {
      const multiPlatformTransactions = [
        { ...mockTransactions[0], platform: 'stripe' },
        { ...mockTransactions[1], platform: 'xero' },
        {
          id: 'txn-3',
          description: 'QuickBooks payment',
          amount: 2000.00,
          currency: 'USD',
          date: '2025-01-17',
          status: 'completed',
          platform: 'quickbooks',
          customer_name: 'Company C',
          url: 'https://quickbooks.com/txn-3'
        },
        {
          id: 'txn-4',
          description: 'Zoho payment',
          amount: 1800.00,
          currency: 'USD',
          date: '2025-01-18',
          status: 'completed',
          platform: 'zoho',
          customer_name: 'Company D',
          url: 'https://zoho.com/txn-4'
        },
        {
          id: 'txn-5',
          description: 'Dynamics payment',
          amount: 2200.00,
          currency: 'USD',
          date: '2025-01-19',
          status: 'pending',
          platform: 'dynamics',
          customer_name: 'Company E',
          url: 'https://dynamics.com/txn-5'
        }
      ];

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: multiPlatformTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        const platforms = result.current.transactions.map(t => t.platform);
        expect(platforms).toContain('stripe');
        expect(platforms).toContain('xero');
        expect(platforms).toContain('quickbooks');
        expect(platforms).toContain('zoho');
        expect(platforms).toContain('dynamics');
      });
    });

    test('FinanceStats structure', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.stats).toHaveProperty('total_revenue');
        expect(result.current.stats).toHaveProperty('pending_revenue');
        expect(result.current.stats).toHaveProperty('transaction_count');
        expect(result.current.stats).toHaveProperty('platform_breakdown');

        expect(typeof result.current.stats.total_revenue).toBe('number');
        expect(typeof result.current.stats.pending_revenue).toBe('number');
        expect(typeof result.current.stats.transaction_count).toBe('number');
        expect(typeof result.current.stats.platform_breakdown).toBe('object');
      });
    });
  });

  describe('3. Polling Behavior Tests', () => {
    test('sets up 60-second interval', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveFinance());

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
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveFinance());

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
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: [],
              providers: {}
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveFinance());

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });

    test('polls multiple times over time', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveFinance());

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
    test('re-fetches finance data when called', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

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
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              stats: {
                total_revenue: callCount * 1000,
                pending_revenue: callCount * 500,
                transaction_count: callCount,
                platform_breakdown: { stripe: callCount * 1000 }
              },
              transactions: callCount === 1 ? mockTransactions : [],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      // Initial fetch
      await waitFor(() => {
        expect(result.current.stats.total_revenue).toBe(1000);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      await waitFor(() => {
        expect(result.current.stats.total_revenue).toBe(2000);
        expect(result.current.transactions).toEqual([]);
      });
    });
  });

  describe('5. Loading States Tests', () => {
    test('initial isLoading is true', () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.isLoading).toBe(true);
    });

    test('becomes false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('handles loading state on error', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveFinance());

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
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch live finance data:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });

    test('console.error called with error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          throw new Error('Network error');
        })
      );

      renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to fetch live finance data:',
          expect.any(Error)
        );
      });
      consoleSpy.mockRestore();
    });

    test('handles non-OK response', async () => {
      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.transactions).toEqual([]);
      });
    });
  });

  describe('7. Provider Tracking Tests', () => {
    test('tracks active providers correctly', async () => {
      const customProviders = {
        stripe: true,
        xero: true,
        quickbooks: true,
        zoho: false,
        dynamics: false
      };

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: customProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(customProviders);
        expect(Object.keys(result.current.activeProviders)).toHaveLength(5);
      });
    });

    test('updates providers on refresh', async () => {
      let callCount = 0;

      overrideHandler(
        rest.get('/api/atom/finance/live/overview', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              transactions: mockTransactions,
              providers: callCount === 1
                ? { stripe: true, xero: false, quickbooks: false, zoho: false, dynamics: false }
                : { stripe: true, xero: true, quickbooks: true, zoho: true, dynamics: true }
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveFinance());

      // Initial state
      await waitFor(() => {
        expect(result.current.activeProviders.xero).toBe(false);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      // Updated state
      await waitFor(() => {
        expect(result.current.activeProviders.xero).toBe(true);
        expect(result.current.activeProviders.quickbooks).toBe(true);
      });
    });
  });
});
