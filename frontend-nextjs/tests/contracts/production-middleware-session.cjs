// Real installed NextAuth SDK session cookies through the actual middleware.
// Tokens are synthetic and never printed; assertions report only status and
// the relative callback target.
const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');

const originalEnv = {
  NODE_ENV: process.env.NODE_ENV,
  NEXTAUTH_URL: process.env.NEXTAUTH_URL,
  NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
};
const originalTs = require.extensions['.ts'];

process.env.NODE_ENV = 'test';
process.env.NEXTAUTH_URL = 'http://localhost:3000';
process.env.NEXTAUTH_SECRET = crypto.randomBytes(32).toString('base64url');

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

const { encode } = require('next-auth/jwt');
const { NextRequest } = require('next/server');
const { middleware } = require(path.join(root, 'middleware.ts'));

after(() => {
  if (originalTs) require.extensions['.ts'] = originalTs;
  else delete require.extensions['.ts'];
  for (const [name, value] of Object.entries(originalEnv)) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
});

function makeRequest(url, cookie, headers = {}) {
  const requestHeaders = { ...headers };
  if (cookie) requestHeaders.cookie = cookie;
  return new NextRequest(url, { headers: requestHeaders });
}

function callbackFrom(response) {
  const location = response.headers.get('location');
  if (!location) return null;
  return new URL(location, 'http://localhost:3000').searchParams.get('callbackUrl');
}

async function encryptedSession(secret = process.env.NEXTAUTH_SECRET, maxAge = 60) {
  return encode({
    secret,
    token: { sub: 'test-user', backendToken: 'test-backend-session' },
    maxAge,
  });
}

function chunked(name, token) {
  const half = Math.floor(token.length / 2);
  return `${name}.0=${token.slice(0, half)}; ${name}.1=${token.slice(half)}`;
}

function assertAdmitted(response) {
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('location'), null);
}

function assertRejected(response, expectedCallback) {
  assert.equal(response.status, 307);
  if (expectedCallback) assert.equal(callbackFrom(response), expectedCallback);
}

test('production secure session cookie admits a protected page', async () => {
  process.env.NEXTAUTH_URL = 'https://app.example.invalid';
  const token = await encryptedSession();
  const response = await middleware(makeRequest(
    'https://app.example.invalid/settings?return=verified',
    `__Secure-next-auth.session-token=${token}`,
  ));
  assertAdmitted(response);
});

test('production chunked session cookie admits a protected page', async () => {
  process.env.NEXTAUTH_URL = 'https://app.example.invalid';
  const token = await encryptedSession();
  const response = await middleware(makeRequest(
    'https://app.example.invalid/settings?return=verified',
    chunked('__Secure-next-auth.session-token', token),
  ));
  assertAdmitted(response);
});

test('development session cookie admits a protected page', async () => {
  const token = await encryptedSession();
  const response = await middleware(makeRequest(
    'http://localhost:3000/settings',
    `next-auth.session-token=${token}`,
  ));
  assertAdmitted(response);
});

test('invalid session cookie redirects with the relative protected target', async () => {
  const response = await middleware(makeRequest(
    'http://localhost:3000/settings?return=verified',
    'next-auth.session-token=invalid',
  ));
  assertRejected(response, '/settings?return=verified');
});

test('expired session cookie does not admit a protected page', async () => {
  const token = await encryptedSession(undefined, -60);
  const response = await middleware(makeRequest(
    'http://localhost:3000/settings',
    `next-auth.session-token=${token}`,
  ));
  assertRejected(response);
});

test('tampered session cookie does not admit a protected page', async () => {
  const token = await encryptedSession();
  const replacement = token.endsWith('AAAAAA') ? 'BBBBBB' : 'AAAAAA';
  const response = await middleware(makeRequest(
    'http://localhost:3000/settings',
    `next-auth.session-token=${token.slice(0, -6)}${replacement}`,
  ));
  assertRejected(response);
});

test('session signed with a different key does not admit a protected page', async () => {
  const token = await encryptedSession(crypto.randomBytes(32).toString('base64url'));
  const response = await middleware(makeRequest(
    'http://localhost:3000/settings',
    `next-auth.session-token=${token}`,
  ));
  assertRejected(response);
});

test('missing signing secret does not admit a protected page', async () => {
  const token = await encryptedSession();
  const saved = process.env.NEXTAUTH_SECRET;
  delete process.env.NEXTAUTH_SECRET;
  try {
    const response = await middleware(makeRequest(
      'http://localhost:3000/settings',
      `next-auth.session-token=${token}`,
    ));
    assertRejected(response);
  } finally {
    process.env.NEXTAUTH_SECRET = saved;
  }
});

test('malformed chunked session does not admit a protected page', async () => {
  process.env.NEXTAUTH_URL = 'https://app.example.invalid';
  const token = await encryptedSession();
  const half = Math.floor(token.length / 2);
  const response = await middleware(makeRequest(
    'https://app.example.invalid/settings',
    `__Secure-next-auth.session-token.0=${token.slice(0, half)}`,
  ));
  assertRejected(response);
});

test('authorization header alone does not admit a protected page', async () => {
  const token = await encryptedSession();
  const response = await middleware(makeRequest(
    'http://localhost:3000/settings',
    null,
    { authorization: `Bearer ${token}` },
  ));
  assertRejected(response);
});

test('legacy auth_token still admits a protected page', async () => {
  const response = await middleware(makeRequest(
    'http://localhost:3000/settings',
    'auth_token=test-token',
  ));
  assert.equal(response.headers.get('location'), null);
});

test('public API passes through and forwards auth_token', async () => {
  const response = await middleware(makeRequest(
    'http://localhost:3000/api/health',
    'auth_token=test-token',
  ));
  assert.equal(response.headers.get('location'), null);
  assert.equal(
    response.headers.get('x-middleware-request-authorization'),
    'Bearer test-token',
  );
});

test('public login page is not redirected', async () => {
  const response = await middleware(makeRequest('http://localhost:3000/login'));
  assert.equal(response.headers.get('location'), null);
});
