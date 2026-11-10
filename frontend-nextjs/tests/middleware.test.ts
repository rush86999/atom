/**
 * @jest-environment jsdom
 * @jest-environment-options {"customExportConditions": ["node", "node-addons"]}
 *
 * Middleware auth admission tests.
 *
 * The login pages accept only same-app relative callbackUrl values. The
 * middleware must therefore pass the protected path + query, not the absolute
 * request URL, or every deep link silently falls back to /dashboard after
 * login. The open-redirect guard remains on the login consumer and is covered
 * by tests/pages/__tests__/login.test.tsx.
 *
 * Session cookies are produced by the installed NextAuth SDK. Token values are
 * synthetic and never printed, even on failure.
 */
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';

import { NextRequest } from 'next/server';

import { middleware } from '../middleware';

const originalNextAuthUrl = process.env.NEXTAUTH_URL;
const originalNextAuthSecret = process.env.NEXTAUTH_SECRET;

function makeRequest(
  url: string,
  cookie?: string,
  headers: Record<string, string> = {},
) {
  const requestHeaders = { ...headers };
  if (cookie) {
    requestHeaders.cookie = cookie;
  }
  return new NextRequest(url, { headers: requestHeaders });
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

async function encryptedSession(
  secret = process.env.NEXTAUTH_SECRET as string,
  maxAge = 60,
): Promise<string> {
  // jsdom's realm-specific encoders break jose's Node Uint8Array checks when
  // the SDK runs in the Jest VM. Encode with the same installed SDK in a plain
  // Node process and return only the opaque token through a pipe.
  const script = `
    const { encode } = require(${JSON.stringify(require.resolve('next-auth/jwt'))});
    encode({
      secret: process.env.TEST_SESSION_SECRET,
      token: { sub: 'test-user', backendToken: 'test-backend-session' },
      maxAge: ${Number(maxAge)},
    }).then((token) => process.stdout.write(token));
  `;
  return execFileSync(process.execPath, ['-e', script], {
    env: { ...process.env, TEST_SESSION_SECRET: secret },
    encoding: 'utf8',
  }).trim();
}

function chunkedCookie(name: string, token: string): string {
  const half = Math.floor(token.length / 2);
  return `${name}.0=${token.slice(0, half)}; ${name}.1=${token.slice(half)}`;
}

beforeEach(() => {
  process.env.NEXTAUTH_URL = 'http://localhost:3000';
});

afterAll(() => {
  if (originalNextAuthUrl === undefined) {
    delete process.env.NEXTAUTH_URL;
  } else {
    process.env.NEXTAUTH_URL = originalNextAuthUrl;
  }
  if (originalNextAuthSecret === undefined) {
    delete process.env.NEXTAUTH_SECRET;
  } else {
    process.env.NEXTAUTH_SECRET = originalNextAuthSecret;
  }
});

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

  test('captured Settings deep link becomes a relative callback', async () => {
    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings?a4dl=return20261106',
      ),
    );

    expect(callbackFrom(response)).toBe(
      '/settings?a4dl=return20261106',
    );
  });

  test('default protected landing still returns to /dashboard', async () => {
    const response = await middleware(
      makeRequest('http://localhost:3000/dashboard'),
    );

    expect(callbackFrom(response)).toBe('/dashboard');
  });

  test('legacy auth_token still admits a protected page', async () => {
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

describe('NextAuth session cookie admission', () => {
  test('valid production secure session admits a protected page', async () => {
    process.env.NEXTAUTH_URL = 'https://app.example.invalid';
    const token = await encryptedSession();

    const response = await middleware(
      makeRequest(
        'https://app.example.invalid/settings?return=verified',
        `__Secure-next-auth.session-token=${token}`,
      ),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });

  test('valid production chunked session admits a protected page', async () => {
    process.env.NEXTAUTH_URL = 'https://app.example.invalid';
    const token = await encryptedSession();

    const response = await middleware(
      makeRequest(
        'https://app.example.invalid/settings?return=verified',
        chunkedCookie('__Secure-next-auth.session-token', token),
      ),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });

  test('valid development session admits a protected page', async () => {
    const token = await encryptedSession();

    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings',
        `next-auth.session-token=${token}`,
      ),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });

  test('invalid session cookie redirects with a relative callback', async () => {
    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings?return=verified',
        'next-auth.session-token=invalid',
      ),
    );

    expect(response.status).toBe(307);
    expect(callbackFrom(response)).toBe('/settings?return=verified');
  });

  test('expired session cookie does not admit a protected page', async () => {
    const token = await encryptedSession(undefined, -60);

    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings',
        `next-auth.session-token=${token}`,
      ),
    );

    expect(response.status).toBe(307);
  });

  test('tampered session cookie does not admit a protected page', async () => {
    const token = await encryptedSession();
    const replacement = token.endsWith('AAAAAA') ? 'BBBBBB' : 'AAAAAA';
    const tampered = `${token.slice(0, -6)}${replacement}`;

    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings',
        `next-auth.session-token=${tampered}`,
      ),
    );

    expect(response.status).toBe(307);
  });

  test('session signed with a different key does not admit a protected page', async () => {
    const token = await encryptedSession(
      randomBytes(32).toString('base64url'),
    );

    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings',
        `next-auth.session-token=${token}`,
      ),
    );

    expect(response.status).toBe(307);
  });

  test('missing signing secret does not admit a protected page', async () => {
    const token = await encryptedSession();
    const savedSecret = process.env.NEXTAUTH_SECRET;
    delete process.env.NEXTAUTH_SECRET;

    try {
      const response = await middleware(
        makeRequest(
          'http://localhost:3000/settings',
          `next-auth.session-token=${token}`,
        ),
      );

      expect(response.status).toBe(307);
    } finally {
      process.env.NEXTAUTH_SECRET = savedSecret;
    }
  });

  test('malformed chunked session does not admit a protected page', async () => {
    process.env.NEXTAUTH_URL = 'https://app.example.invalid';
    const token = await encryptedSession();
    const half = Math.floor(token.length / 2);

    const response = await middleware(
      makeRequest(
        'https://app.example.invalid/settings',
        `__Secure-next-auth.session-token.0=${token.slice(0, half)}`,
      ),
    );

    expect(response.status).toBe(307);
  });

  test('an authorization header alone does not admit a protected page', async () => {
    const token = await encryptedSession();

    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings',
        undefined,
        { authorization: `Bearer ${token}` },
      ),
    );

    expect(response.status).toBe(307);
  });

  test('invalid cookie never falls back to a valid authorization header', async () => {
    const token = await encryptedSession();

    const response = await middleware(
      makeRequest(
        'http://localhost:3000/settings',
        'next-auth.session-token=invalid',
        { authorization: `Bearer ${token}` },
      ),
    );

    expect(response.status).toBe(307);
  });
});

