/**
 * useLiveSupport Hook Unit Tests
 *
 * The real useLiveSupport hook fetches support tickets from
 * `http://localhost:8000/api/atom/communication/live/support/tickets` on mount
 * and returns { tickets, isLoading, error, refresh }.
 *
 * It has NO embedded mock data and NO artificial delay — earlier tests that
 * advanced fake timers by 500ms and expected hardcoded tickets (TKT-991, etc.)
 * were testing a fabricated contract and have been rewritten against the real
 * fetch-based behavior. The mount fetch consumes the first queued mock.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveSupport, Ticket } from '../useLiveSupport';

const API_URL =
  '/api/atom/communication/live/support/tickets';

const mockTickets: Ticket[] = [
  {
    id: 'TKT-991',
    subject: 'Cloud Sync Failed for Org #55',
    status: 'Open',
    priority: 'High',
    platform: 'zendesk',
    customer: 'Acme Corp',
  },
  {
    id: 'FR-22',
    subject: 'Billing Inquiry: Overcharged',
    status: 'Pending',
    priority: 'Medium',
    platform: 'freshdesk',
    customer: 'Bob Smith',
  },
  {
    id: 'IC-451',
    subject: 'How do I add a team member?',
    status: 'Closed',
    priority: 'Low',
    platform: 'intercom',
    customer: 'Sarah Lane',
  },
];

const ticketsResponse = (tickets: Ticket[]) => ({
  ok: true,
  json: async () => ({ tickets }),
});

describe('useLiveSupport Hook', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    global.mockFetch = global.fetch;
    jest.clearAllMocks();
  });

  describe('1. Data Fetching Tests', () => {
    test('fetches support tickets on mount', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      expect(global.fetch).toHaveBeenCalledWith(API_URL, expect.any(Object));

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('sets tickets state from data.tickets in the API response', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
        expect(result.current.tickets[0]).toMatchObject({
          id: 'TKT-991',
          subject: 'Cloud Sync Failed for Org #55',
          status: 'Open',
          priority: 'High',
          platform: 'zendesk',
          customer: 'Acme Corp',
        });
      });
    });

    test('handles a raw array response', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => [mockTickets[0]],
      });

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(1);
        expect(result.current.tickets[0].id).toBe('TKT-991');
      });
    });

    test('sets isLoading to false after fetch completes', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('2. Data Structure Tests', () => {
    test('passes through Ticket interface fields', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        const tickets: Ticket[] = result.current.tickets;
        tickets.forEach((ticket) => {
          expect(ticket).toHaveProperty('id');
          expect(ticket).toHaveProperty('subject');
          expect(ticket).toHaveProperty('status');
          expect(ticket).toHaveProperty('priority');
          expect(ticket).toHaveProperty('platform');
          expect(ticket).toHaveProperty('customer');
          expect(typeof ticket.id).toBe('string');
          expect(typeof ticket.subject).toBe('string');
          expect(typeof ticket.customer).toBe('string');
        });
      });
    });

    test('supports platform types: zendesk, freshdesk, intercom', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        const platforms = result.current.tickets.map((t) => t.platform);
        expect(platforms).toContain('zendesk');
        expect(platforms).toContain('freshdesk');
        expect(platforms).toContain('intercom');
      });
    });

    test('supports priority levels: High, Medium, Low', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        const priorities = result.current.tickets.map((t) => t.priority);
        expect(priorities).toContain('High');
        expect(priorities).toContain('Medium');
        expect(priorities).toContain('Low');
      });
    });

    test('supports status types: Open, Pending, Closed', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        const statuses = result.current.tickets.map((t) => t.status);
        expect(statuses).toContain('Open');
        expect(statuses).toContain('Pending');
        expect(statuses).toContain('Closed');
      });
    });
  });

  describe('3. Refresh Function Tests', () => {
    test('re-fetches tickets when called', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(ticketsResponse(mockTickets))
        .mockResolvedValueOnce(ticketsResponse(mockTickets));

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });

      act(() => {
        result.current.refresh();
      });

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });

      // mount fetch + refresh fetch
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    test('updates tickets state on refresh', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(ticketsResponse(mockTickets))
        .mockResolvedValueOnce(ticketsResponse([mockTickets[0]]));

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });

      act(() => {
        result.current.refresh();
      });

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(1);
      });
    });

    test('refresh can be called multiple times', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(ticketsResponse(mockTickets))
        .mockResolvedValue(ticketsResponse(mockTickets));

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });

      for (let i = 0; i < 3; i++) {
        act(() => {
          result.current.refresh();
        });
      }

      await waitFor(() => {
        expect(result.current.tickets).toHaveLength(3);
      });
    });
  });

  describe('4. Loading States Tests', () => {
    test('isLoading starts as true while the initial fetch is pending', () => {
      // A never-resolving fetch keeps isLoading true deterministically.
      (global.mockFetch as jest.Mock).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useLiveSupport());

      expect(result.current.isLoading).toBe(true);
    });

    test('isLoading becomes false after fetch completes', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('isLoading is true during a refresh', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce(ticketsResponse(mockTickets));

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // A never-resolving fetch keeps isLoading true through the refresh.
      (global.mockFetch as jest.Mock).mockReturnValue(new Promise(() => {}));

      act(() => {
        result.current.refresh();
      });

      expect(result.current.isLoading).toBe(true);
    });
  });

  describe('5. Error Handling Tests', () => {
    test('sets an HTTP error and clears tickets on a non-ok response', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}),
      });

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.error).toBe('HTTP 500');
        expect(result.current.tickets).toEqual([]);
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('sets error and clears tickets on a network failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network error')
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
        expect(result.current.tickets).toEqual([]);
        expect(result.current.isLoading).toBe(false);
      });

      consoleSpy.mockRestore();
    });

    test('does not throw on fetch rejection', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network error')
      );

      expect(() => renderHook(() => useLiveSupport())).not.toThrow();

      consoleSpy.mockRestore();
    });
  });

  describe('6. Multiple Hook Instances', () => {
    test('multiple hook instances work independently', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue(
        ticketsResponse(mockTickets)
      );

      const { result: result1 } = renderHook(() => useLiveSupport());
      const { result: result2 } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result1.current.tickets).toHaveLength(3);
        expect(result2.current.tickets).toHaveLength(3);
      });

      // Refresh the first instance only; the shared mock resolves for both but
      // each hook tracks its own state independently.
      act(() => {
        result1.current.refresh();
      });

      await waitFor(() => {
        expect(result1.current.tickets).toHaveLength(3);
        expect(result2.current.tickets).toHaveLength(3);
      });
    });
  });

  describe('7. Data Content', () => {
    test('passes API data through to tickets', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValueOnce(
        ticketsResponse(mockTickets)
      );

      const { result } = renderHook(() => useLiveSupport());

      await waitFor(() => {
        expect(result.current.tickets).toEqual(mockTickets);
      });
    });
  });
});
