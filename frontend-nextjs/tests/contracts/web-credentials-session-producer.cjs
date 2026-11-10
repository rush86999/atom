// Actual installed NextAuth Credentials handler: an already-issued backend
// bearer is validated at /api/auth/me, then the SDK encrypts its own session
// cookie. Token values are synthetic and never printed.
const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Module = require('node:module');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');

const originalResolve = Module._resolveFilename;
const originalFetch = global.fetch;
const originalTs = require.extensions['.ts'];
const originalEnv = {
  NODE_ENV: process.env.NODE_ENV,
  NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
  NEXTAUTH_URL: process.env.NEXTAUTH_URL,
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
};

process.env.NODE_ENV = 'development';
process.env.NEXTAUTH_URL = 'http://localhost:3000';
process.env.NEXT_PUBLIC_API_URL = 'http://controlled-backend.invalid';
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
const { decode } = require('next-auth/jwt');
const pageModule = path.join(root, 'pages/api/auth/[...nextauth].ts');

after(() => {
  Module._resolveFilename = originalResolve;
  global.fetch = originalFetch;
  if (originalTs) require.extensions['.ts'] = originalTs;
  else delete require.extensions['.ts'];
  for (const [name, value] of Object.entries(originalEnv)) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
});

function identity(overrides = {}) {
  return {
    id: 'canonical-user',
    email: 'canonical@example.invalid',
    first_name: 'Canonical',
    last_name: 'User',
    status: 'active',
    role: 'member',
    workspace_id: 'workspace',
    tenant_id: 'tenant',
    ...overrides,
  };
}

function setFetch(status, body) {
  const calls = [];
  global.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    };
  };
  return calls;
}

function cookieHeader(setCookie) {
  return setCookie.map((cookie) => cookie.split(';')[0]).join('; ');
}

function cookieMap(setCookie) {
  const cookies = {};
  for (const cookie of setCookie) {
    const pair = cookie.split(';')[0];
    const index = pair.indexOf('=');
    cookies[pair.slice(0, index)] = decodeURIComponent(pair.slice(index + 1));
  }
  return cookies;
}

async function csrf() {
  const { req, res } = createMocks({
    method: 'GET',
    query: { nextauth: ['csrf'] },
    headers: { host: 'localhost:3000' },
  });
  await require(pageModule).default(req, res);
  const setCookie = res._getHeaders()['set-cookie'] || [];
  const raw = res._getData();
  const body = typeof raw === 'string' ? JSON.parse(raw || '{}') : (raw || {});
  assert.equal(typeof body.csrfToken, 'string');
  return {
    csrfToken: body.csrfToken,
    cookie: cookieHeader(setCookie),
    cookies: cookieMap(setCookie),
  };
}

async function signInWithCredentials(backendToken) {
  const { csrfToken, cookie, cookies } = await csrf();
  const { req, res } = createMocks({
    method: 'POST',
    query: { nextauth: ['callback', 'credentials'] },
    cookies,
    headers: {
      host: 'localhost:3000',
      cookie,
      'content-type': 'application/x-www-form-urlencoded',
    },
  });
  req.body = { csrfToken, backendToken, json: 'true' };
  await require(pageModule).default(req, res);
  return res;
}

function sessionCookie(setCookie) {
  return setCookie.find((cookie) =>
    cookie.startsWith('next-auth.session-token='));
}

test('explicit backend bearer produces an SDK-encrypted session cookie', async () => {
  const calls = setFetch(200, identity());
  const response = await signInWithCredentials('issued-bearer');
  const setCookie = response._getHeaders()['set-cookie'] || [];
  const cookie = sessionCookie(setCookie);

  assert.ok(cookie, 'SDK session cookie emitted');
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/auth\/me$/);
  assert.equal(calls[0].options.headers.Authorization === 'Bearer issued-bearer', true);
  assert.equal(calls.some((call) => /\/api\/auth\/login$/.test(call.url)), false);

  const value = decodeURIComponent(cookie.slice(cookie.indexOf('=') + 1).split(';')[0]);
  assert.equal(value === 'issued-bearer', false);
  const payload = await decode({ token: value, secret: process.env.NEXTAUTH_SECRET });
  assert.equal(payload.id, 'canonical-user');
  assert.equal(payload.email, 'canonical@example.invalid');
  assert.equal(payload.backendToken === 'issued-bearer', true);
  assert.equal(/HttpOnly/i.test(cookie), true);
  assert.equal(/SameSite=Lax/i.test(cookie), true);
});

test('invalid explicit bearer emits no session cookie and never logs in again', async () => {
  const calls = setFetch(401, { detail: 'expired' });
  const response = await signInWithCredentials('expired-bearer');
  const setCookie = response._getHeaders()['set-cookie'] || [];

  assert.equal(sessionCookie(setCookie) === undefined, true);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/auth\/me$/);
  assert.equal(calls.some((call) => /\/api\/auth\/login$/.test(call.url)), false);
  assert.equal((response._getData() || '').includes('expired-bearer'), false);
});

test('inactive current identity emits no session cookie', async () => {
  const calls = setFetch(200, identity({ status: 'inactive' }));
  const response = await signInWithCredentials('inactive-bearer');
  const setCookie = response._getHeaders()['set-cookie'] || [];

  assert.equal(sessionCookie(setCookie) === undefined, true);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/auth\/me$/);
});
