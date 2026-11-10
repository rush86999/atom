import { webSsoLoginPath } from '@/lib/sso-web';

describe('same-origin web SSO entry path', () => {
  test('encodes a safe same-app return target on the web login endpoint', () => {
    expect(webSsoLoginPath('/settings?a4dl=return20261106')).toBe(
      '/api/auth/sso/oidc/web/login?return_to=%2Fsettings%3Fa4dl%3Dreturn20261106',
    );
  });

  test('never builds an absolute or protocol-relative backend URL', () => {
    const path = webSsoLoginPath('/dashboard');
    expect(path.startsWith('/api/auth/sso/oidc/web/login?')).toBe(true);
    expect(path.startsWith('//')).toBe(false);
    expect(path.includes('http://')).toBe(false);
    expect(path.includes('https://')).toBe(false);
  });
});
