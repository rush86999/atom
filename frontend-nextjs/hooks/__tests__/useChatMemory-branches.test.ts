/**
 * useChatMemory Hook — supplemental branch coverage (failure branches).
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatMemory } from '../useChatMemory';

describe('useChatMemory Hook (failure branches)', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    global.mockFetch = global.fetch;
    jest.clearAllMocks();
  });

  const render = (overrides: any = {}) =>
    renderHook(() =>
      useChatMemory({
        userId: 'user-1',
        sessionId: 'session-1',
        enableMemory: true,
        ...overrides,
      })
    );

  test('storeMemory rejects non-success status', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm1' }) }) // stats
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'failure', message: 'storage full' }) }); // store
    const { result } = render();
    await act(async () => {
      await result.current.storeMemory({
        userId: 'user-1',
        sessionId: 'session-1',
        role: 'user',
        content: 'hi',
        metadata: { messageType: 'text', importance: 0.5, accessCount: 0, lastAccessed: new Date() },
      });
    });
    await waitFor(() => {
      expect(result.current.error).toBe('storage full');
    });
  });

  test('storeMemory tolerates a non-Error rejection', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm1' }) }) // stats
      .mockResolvedValueOnce({ ok: false, statusText: 'Boom' });
    const { result } = render();
    await act(async () => {
      await result.current.storeMemory({
        userId: 'user-1',
        sessionId: 'session-1',
        role: 'user',
        content: 'x',
        metadata: { messageType: 'text', importance: 0.5, accessCount: 0, lastAccessed: new Date() },
      });
    });
    await waitFor(() => {
      expect(result.current.error).toBe('Failed to store memory: Boom');
    });
  });

  test('getMemoryContext rejects non-success status', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm1' }) }) // stats
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'error', message: 'no context' }) }); // context
    const { result } = render();
    let ctx: any;
    await act(async () => {
      ctx = await result.current.getMemoryContext('hello');
    });
    expect(ctx.conversationSummary).toBe('Memory context unavailable');
    expect(ctx.relevanceScore).toBe(0);
    await waitFor(() => {
      expect(result.current.error).toBe('no context');
    });
  });

  test('getMemoryContext tolerates network failure', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm1' }) }) // stats
      .mockRejectedValueOnce(new Error('network down')); // context
    const { result } = render();
    let ctx: any;
    await act(async () => {
      ctx = await result.current.getMemoryContext('hello');
    });
    expect(ctx.shortTermMemories).toEqual([]);
    expect(ctx.conversationSummary).toBe('Memory context unavailable');
  });

  test('clearSessionMemory rejects non-success status', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm1' }) }) // stats
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'error', message: 'cannot clear' }) }); // clear
    const { result } = render();
    await act(async () => {
      await result.current.clearSessionMemory();
    });
    await waitFor(() => {
      expect(result.current.error).toBe('cannot clear');
    });
  });

  test('clearSessionMemory tolerates network failure', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm1' }) }) // stats
      .mockRejectedValueOnce(new Error('down')); // clear
    const { result } = render();
    await act(async () => {
      await result.current.clearSessionMemory();
    });
    await waitFor(() => {
      expect(result.current.error).toBe('down');
    });
  });

  test('refreshMemoryStats rejects non-success status', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'error', message: 'stats broken' }) }); // stats
    const { result } = render();
    await waitFor(() => {
      expect(result.current.memoryStats).toBeNull();
    });
    await act(async () => {
      await result.current.refreshMemoryStats();
    });
  });

  test('refreshMemoryStats tolerates network failure', async () => {
    (global.mockFetch as jest.Mock).mockRejectedValueOnce(new Error('down'));
    const { result } = render();
    await act(async () => {
      await result.current.refreshMemoryStats();
    });
  });

  test('autoStoreMessage stores when enabled', async () => {
    (global.mockFetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm1' }) }) // stats
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm2' }) }) // store
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'success', memory_id: 'm2' }) }); // stats refresh
    const { result } = render({ autoStoreMessages: true });
    await act(async () => {
      await (result.current as any).autoStoreMessage('user', 'remember this');
    });
    await waitFor(() => {
      expect(result.current.memories[0].content).toBe('remember this');
    });
    const storeBody = JSON.parse((global.mockFetch as jest.Mock).mock.calls[1][1].body);
    expect(storeBody.metadata.messageType).toBe('text');
    expect(storeBody.metadata.importance).toBe(0.5);
  });
});
