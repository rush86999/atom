// Real installed NextAuth handler cookie contract. The actual page API handler
// is invoked through node-mocks-http in production and development contexts;
// no network listener, provider, backend, or credential call is made.
//
// Assertions compare only parsed cookie names and boolean/attribute presence.
// Cookie values, response bodies, and signing material are never printed.
const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const crypto = require('node:crypto');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');

const originalResolve = Module._resolveFilename;
const originalTs = require.extensions['.ts'];
const originalEnv = {
  NODE_ENV: process.env.NODE_ENV,
  NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
  NEXTAUTH_URL: process.env.NEXTAUTH_URL,
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
};

// Synthetic process-local signing material; never logs or persists.
process.env.NEXTAUTH_SECRET = crypto.randomBytes(32).toString('base64url');

Module._resolveFilename = function (request, ...args) {
  if (request.startsWith('@/lib/')) request = path.join(root, request.slice(2));
  return originalResolve.call(this, request, ...args);
};
require.extensions['.ts'] = (module, filename) => module._compile(
  ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
  }).outputText,
  filename,
);

const { createMocks } = require(path.join(root, 'node_modules/node-mocks-http'));
const pageModule = path.join(root, 'pages/api/auth/[...nextauth].ts');

after(() => {
  Module._resolveFilename = originalResolve;
  if (originalTs) require.extensions['.ts'] = originalTs;
  else delete require.extensions['.ts'];
  for (const [name, value] of Object.entries(originalEnv)) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
});

function loadOptions(mode) {
  process.env.NODE_ENV = mode;
  delete require.cache[require.resolve(pageModule)];
  return require(pageModule).authOptions;
}

// Return only name and presence/boolean attributes: never the cookie value.
function parseCookie(cookie) {
  const parts = cookie.split(';').map((part) => part.trim());
  const attributes = {};
  for (const part of parts.slice(1)) {
    const index = part.indexOf('=');
    const key = (index === -1 ? part : part.slice(0, index)).toLowerCase();
    attributes[key] = index === -1 ? true : part.slice(index + 1);
  }
  return {
    name: parts[0].split('=')[0],
    secure: attributes.secure === true,
    httpOnly: attributes.httponly === true,
    sameSite: attributes.samesite || null,
    path: attributes.path || null,
    hasDomain: Object.prototype.hasOwnProperty.call(attributes, 'domain'),
  };
}

async function readCsrfResponse(mode) {
  const authOptions = loadOptions(mode);
  const source = Object.getOwnPropertyDescriptor(authOptions, 'secret');
  assert.equal(typeof source.get, 'function', 'runtime secret getter retained');

  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (...args) => { warnings.push(args.map((value) => String(value)).join(' ')); };
  let response;
  try {
    const { req, res } = createMocks({
      method: 'GET',
      query: { nextauth: ['csrf'] },
      headers: {
        host: 'app.example.invalid',
        'x-forwarded-proto': mode === 'production' ? 'https' : 'http',
      },
    });
    await require(pageModule).default(req, res);
    response = res;
  } finally {
    console.warn = originalWarn;
  }

  const setCookie = response._getHeaders()['set-cookie'] || [];
  return {
    authOptions,
    cookies: setCookie.map(parseCookie),
    debugWarning: warnings.some((line) => line.includes('DEBUG_ENABLED')),
  };
}

function assertCookieShape(cookie, expected) {
  assert.ok(cookie, `${expected.name} cookie emitted`);
  assert.equal(cookie.name, expected.name);
  assert.equal(cookie.secure, expected.secure);
  assert.equal(cookie.httpOnly, true);
  assert.equal(cookie.sameSite, 'Lax');
  assert.equal(cookie.path, '/');
  assert.equal(cookie.hasDomain, false, `${expected.name} must not carry Domain`);
}

test('production: actual handler reuses NextAuth __Host- CSRF and __Secure- cookies without Domain', async () => {
  process.env.NEXTAUTH_URL = 'https://app.example.invalid';
  const { authOptions, cookies, debugWarning } = await readCsrfResponse('production');

  assert.deepEqual(authOptions.providers.map((provider) => provider.id), [
    'google',
    'github',
    'credentials',
  ]);
  assert.equal(authOptions.useSecureCookies, true);
  assert.equal(authOptions.cookies, undefined);
  assert.equal(authOptions.debug, false);
  assert.equal(debugWarning, false);

  const csrf = cookies.find((cookie) => cookie.name.includes('csrf-token'));
  const callback = cookies.find((cookie) => cookie.name.includes('callback-url'));
  assert.equal(cookies.some((cookie) => cookie.hasDomain), false, 'no emitted cookie carries Domain');
  assertCookieShape(csrf, {
    name: '__Host-next-auth.csrf-token',
    secure: true,
  });
  assertCookieShape(callback, {
    name: '__Secure-next-auth.callback-url',
    secure: true,
  });
});

test('development: actual handler reuses NextAuth non-Secure host cookies without Domain', async () => {
  process.env.NEXTAUTH_URL = 'http://localhost:3000';
  const { authOptions, cookies, debugWarning } = await readCsrfResponse('development');

  assert.equal(authOptions.useSecureCookies, false);
  assert.equal(authOptions.cookies, undefined);
  assert.equal(authOptions.debug, false);
  assert.equal(debugWarning, false);

  const csrf = cookies.find((cookie) => cookie.name.includes('csrf-token'));
  const callback = cookies.find((cookie) => cookie.name.includes('callback-url'));
  assert.equal(cookies.some((cookie) => cookie.hasDomain), false, 'no emitted cookie carries Domain');
  assertCookieShape(csrf, {
    name: 'next-auth.csrf-token',
    secure: false,
  });
  assertCookieShape(callback, {
    name: 'next-auth.callback-url',
    secure: false,
  });
});
