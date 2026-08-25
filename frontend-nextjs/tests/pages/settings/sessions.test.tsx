/**
 * Round 82 / F8 — settings/sessions page records the real backend token.
 *
 * The page used to POST the literal placeholder 'current-session-token' as
 * the session token. The proxy upserts on session_token
 * (ON CONFLICT (session_token) DO UPDATE), so every user's "record current
 * session" ping collided onto ONE shared row, and the is_current check
 * (session_token = backendToken) could never match.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react';

jest.mock('next/router', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('ua-parser-js', () => {
  return jest.fn().mockImplementation(() => ({
    getResult: () => ({
      device: { type: 'desktop' },
      browser: { name: 'jest' },
      os: { name: 'ci' },
    }),
  }));
});

const SessionSettings =
  require('@/pages/settings/sessions').default;

describe('settings/sessions — current-session recording', () => {
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

  it('sends the stored auth_token, not a placeholder constant', async () => {
    render(<SessionSettings />);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/auth/sessions',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ token: 'jwt-real-token-123' }),
        })
      );
    });
  });

  it('never sends the legacy placeholder value', async () => {
    render(<SessionSettings />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const calls = (global.fetch as jest.Mock).mock.calls.filter(
      ([url]: any[]) => String(url).includes('/api/auth/sessions')
    );
    expect(calls.length).toBeGreaterThan(0);
    for (const [, init] of calls) {
      expect(String(init?.body)).not.toContain('current-session-token');
    }
  });
});
