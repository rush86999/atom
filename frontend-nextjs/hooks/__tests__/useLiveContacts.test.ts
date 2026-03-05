/**
 * useLiveContacts Hook Unit Tests
 *
 * Tests for useLiveContacts hook managing live contact polling.
 * Verifies data fetching, polling behavior, error handling,
 * and cleanup on unmount.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveContacts } from '../useLiveContacts';
import { rest } from 'msw';
import { overrideHandler } from '@/tests/mocks/server';

describe('useLiveContacts Hook', () => {
  const mockContacts = [
    {
      id: 'contact-1',
      name: 'John Doe',
      provider: 'slack',
      status: 'online',
      avatar: 'https://example.com/avatar1.jpg',
    },
    {
      id: 'contact-2',
      name: 'Jane Smith',
      provider: 'teams',
      status: 'offline',
      avatar: 'https://example.com/avatar2.jpg',
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('1. Data Fetching Tests', () => {
    test('fetches contacts on mount', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              contacts: mockContacts,
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      await waitFor(() => {
        expect(result.current.contacts).toEqual(mockContacts);
      });
    });

    test('sets contacts state from API response', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              contacts: mockContacts,
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      await waitFor(() => {
        expect(result.current.contacts).toHaveLength(2);
        expect(result.current.contacts[0].name).toBe('John Doe');
      });
    });

    test('sets loading to false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              contacts: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });

    test('parses data.ok and data.contacts correctly', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              contacts: mockContacts,
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      await waitFor(() => {
        expect(result.current.contacts).toEqual(mockContacts);
      });
    });

    test('handles when data.ok is false', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: false,
              contacts: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      await waitFor(() => {
        expect(result.current.contacts).toEqual([]);
      });
    });
  });

  describe('2. Polling Behavior Tests', () => {
    test('sets up 60-second interval', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              contacts: mockContacts,
            })
          );
        })
      );

      renderHook(() => useLiveContacts());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward 60 seconds
      jest.advanceTimersByTime(60000);

      // Should have fetched again
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });
    });

    test('cleans up interval on unmount', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              contacts: mockContacts,
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveContacts());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Unmount the hook
      unmount();

      // Fast-forward past the interval time
      jest.advanceTimersByTime(60000);

      // Should not have fetched again after unmount
      expect(fetchCount).toBe(1);
    });

    test('clears interval in cleanup function', async () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              contacts: [],
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveContacts());

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });
  });

  describe('3. Error Handling Tests', () => {
    test('handles fetch errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch contacts:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });

    test('sets loading to false on error', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      expect(result.current.loading).toBe(true);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
    });

    test('console.error called with error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const mockError = new Error('Network error');

      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          throw mockError;
        })
      );

      renderHook(() => useLiveContacts());

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to fetch contacts:',
          expect.any(Error)
        );
      });
      consoleSpy.mockRestore();
    });
  });

  describe('4. Initial State Tests', () => {
    test('loading starts as true', () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              contacts: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      expect(result.current.loading).toBe(true);
    });

    test('contacts starts empty', () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              contacts: [],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      expect(result.current.contacts).toEqual([]);
    });
  });

  describe('5. Multiple Polls Tests', () => {
    test('polls multiple times over time', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              contacts: mockContacts,
            })
          );
        })
      );

      renderHook(() => useLiveContacts());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward through multiple intervals
      jest.advanceTimersByTime(60000); // 1st interval
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });

      jest.advanceTimersByTime(60000); // 2nd interval
      await waitFor(() => {
        expect(fetchCount).toBe(3);
      });

      jest.advanceTimersByTime(60000); // 3rd interval
      await waitFor(() => {
        expect(fetchCount).toBe(4);
      });
    });

    test('updates contacts on each poll', async () => {
      let pollIndex = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/contacts/recent', (req, res, ctx) => {
          pollIndex++;
          return res(
            ctx.json({
              ok: true,
              contacts: [
                {
                  id: `contact-${pollIndex}`,
                  name: `Contact ${pollIndex}`,
                  provider: 'slack',
                  status: 'online',
                  avatar: `https://example.com/avatar${pollIndex}.jpg`,
                },
              ],
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveContacts());

      // Initial poll
      await waitFor(() => {
        expect(result.current.contacts[0].id).toBe('contact-1');
      });

      // After 60 seconds
      jest.advanceTimersByTime(60000);
      await waitFor(() => {
        expect(result.current.contacts[0].id).toBe('contact-2');
      });

      // After another 60 seconds
      jest.advanceTimersByTime(60000);
      await waitFor(() => {
        expect(result.current.contacts[0].id).toBe('contact-3');
      });
    });
  });
});
