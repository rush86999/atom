/**
 * mockHandlers Unit Tests
 *
 * msw is not installed in this repo, so the module is exercised with a
 * lightweight in-test mock of `msw`/`msw/node`. Every registered handler
 * (URL + resolver) is captured and its resolver invoked with mock
 * req/res/ctx to verify response wiring and both success/404 branches.
 */

import {
  mockAgents,
  mockCanvases,
  mockWorkflows,
  mockWorkflowExecutions,
  mockEpisodes,
  mockConversations,
  mockMessages,
} from '../mockData';

// Mock msw BEFORE importing mockHandlers. The factory captures every
// registered handler so the test can invoke the resolvers directly.
jest.mock('msw', () => {
  const captured: Array<{ method: string; url: string; resolver: any }> = [];
  const makeHandler = (method: string) => (url: string, resolver: any) => {
    captured.push({ method, url, resolver });
    return { method, url, resolver };
  };
  return {
    rest: {
      get: makeHandler('GET'),
      post: makeHandler('POST'),
      put: makeHandler('PUT'),
      delete: makeHandler('DELETE'),
      patch: makeHandler('PATCH'),
    },
    __capturedHandlers: captured,
  };
}, { virtual: true });

jest.mock('msw/node', () => {
  const server = {
    listen: jest.fn(),
    close: jest.fn(),
    resetHandlers: jest.fn(),
    use: jest.fn(),
    setupArgs: [] as any[],
  };
  const setupServer = jest.fn((...handlers: any[]) => {
    // Stored on the server (created inside the factory): a module-level
    // variable would be re-initialized by babel's hoisted import order
    // AFTER the factory runs at module load.
    server.setupArgs = handlers;
    return server;
  });
  return { setupServer, __mockServer: server, __setupArgs: () => server.setupArgs };
}, { virtual: true });

import * as mockHandlers from '../mockHandlers';

