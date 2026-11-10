import fs from 'node:fs';
import path from 'node:path';

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalAllowLoopback = process.env.NEXT_PUBLIC_ALLOW_LOOPBACK;
const configPath = require.resolve('../next.config.js');

function loadConfig(apiUrl: string) {
  process.env.NEXT_PUBLIC_API_URL = apiUrl;
  delete process.env.NEXT_PUBLIC_ALLOW_LOOPBACK;
  delete require.cache[configPath];
  return require('../next.config.js') as {
    rewrites: () => Promise<{
      afterFiles: Array<{ source: string; destination: string }>;
      fallback: Array<{ source: string; destination: string }>;
    }>;
  };
}

afterAll(() => {
  if (originalApiUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
  else process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
  if (originalAllowLoopback === undefined) delete process.env.NEXT_PUBLIC_ALLOW_LOOPBACK;
  else process.env.NEXT_PUBLIC_ALLOW_LOOPBACK = originalAllowLoopback;
  delete require.cache[configPath];
});

describe('same-origin web OIDC rewrite precedence', () => {
  test('puts the exact SSO web family in afterFiles before NextAuth catchall', async () => {
    const config = loadConfig('https://backend.example.invalid');
    const rewrites = await config.rewrites();
    const sso = rewrites.afterFiles.find(
      (rewrite) => rewrite.source === '/api/auth/sso/oidc/web/:path*',
    );
    expect(sso).toEqual({
      source: '/api/auth/sso/oidc/web/:path*',
      destination: 'https://backend.example.invalid/api/auth/sso/oidc/web/:path*',
    });
    expect(
      rewrites.fallback.some((rewrite) =>
        rewrite.source.startsWith('/api/auth/sso/oidc/web')),
    ).toBe(false);
  });

  test('uses the configured backend origin when it is remapped', async () => {
    const config = loadConfig('https://api.remapped.example');
    const rewrites = await config.rewrites();
    expect(
      rewrites.afterFiles.find(
        (rewrite) => rewrite.source === '/api/auth/sso/oidc/web/:path*',
      )?.destination,
    ).toBe('https://api.remapped.example/api/auth/sso/oidc/web/:path*');
  });

  test('does not broad-proxy installed NextAuth session/csrf/callback routes', async () => {
    const config = loadConfig('https://backend.example.invalid');
    const rewrites = await config.rewrites();
    const after = rewrites.afterFiles.map((rewrite) => rewrite.source);
    expect(after).not.toContain('/api/auth/:path*');
    expect(after).not.toContain('/api/auth/session');
    expect(after).not.toContain('/api/auth/csrf');
    expect(after).not.toContain('/api/auth/callback/:path*');
    expect(rewrites.fallback).toEqual([
      {
        source: '/api/:path*',
        destination: 'https://backend.example.invalid/api/:path*',
      },
    ]);
    expect(
      fs.existsSync(
        path.resolve(__dirname, '../pages/api/auth/[...nextauth].ts'),
      ),
    ).toBe(true);
  });
});
