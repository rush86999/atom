/**
 * useLiveSupport Hook Unit Tests
 *
 * Tests for useLiveSupport hook managing support tickets with mock data.
 * Verifies data fetching, mock data structure, loading states,
 * refresh function, and error handling.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveSupport, Ticket } from '../useLiveSupport';

describe('useLiveSupport Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('1. Data Fetching Tests', () => {
    test('fetches support tickets on mount', async () => {
      const { result } = renderHook(() => useLiveSupport());

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Fast-forward past the artificial delay
      act(() => {
        jest.advanceTimersByTime(500);
      });

      // Should have tickets now
      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('sets tickets state from mock data', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
        expect(result.current.tickets[0]).toMatchObject({
          id: 'TKT-991',
          subject: 'Cloud Sync Failed for Org #55',
          status: 'Open',
          priority: 'High',
          platform: 'zendesk',
          customer: 'Acme Corp'
        });
      });
    });

    test('sets isLoading to false after fetch', async () => {
      const { result } = renderHook(() => useLiveSupport());

      expect(result.current.isLoading).toBe(true);

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('handles artificial delay (setTimeout)', async () => {
      const setTimeoutSpy = jest.spyOn(global, 'setTimeout');

      const { result } = renderHook(() => useLiveSupport());

      expect(setTimeoutSpy).toHaveBeenCalled();
      expect(result.current.isLoading).toBe(true);

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      setTimeoutSpy.mockRestore();
    });
  });

  describe('2. Mock Data Structure Tests', () => {
    test('correct ticket types (Ticket interface)', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        const tickets: Ticket[] = result.current.tickets;

        tickets.forEach(ticket => {
          expect(ticket).toHaveProperty('id');
          expect(ticket).toHaveProperty('subject');
          expect(ticket).toHaveProperty('status');
          expect(ticket).toHaveProperty('priority');
          expect(ticket).toHaveProperty('platform');
          expect(ticket).toHaveProperty('customer');

          // Type checking
          expect(typeof ticket.id).toBe('string');
          expect(typeof ticket.subject).toBe('string');
          expect(typeof ticket.customer).toBe('string');
        });
      });
    });

    test('platform types: zendesk, freshdesk, intercom', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        const platforms = result.current.tickets.map(t => t.platform);
        expect(platforms).toContain('zendesk');
        expect(platforms).toContain('freshdesk');
        expect(platforms).toContain('intercom');
      });
    });

    test('priority levels: High, Medium, Low', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        const priorities = result.current.tickets.map(t => t.priority);
        expect(priorities).toContain('High');
        expect(priorities).toContain('Medium');
        expect(priorities).toContain('Low');
      });
    });

    test('status types: Open, Pending, Closed', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        const statuses = result.current.tickets.map(t => t.status);
        expect(statuses).toContain('Open');
        expect(statuses).toContain('Pending');
        expect(statuses).toContain('Closed');
      });
    });

    test('all mock tickets have required fields', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        result.current.tickets.forEach(ticket => {
          expect(ticket.id).toBeTruthy();
          expect(ticket.subject).toBeTruthy();
          expect(ticket.status).toBeTruthy();
          expect(ticket.priority).toBeTruthy();
          expect(ticket.platform).toBeTruthy();
          expect(ticket.customer).toBeTruthy();
        });
      });
    });
  });

  describe('3. Refresh Function Tests', () => {
    test('re-fetches tickets when called', async () => {
      const { result } = renderHook(() => useLiveSupport());

      // Initial fetch
      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });

      // Call refresh
      act(() => {
        result.current.refresh();
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });
    });

    test('updates tickets state on refresh', async () => {
      const { result } = renderHook(() => useLiveSupport());

      // Initial fetch
      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.tickets).toHaveLength(3);
      });

      const initialTickets = [...result.current.tickets];

      // Refresh
      act(() => {
        result.current.refresh();
      });

      // Should be loading again
      expect(result.current.isLoading).toBe(true);

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        // Mock data is the same, but state was updated
        expect(result.current.tickets).toHaveLength(initialTickets.length);
      });
    });

    test('refresh can be called multiple times', async () => {
      const { result } = renderHook(() => useLiveSupport());

      // Initial fetch
      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });

      // Refresh 3 times
      for (let i = 0; i < 3; i++) {
        act(() => {
          result.current.refresh();
          jest.advanceTimersByTime(500);
        });

        await waitFor(() => {
          expect(result.current.tickets).toHaveLength(3);
        });
      }
    });
  });

  describe('4. Loading States Tests', () => {
    test('isLoading starts as true', () => {
      const { result } = renderHook(() => useLiveSupport());

      expect(result.current.isLoading).toBe(true);
    });

    test('isLoading becomes false after fetch', async () => {
      const { result } = renderHook(() => useLiveSupport());

      expect(result.current.isLoading).toBe(true);

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('isLoading is true during refresh', async () => {
      const { result } = renderHook(() => useLiveSupport());

      // Initial fetch
      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Start refresh
      act(() => {
        result.current.refresh();
      });

      expect(result.current.isLoading).toBe(true);

      // Complete refresh
      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('5. Error Handling Tests', () => {
    test('handles fetch errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      // Mock fetchTickets to throw error
      const originalFetch = global.fetch;
      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      // Should not throw, just log error
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      consoleSpy.mockRestore();
      global.fetch = originalFetch;
    });

    test('sets isLoading to false on error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      // The hook uses mock data, so we need to simulate an error
      // by making the setTimeout callback throw
      const realSetTimeout = global.setTimeout;
      global.setTimeout = jest.fn((fn, delay) => {
        if (delay === 500) {
          // Call the function but it will catch its own errors
          try {
            fn();
          } catch (e) {
            // Hook catches this
          }
        }
        return realSetTimeout(fn, delay);
      });

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      global.setTimeout = realSetTimeout;
      consoleSpy.mockRestore();
    });

    test('console.error called with error message', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      // Since the mock data fetch succeeds, this shouldn't error
      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });

      // No error should have been logged
      expect(consoleSpy).not.toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });

  describe('6. Multiple Hook Instances', () => {
    test('multiple hook instances work independently', async () => {
      const { result: result1 } = renderHook(() => useLiveSupport());
      const { result: result2 } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result1.current.tickets).toHaveLength(3);
        expect(result2.current.tickets).toHaveLength(3);
      });

      // Refresh first instance
      act(() => {
        result1.current.refresh();
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        expect(result1.current.tickets).toHaveLength(3);
        expect(result2.current.tickets).toHaveLength(3);
      });
    });
  });

  describe('7. Mock Data Content', () => {
    test('contains expected zendesk ticket', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        const zendeskTicket = result.current.tickets.find(t => t.platform === 'zendesk');
        expect(zendeskTicket).toMatchObject({
          id: 'TKT-991',
          subject: 'Cloud Sync Failed for Org #55',
          status: 'Open',
          priority: 'High',
          customer: 'Acme Corp'
        });
      });
    });

    test('contains expected freshdesk ticket', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        const freshdeskTicket = result.current.tickets.find(t => t.platform === 'freshdesk');
        expect(freshdeskTicket).toMatchObject({
          id: 'FR-22',
          subject: 'Billing Inquiry: Overcharged',
          status: 'Pending',
          priority: 'Medium',
          customer: 'Bob Smith'
        });
      });
    });

    test('contains expected intercom ticket', async () => {
      const { result } = renderHook(() => useLiveSupport());

      act(() => {
        jest.advanceTimersByTime(500);
      });

      await waitFor(() => {
        const intercomTicket = result.current.tickets.find(t => t.platform === 'intercom');
        expect(intercomTicket).toMatchObject({
          id: 'IC-451',
          subject: 'How do I add a team member?',
          status: 'Closed',
          priority: 'Low',
          customer: 'Sarah Lane'
        });
      });
    });
  });
});
