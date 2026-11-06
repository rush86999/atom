/**
 * Login return-target tests for session expiry.
 *
 * Both the middleware and the client 401 handlers must hand /login a
 * same-app relative path+query. An absolute URL is rejected by the login
 * guard and silently falls back to /dashboard, losing the deep link.
 */
import { handleSessionExpired, loginCallbackPath } from '@/lib/auth-headers';

describe('loginCallbackPath', () => {
  test('returns the path and query without an origin', () => {
    expect(
      loginCallbackPath({ pathname: '/workflows/123', search: '?tab=steps' }),
    ).toBe('/workflows/123?tab=steps');
  });

  test('returns a bare path when there is no query', () => {
    expect(
      loginCallbackPath({ pathname: '/dashboard', search: '' }),
    ).toBe('/dashboard');
  });

  test('never includes a scheme or host', () => {
    const target = loginCallbackPath({
      pathname: '/settings/account',
      search: '?section=security',
    });
    expect(target.startsWith('/')).toBe(true);
    expect(target.startsWith('//')).toBe(false);
    expect(target).not.toContain('://');
  });
});

describe('handleSessionExpired', () => {
  test('bounces to /login with a relative callbackUrl', () => {
    const navigate = jest.fn();

    expect(handleSessionExpired(
      { pathname: '/workflows/123', search: '?tab=steps' },
      navigate,
    )).toBe(true);
    expect(navigate).toHaveBeenCalledWith(
      '/login?callbackUrl=%2Fworkflows%2F123%3Ftab%3Dsteps',
    );
  });

  test('does not redirect from an auth page', () => {
    const navigate = jest.fn();

    expect(handleSessionExpired(
      { pathname: '/login', search: '' },
      navigate,
    )).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });
});
