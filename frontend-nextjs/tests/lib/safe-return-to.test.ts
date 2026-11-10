import {
  safeReturnTo,
  validateSameAppReturnTo,
} from '@/lib/safe-return-to';

describe('same-app return target validation', () => {
  test.each([
    '/dashboard',
    '/settings?a4dl=return20261109',
    '/workflows/123?tab=steps',
    '/api/v1/tasks',
  ])('accepts a relative same-app target %s', (value) => {
    expect(validateSameAppReturnTo(value)).toBe(value);
    expect(safeReturnTo(value, '/fallback')).toBe(value);
  });

  test.each([
    '',
    ' ',
    'dashboard',
    '//evil.example/path',
    'https://evil.example/path',
    '/\\evil.example/path',
    '/%5Cevil.example/path',
    '/%2F%2Fevil.example/path',
    '/%252F%252Fevil.example/path',
    '/dashboard%0d%0aX-Test: 1',
    '/dashboard#fragment',
    '/dashboard/../auth/signin',
    '/dashboard/./settings',
    '/auth',
    '/auth/signin',
    '/auth/sso/callback',
    '/api/auth',
    '/api/auth/me',
    '/login',
    `/dashboard?x=${'a'.repeat(2100)}`,
    null,
    42,
    {},
    [],
  ])('rejects unsafe target %p', (value) => {
    expect(validateSameAppReturnTo(value)).toBeNull();
    expect(safeReturnTo(value, '/dashboard')).toBe('/dashboard');
  });
});