describe('public password-recovery and verification pages', () => {
  test.each([
    '/auth/forgot-password',
    '/auth/reset-password?token=nonsecret-probe',
    '/auth/verify-email?email=user%40example.com',
    '/auth/verification-sent?email=user%40example.com',
    '/auth/error',
    '/auth/signin',
    '/auth/signup',
    '/login',
  ])('%s is reachable without a session', async (path) => {
    const response = await middleware(
      makeRequest(`http://localhost:3000${path}`),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });

  test.each([
    '/auth',
    '/auth/unknown',
    '/auth/forgot-password/extra',
    '/auth/reset-password-evil',
    '/auth/verify-emailx',
    '/login-extra',
    '/settings',
    '/settings/account',
    '/settings?token=nonsecret-probe',
  ])('%s remains gated without a session', async (path) => {
    const response = await middleware(
      makeRequest(`http://localhost:3000${path}`),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).not.toBeNull();
  });
});

describe('SSO callback admission', () => {
  test('public exact callback is reachable with no-store and no-referrer', async () => {
    const response = await middleware(
      makeRequest(
        'http://localhost:3000/auth/sso/callback?code=nonsecret-probe',
      ),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
    expect(response.headers.get('cache-control')).toBe('no-store');
    expect(response.headers.get('referrer-policy')).toBe('no-referrer');
  });

  test.each([
    '/auth/sso/callback/extra',
    '/auth/sso/callback-evil',
    '/auth/sso',
  ])('%s is not made public by the exact callback route', async (path) => {
    const response = await middleware(
      makeRequest(`http://localhost:3000${path}`),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).not.toBeNull();
  });

  test('SSO web API family remains a public same-origin API passthrough', async () => {
    const response = await middleware(
      makeRequest(
        'http://localhost:3000/api/auth/sso/oidc/web/exchange',
        'auth_token=test-token',
      ),
    );

    expect(response.headers.get('location')).toBeNull();
    expect(
      response.headers.get('x-middleware-request-authorization'),
    ).toBe('Bearer test-token');
  });
});

describe('API passthrough', () => {
  test('public API route is not redirected and forwards auth_token', async () => {
    const response = await middleware(
      makeRequest('http://localhost:3000/api/health', 'auth_token=test-token'),
    );

    expect(response.headers.get('location')).toBeNull();
    expect(
      response.headers.get('x-middleware-request-authorization'),
    ).toBe('Bearer test-token');
  });
});
