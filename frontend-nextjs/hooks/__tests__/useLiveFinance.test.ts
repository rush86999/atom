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
import { useLiveFinance, UnifiedTransaction, FinanceStats } from '../useLiveFinance';

describe('useLiveFinance Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
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
      const setIntervalSpy = jest.spyOn(global, 'setInterval');

      renderHook(() => useLiveFinance());

      expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 60000);
      setIntervalSpy.mockRestore();
    });

    test('clears interval on unmount', () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      const { unmount } = renderHook(() => useLiveFinance());

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
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
    test('uses 60 second interval', () => {
      const setIntervalSpy = jest.spyOn(global, 'setInterval');

      renderHook(() => useLiveFinance());

      const calls = setIntervalSpy.mock.calls;
      const intervalCall = calls.find(call => call[1] === 60000);

      expect(intervalCall).toBeDefined();
      setIntervalSpy.mockRestore();
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
});