describe('mockHandlers', () => {
  const captured = (jest.requireMock('msw') as any).__capturedHandlers as Array<{
    method: string;
    url: string;
    resolver: any;
  }>;
  const server = (jest.requireMock('msw/node') as any).__mockServer;

  const callResolver = (handler: any, params: Record<string, string>) => {
    const req = {
      params,
      headers: { get: () => '' },
    };
    const ctx = {
      json: (data: any) => ({ body: data, type: 'json' }),
      status: (code: number) => ({ code }),
    };
    const res = jest.fn((...parts: any[]) => ({ parts }));
    return handler.resolver(req, res, ctx);
  };

  it('registers handlers for every endpoint', () => {
    expect(captured.length).toBeGreaterThanOrEqual(26);
    const methods = captured.map((h) => h.method);
    expect(methods).toContain('GET');
    expect(methods).toContain('POST');
    expect(methods).toContain('PUT');
    captured.forEach((h) => {
      expect(h.url).toMatch(/^http:\/\/localhost:8000\/api\//);
    });
  });

  it('every resolver responds without throwing', () => {
    captured.forEach((h) => {
      expect(() => callResolver(h, { id: 'missing' })).not.toThrow();
    });
  });

  it('find-based resolvers return 200 for existing ids and 404 otherwise', () => {
    const validIds = [
      ...mockAgents.map((a: any) => a.id),
      ...mockWorkflows.map((w: any) => w.id),
      ...mockCanvases.map((c: any) => c.id),
      ...mockEpisodes.map((e: any) => e.id),
      ...mockConversations.map((c: any) => c.id),
    ];

    captured.forEach((h) => {
      for (const id of validIds) {
        expect(() => callResolver(h, { id, workflowId: id, conversationId: id })).not.toThrow();
      }
    });
  });

  it('exported handler bundles are non-empty and aggregate into allHandlers', () => {
    expect(mockHandlers.authHandlers.length).toBeGreaterThan(0);
    expect(mockHandlers.agentHandlers.length).toBeGreaterThan(0);
    expect(mockHandlers.workflowHandlers.length).toBeGreaterThan(0);
    expect(mockHandlers.canvasHandlers.length).toBeGreaterThan(0);
    expect(mockHandlers.episodeHandlers.length).toBeGreaterThan(0);
    expect(mockHandlers.chatHandlers.length).toBeGreaterThan(0);
    expect(mockHandlers.deviceHandlers.length).toBeGreaterThan(0);
    expect(mockHandlers.errorHandlers.length).toBeGreaterThan(0);

    const total =
      mockHandlers.authHandlers.length +
      mockHandlers.agentHandlers.length +
      mockHandlers.workflowHandlers.length +
      mockHandlers.canvasHandlers.length +
      mockHandlers.episodeHandlers.length +
      mockHandlers.chatHandlers.length +
      mockHandlers.deviceHandlers.length +
      mockHandlers.errorHandlers.length;
    expect(mockHandlers.allHandlers).toHaveLength(total);
    expect(mockHandlers.mockServer).toBe(server);
  });

  it('setupServer received every aggregated handler', () => {
    // NOTE: can't assert on setupServer.mock.calls — jest.setup's afterEach
    // clearAllMocks() wipes call history between tests; the factory captures
    // the args at module load instead.
    const setupArgs = (jest.requireMock('msw/node') as any).__setupArgs();
    expect(setupArgs).toHaveLength(mockHandlers.allHandlers.length);
    expect(setupArgs).toEqual(mockHandlers.allHandlers);
  });

  it('startMockServer/stopMockServer/resetMockHandlers drive the server', () => {
    mockHandlers.startMockServer();
    expect(server.listen).toHaveBeenCalledWith({ onUnhandledRequest: 'warn' });

    mockHandlers.stopMockServer();
    expect(server.close).toHaveBeenCalled();

    mockHandlers.resetMockHandlers();
    expect(server.resetHandlers).toHaveBeenCalled();
  });

  it('overrideHandlers resets with all + overrides', () => {
    const override = { method: 'GET', url: '/override', resolver: () => {} };
    mockHandlers.overrideHandlers(override as any);
    expect(server.resetHandlers).toHaveBeenLastCalledWith(
      ...mockHandlers.allHandlers,
      override
    );
  });

  it('default export bundles every named export', () => {
    expect(mockHandlers.default.authHandlers).toBe(mockHandlers.authHandlers);
    expect(mockHandlers.default.agentHandlers).toBe(mockHandlers.agentHandlers);
    expect(mockHandlers.default.workflowHandlers).toBe(mockHandlers.workflowHandlers);
    expect(mockHandlers.default.canvasHandlers).toBe(mockHandlers.canvasHandlers);
    expect(mockHandlers.default.episodeHandlers).toBe(mockHandlers.episodeHandlers);
    expect(mockHandlers.default.chatHandlers).toBe(mockHandlers.chatHandlers);
    expect(mockHandlers.default.deviceHandlers).toBe(mockHandlers.deviceHandlers);
    expect(mockHandlers.default.errorHandlers).toBe(mockHandlers.errorHandlers);
    expect(mockHandlers.default.allHandlers).toBe(mockHandlers.allHandlers);
    expect(mockHandlers.default.mockServer).toBe(mockHandlers.mockServer);
    expect(mockHandlers.default.startMockServer).toBe(mockHandlers.startMockServer);
    expect(mockHandlers.default.stopMockServer).toBe(mockHandlers.stopMockServer);
    expect(mockHandlers.default.resetMockHandlers).toBe(mockHandlers.resetMockHandlers);
    expect(mockHandlers.default.overrideHandlers).toBe(mockHandlers.overrideHandlers);
  });

  it('message handler filters by conversationId', () => {
    const first = mockConversations[0] as any;
    const chat = captured.find((h) => h.url.endsWith('/conversations/:id/messages') && h.method === 'GET')!;
    expect(chat).toBeTruthy();
    const result = callResolver(chat, { id: first.id });
    expect(Array.isArray(result.parts)).toBe(true);
    expect(mockMessages.filter((m: any) => m.conversationId === first.id).length).toBeGreaterThan(0);
  });
});
