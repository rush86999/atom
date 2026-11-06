/**
 * Middleware auth redirect tests.
 *
 * The login pages accept only same-app relative callbackUrl values. The
 * middleware must therefore pass the protected path + query, not the absolute
 * request URL, or every deep link silently falls back to /dashboard after
 * login. The open-redirect guard remains on the login consumer and is covered
 * by tests/pages/__tests__/login.test.tsx.
 */
import { NextRequest } from 'next/server';

jest.mock('next-auth/jwt', () => ({
  getToken: jest.fn().mockResolvedValue(null),
}));

import { middleware } from '../middleware';

function makeRequest(url: string, cookie?: string) {
  return new NextRequest(
    url,
    cookie ? { headers: { cookie } } : undefined,
  );
}

function callbackFrom(response: Response): string | null {
  const location = response.headers.get('location');
  if (!location) {
    return null;
  }
  return new URL(location, 'http://localhost:3000').searchParams.get(
    'callbackUrl',
  );
}

describe('auth middleware callbackUrl', () => {
  test('preserves an internal protected path and query as a relative target', async () => {
    const response = await middleware(
      makeRequest('http://localhost:3000/workflows/123?tab=steps'),
    );

    expect(response.status).toBe(307);
    expect(callbackFrom(response)).toBe('/workflows/123?tab=steps');
    expect(callbackFrom(response)?.startsWith('http')).toBe(false);
    expect(callbackFrom(response)?.startsWith('//')).toBe(false);
  });

  test('default protected landing still returns to /dashboard', async () => {
    const response = await middleware(
      makeRequest('http://localhost:3000/dashboard'),
    );

    expect(callbackFrom(response)).toBe('/dashboard');
  });

  test('authenticated requests pass through without a login redirect', async () => {
    const response = await middleware(
      makeRequest(
        'http://localhost:3000/workflows/123',
        'auth_token=test-token',
      ),
    );

    expect(response.headers.get('location')).toBeNull();
  });

  test('public login route is not redirected', async () => {
    const response = await middleware(
      makeRequest('http://localhost:3000/login'),
    );

    expect(response.headers.get('location')).toBeNull();
  });
});
