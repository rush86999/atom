/**
 * WA-075 — settings/sessions must never ship bearer material to the proxy.
 *
 * Before this contract the page POSTed `localStorage.auth_token` so the proxy
 * could upsert a `user_sessions` row keyed on the raw token. That made the
 * browser the inventory writer, stored a raw bearer, and (once revocation was
 * made real) would have let a user record a token they did not own. The
 * heartbeat is now bodyless and identity comes from the session credential the
 * server already verified.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react';

jest.mock('next/router', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('next-auth/react', () => ({
  signOut: jest.fn(),
}));

const SessionSettings = require('@/pages/settings/sessions').default;

describe('settings/sessions — no client-supplied session material', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    const store: Record<string, string> = { auth_token: 'jwt-real-token-123' };
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (k: string) => store[k] ?? null,
        setItem: jest.fn(),
        removeItem: jest.fn(),
        clear: jest.fn(),
        key: (): string | null => null,
        length: 0,
      },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async (): Promise<{ sessions: unknown[] }> => ({ sessions: [] }),
    }) as any;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('sends a bodyless heartbeat', async () => {
    render(<SessionSettings />);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/auth/sessions', { method: 'POST' });
    });
  });

  it('never sends the stored bearer or the legacy placeholder in any request body', async () => {
    render(<SessionSettings />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const calls = (global.fetch as jest.Mock).mock.calls.filter(
      ([url]: any[]) => String(url).includes('/api/auth/sessions'),
    );
    expect(calls.length).toBeGreaterThan(0);
    for (const [, init] of calls) {
      expect(init?.body).toBeUndefined();
      expect(JSON.stringify(init ?? {})).not.toContain('jwt-real-token-123');
      expect(JSON.stringify(init ?? {})).not.toContain('current-session-token');
    }
  });
});
