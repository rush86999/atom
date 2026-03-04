/**
 * useLiveCommunication Hook Unit Tests
 *
 * Tests for useLiveCommunication hook managing live inbox polling.
 * Verifies data fetching, polling behavior, API response parsing,
 * and CRITICAL data transformation from RawUnifiedMessage to Message UI model.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveCommunication } from '../useLiveCommunication';
import { rest } from 'msw';
import { overrideHandler } from '@/tests/mocks/server';

describe('useLiveCommunication Hook', () => {
  const mockRawMessages = [
    {
      id: 'msg-1',
      content: 'Hello, how can I help you today?',
      sender: 'John Doe',
      timestamp: '2025-01-15T10:30:00Z',
      provider: 'slack',
      status: 'unread',
      metadata: {}
    },
    {
      id: 'msg-2',
      content: 'Meeting reminder at 2 PM',
      sender: 'jane@example.com',
      timestamp: '2025-01-15T11:00:00Z',
      provider: 'gmail',
      status: 'read',
      metadata: {}
    },
    {
      id: 'msg-3',
      content: 'Project update: Phase 1 complete',
      sender: 'Alice Smith',
      timestamp: '2025-01-15T12:15:00Z',
      provider: 'teams',
      status: 'unread',
      metadata: {}
    }
  ];

  const mockProviders = {
    slack: true,
    gmail: true,
    discord: false,
    teams: true,
    zoho: false,
    outlook: false
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
    test('fetches live inbox on mount', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(3);
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('sets messages state', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(3);
        expect(result.current.messages[0].content).toBe('Hello, how can I help you today?');
      });
    });

    test('sets activeProviders state', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(mockProviders);
        expect(result.current.activeProviders.slack).toBe(true);
        expect(result.current.activeProviders.discord).toBe(false);
      });
    });

    test('parses LiveInboxResponse correctly', async () => {
      const mockResponse = {
        ok: true,
        count: 3,
        messages: mockRawMessages,
        providers: mockProviders
      };

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(3);
        expect(result.current.activeProviders).toEqual(mockProviders);
      });
    });

    test('sets loading to false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 0,
              messages: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('2. Data Transformation Tests (CRITICAL)', () => {
    test('maps RawUnifiedMessage to Message UI model', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        result.current.messages.forEach(msg => {
          // Message UI model fields
          expect(msg).toHaveProperty('id');
          expect(msg).toHaveProperty('platform');
          expect(msg).toHaveProperty('from');
          expect(msg).toHaveProperty('subject');
          expect(msg).toHaveProperty('preview');
          expect(msg).toHaveProperty('content');
          expect(msg).toHaveProperty('timestamp');
          expect(msg).toHaveProperty('unread');
          expect(msg).toHaveProperty('priority');
          expect(msg).toHaveProperty('status');
        });
      });
    });

    test('maps gmail provider to email platform', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Test email',
                  sender: 'sender@example.com',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'gmail',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].platform).toBe('email');
      });
    });

    test('maps sender to from field', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Test message',
                  sender: 'John Doe',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'slack',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].from).toBe('John Doe');
      });
    });

    test('adds default subject for chat platforms (slack)', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Slack message',
                  sender: 'user1',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'slack',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].subject).toBe('Message');
      });
    });

    test('adds default subject for chat platforms (discord)', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Discord message',
                  sender: 'user1',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'discord',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].subject).toBe('Message');
      });
    });

    test('adds No Subject for non-chat platforms', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Email content',
                  sender: 'sender@example.com',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'teams',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].subject).toBe('No Subject');
      });
    });

    test('converts timestamp string to Date', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Test',
                  sender: 'user',
                  timestamp: '2025-01-15T10:30:00Z',
                  provider: 'slack',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].timestamp).toBeInstanceOf(Date);
        expect(result.current.messages[0].timestamp.toISOString()).toBe('2025-01-15T10:30:00.000Z');
      });
    });

    test('maps unread status to unread boolean', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 2,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Unread message',
                  sender: 'user1',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'slack',
                  status: 'unread',
                  metadata: {}
                },
                {
                  id: 'msg-2',
                  content: 'Read message',
                  sender: 'user2',
                  timestamp: '2025-01-15T11:00:00Z',
                  provider: 'slack',
                  status: 'read',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].unread).toBe(true);
        expect(result.current.messages[1].unread).toBe(false);
      });
    });

    test('triggers content to preview (substring 0-100)', async () => {
      const longContent = 'A'.repeat(150);

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: longContent,
                  sender: 'user',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'slack',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].preview).toHaveLength(100);
        expect(result.current.messages[0].preview).toBe('A'.repeat(100));
      });
    });

    test('preview is full content when shorter than 100 chars', async () => {
      const shortContent = 'Short message';

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: shortContent,
                  sender: 'user',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'slack',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].preview).toBe(shortContent);
      });
    });

    test('sets default priority and status', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: [
                {
                  id: 'msg-1',
                  content: 'Test',
                  sender: 'user',
                  timestamp: '2025-01-15T10:00:00Z',
                  provider: 'slack',
                  status: 'unread',
                  metadata: {}
                }
              ],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages[0].priority).toBe('normal');
        expect(result.current.messages[0].status).toBe('received');
      });
    });
  });

  describe('3. Provider Types Tests', () => {
    test('supports all provider types', async () => {
      const multiProviderMessages = [
        { ...mockRawMessages[0], provider: 'slack' as const },
        { ...mockRawMessages[1], provider: 'gmail' as const },
        { ...mockRawMessages[2], provider: 'discord' as const },
        {
          id: 'msg-4',
          content: 'Teams message',
          sender: 'user4',
          timestamp: '2025-01-15T13:00:00Z',
          provider: 'teams' as const,
          status: 'unread' as const,
          metadata: {}
        },
        {
          id: 'msg-5',
          content: 'Zoho message',
          sender: 'user5',
          timestamp: '2025-01-15T14:00:00Z',
          provider: 'zoho' as const,
          status: 'read' as const,
          metadata: {}
        },
        {
          id: 'msg-6',
          content: 'Outlook message',
          sender: 'user6@example.com',
          timestamp: '2025-01-15T15:00:00Z',
          provider: 'outlook' as const,
          status: 'unread' as const,
          metadata: {}
        }
      ];

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 6,
              messages: multiProviderMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(6);

        const platforms = result.current.messages.map(m => m.platform);
        expect(platforms).toContain('slack');
        expect(platforms).toContain('email'); // gmail maps to email
        expect(platforms).toContain('discord');
        expect(platforms).toContain('teams');
        expect(platforms).toContain('zoho');
        expect(platforms).toContain('outlook');
      });
    });
  });

  describe('4. Polling Behavior Tests', () => {
    test('sets up 30-second interval (faster than others)', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveCommunication());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward 30 seconds
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      // Should have fetched again
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });
    });

    test('cleans up interval on unmount', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveCommunication());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Unmount the hook
      unmount();

      // Fast-forward past the interval time
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      // Should not have fetched again after unmount
      expect(fetchCount).toBe(1);
    });

    test('clears interval in cleanup function', async () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 0,
              messages: [],
              providers: {}
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveCommunication());

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });

    test('polls multiple times over time', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveCommunication());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward through multiple intervals
      act(() => {
        jest.advanceTimersByTime(30000); // 1st interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });

      act(() => {
        jest.advanceTimersByTime(30000); // 2nd interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(3);
      });

      act(() => {
        jest.advanceTimersByTime(30000); // 3rd interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(4);
      });
    });
  });

  describe('5. Refresh Function Tests', () => {
    test('re-fetches inbox data when called', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

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

    test('updates messages state on refresh', async () => {
      let callCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              count: 1,
              messages: callCount === 1 ? mockRawMessages : [mockRawMessages[0]],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      // Initial fetch
      await waitFor(() => {
        expect(result.current.messages).toHaveLength(3);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(1);
      });
    });
  });

  describe('6. Loading States Tests', () => {
    test('initial isLoading is true', () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 0,
              messages: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      expect(result.current.isLoading).toBe(true);
    });

    test('becomes false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('handles loading state on error', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('7. Error Handling Tests', () => {
    test('handles fetch errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch live inbox:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });

    test('console.error called with error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          throw new Error('Network error');
        })
      );

      renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to fetch live inbox:',
          expect.any(Error)
        );
      });
      consoleSpy.mockRestore();
    });

    test('handles non-OK response', async () => {
      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.messages).toEqual([]);
      });
    });
  });

  describe('8. Provider Tracking Tests', () => {
    test('tracks active providers correctly', async () => {
      const customProviders = {
        slack: true,
        gmail: false,
        discord: true,
        teams: true,
        zoho: true,
        outlook: false
      };

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: customProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(customProviders);
        expect(Object.keys(result.current.activeProviders)).toHaveLength(6);
      });
    });

    test('updates providers on refresh', async () => {
      let callCount = 0;

      overrideHandler(
        rest.get('/api/atom/communication/live/inbox', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              count: 3,
              messages: mockRawMessages,
              providers: callCount === 1
                ? { slack: true, gmail: false, discord: false, teams: false, zoho: false, outlook: false }
                : { slack: true, gmail: true, discord: true, teams: true, zoho: true, outlook: true }
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveCommunication());

      // Initial state
      await waitFor(() => {
        expect(result.current.activeProviders.gmail).toBe(false);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      // Updated state
      await waitFor(() => {
        expect(result.current.activeProviders.gmail).toBe(true);
        expect(result.current.activeProviders.discord).toBe(true);
      });
    });
  });
});
