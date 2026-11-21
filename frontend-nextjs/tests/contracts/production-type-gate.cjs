// Real installed Next CLI production type-gate contract.
//
// Two throwaway pages-router fixtures reuse this project's actual
// next.config.js (through a one-line require shim) and its existing
// node_modules (through a symlink). No dependency is installed, no network
// request is made, and the fixtures render static text only: no backend,
// database, provider, runtime key, or credential is touched.
//
// Fixtures live below the project and tracing/bundler roots cover both the
// fixture and installed modules. This avoids external-symlink rejection and
// standalone ../ copies outside the owned output. Type settings remain the
// actual project's settings; the actual default production bundler is used.
//
// Actual builds require >=4 GiB free temporary disk; bounded checks >=2 GiB.
// The caller serializes heavy runs through the existing resource gate.
// Use the current Node executable and platform temporary root; no hard-coded
// macOS path or PATH-selected newer Node. Fixtures are removed; logs retained.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const nextBin = path.join(root, 'node_modules', 'next', 'dist', 'bin', 'next');
const projectConfigPath = path.join(root, 'next.config.js');
const projectNodeModules = fs.realpathSync(path.join(root, 'node_modules'));
let fixtureTracingRoot = fs.realpathSync(root);
while (path.relative(fixtureTracingRoot, projectNodeModules).startsWith('..') ||
       path.isAbsolute(path.relative(fixtureTracingRoot, projectNodeModules))) {
  const parent = path.dirname(fixtureTracingRoot);
  if (parent === fixtureTracingRoot) throw new Error('fixture/modules must share a filesystem root');
  fixtureTracingRoot = parent;
}

const tempRoot = os.tmpdir();
const logDir = fs.mkdtempSync(path.join(tempRoot, 'atom-production-type-gate-logs-'));

const BUILD_TIMEOUT_MS = 15 * 60 * 1000;
const MIN_BOUNDED_BYTES = 2 * 1024 ** 3;
const MIN_HEAVY_BYTES = 4 * 1024 ** 3;

const TSCONFIG = {
  compilerOptions: {
    target: 'ES2020',
    lib: ['dom', 'dom.iterable', 'esnext'],
    allowJs: false,
    skipLibCheck: true,
    strict: true,
    noEmit: true,
    esModuleInterop: true,
    module: 'esnext',
    moduleResolution: 'bundler',
    resolveJsonModule: true,
    isolatedModules: true,
    jsx: 'preserve',
    incremental: true,
  },
  include: ['next-env.d.ts', '**/*.ts', '**/*.tsx'],
  exclude: ['node_modules'],
};

function formatBytes(bytes) {
  return `${(bytes / 1024 ** 3).toFixed(2)} GiB`;
}

// Local callers use the existing shared run_bounded_test_gate wrapper.
// CI runs these two fixtures sequentially in one job; no second lock engine.
function assertResourceGate(kind) {
  const required = kind === 'heavy' ? MIN_HEAVY_BYTES : MIN_BOUNDED_BYTES;
  const disk = fs.statfsSync(tempRoot);
  const available = disk.bavail * disk.bsize;
  assert.ok(available >= required,
    `disk gate (${kind}): need >= ${formatBytes(required)} free, ` +
    `have ${formatBytes(available)}; refusing to start`);
}

// Minimal environment: no inherited secrets, no live backend target, no
// package-manager network path.
function buildEnv() {
  return {
    PATH: process.env.PATH || '',
    HOME: process.env.HOME || '',
    TMPDIR: tempRoot,
    LANG: process.env.LANG || 'en_US.UTF-8',
    CI: '1',
    NODE_ENV: 'production',
    NEXT_PUBLIC_API_URL: 'https://api.example.invalid',
    NEXT_PUBLIC_ALLOW_LOOPBACK: '0',
    NEXT_TELEMETRY_DISABLED: '1',
    NEXT_DIST_DIR: '.next',
    ANALYZE: 'false',
    npm_config_offline: 'true',
    npm_config_audit: 'false',
    npm_config_fund: 'false',
    npm_config_registry: 'https://registry.example.invalid/',
    NO_COLOR: '1',
  };
}

function writeFixture(directory, pageSource) {
  fs.mkdirSync(path.join(directory, 'pages'), { recursive: true });
  fs.symlinkSync(projectNodeModules, path.join(directory, 'node_modules'), 'dir');
  fs.writeFileSync(
    path.join(directory, 'next.config.js'),
    `const config = require(${JSON.stringify(projectConfigPath)});
` +
      `module.exports = { ...config, outputFileTracingRoot: ${JSON.stringify(fixtureTracingRoot)}, ` +
      `turbopack: { ...config.turbopack, root: ${JSON.stringify(fixtureTracingRoot)} } };\n`,
  );
  fs.writeFileSync(path.join(directory, 'tsconfig.json'), JSON.stringify(TSCONFIG, null, 2));
  fs.writeFileSync(path.join(directory, 'pages', 'index.tsx'), pageSource);
}

function runBuild(label, baseDir, pageSource) {
  const fixtureDir = path.join(baseDir, label);
  writeFixture(fixtureDir, pageSource);
  const logPath = path.join(logDir, `${label}.log`);
  const result = spawnSync(process.execPath, [nextBin, 'build'], {
    cwd: fixtureDir,
    env: buildEnv(),
    encoding: 'utf8',
    timeout: BUILD_TIMEOUT_MS,
    maxBuffer: 64 * 1024 * 1024,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const output = [result.stdout, result.stderr].filter(Boolean).join('\n');
  fs.writeFileSync(logPath, output);

  if (result.error && result.error.code === 'ETIMEDOUT') {
    assert.fail(`next build (${label}) exceeded ${BUILD_TIMEOUT_MS}ms; log: ${logPath}`);
  }
  if (result.error) {
    assert.fail(`next build (${label}) could not start: ${result.error.message}; log: ${logPath}`);
  }
  return {
    label,
    status: result.status,
    signal: result.signal,
    output,
    logPath,
  };
}

function assertNoEslintOptionWarning(output, label) {
  assert.doesNotMatch(
    output,
    /Unrecognized key\(s\) in object:? [`'"]?eslint/i,
    `${label}: removed eslint config option must not warn`,
  );
}

function assertNoEnvironmentFailure(output, label) {
  const forbidden = [
    [/Module not found/i, 'module resolution failure'],
    [/Cannot find module/i, 'module resolution failure'],
    [/Failed to load (?:next\.)?config/i, 'config load failure'],
    [/Invalid next\.config/i, 'invalid config'],
    [/Unrecognized key\(s\) in object/i, 'unsupported config key'],
    [/ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ETIMEDOUT/i, 'network failure'],
    [/npm (?:ERR!|error)/i, 'package-manager failure'],
    [/Please install/i, 'missing dependency prompt'],
    [/EACCES|EPERM|ENOSPC|Failed to copy traced files/i, 'filesystem/resource failure'],
    [/TurbopackInternalError/i, 'bundler environment failure'],
    [/Symlink .* is invalid/i, 'filesystem symlink failure'],
  ];
  for (const [pattern, description] of forbidden) {
    assert.doesNotMatch(output, pattern, `${label}: unexpected ${description}`);
  }
}

test('production config enforces type errors and omits the removed eslint option', () => {
  assertResourceGate('bounded');
  assert.ok(fs.existsSync(nextBin), `installed next CLI present at ${nextBin}`);

  const saved = { ...process.env };
  try {
    process.env.NODE_ENV = 'production';
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.invalid';
    process.env.NEXT_PUBLIC_ALLOW_LOOPBACK = '0';
    process.env.ANALYZE = 'false';
    delete require.cache[projectConfigPath];
    const config = require(projectConfigPath);

    assert.equal(
      config.typescript && config.typescript.ignoreBuildErrors,
      false,
      'production config must explicitly enforce TypeScript build errors',
    );
    assert.equal(
      Object.prototype.hasOwnProperty.call(config, 'eslint'),
      false,
      'Next 16 removed the eslint config option; it must not be present',
    );
  } finally {
    for (const key of Object.keys(process.env)) {
      if (!(key in saved)) delete process.env[key];
    }
    Object.assign(process.env, saved);
    delete require.cache[projectConfigPath];
  }
});

test('production config preserves loopback guard and routes server rewrites through BACKEND_URL', async () => {
  const saved = { ...process.env };
  const loadConfig = () => {
    delete require.cache[projectConfigPath];
    return require(projectConfigPath);
  };

  try {
    process.env.NODE_ENV = 'production';
    process.env.ANALYZE = 'false';
    delete process.env.BACKEND_URL;
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.invalid';
    process.env.NEXT_PUBLIC_ALLOW_LOOPBACK = '0';

    const publicRewrites = await loadConfig().rewrites();
    assert.ok(publicRewrites.afterFiles.length > 0, 'production rewrites must be present');
    assert.ok(
      publicRewrites.afterFiles.every(({ destination }) =>
        destination.startsWith('https://api.example.invalid/')),
      'without BACKEND_URL, server rewrites keep the existing public URL fallback',
    );
    assert.equal(
      publicRewrites.fallback[0].destination,
      'https://api.example.invalid/api/:path*',
      'fallback rewrites keep the existing public URL fallback',
    );

    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8001';
    assert.throws(
      loadConfig,
      /Refusing to bake a loopback URL/,
      'production builds must still refuse loopback without explicit opt-in',
    );

    process.env.NEXT_PUBLIC_ALLOW_LOOPBACK = '1';
    process.env.BACKEND_URL = 'http://atom-backend:8000';
    const internalRewrites = await loadConfig().rewrites();
    assert.ok(
      internalRewrites.afterFiles.every(({ destination }) =>
        destination.startsWith('http://atom-backend:8000/')),
      'same-origin server rewrites must use the internal BACKEND_URL',
    );
    assert.ok(
      internalRewrites.afterFiles.every(({ destination }) => !destination.includes('localhost:8001')),
      'server rewrites must not resolve the browser loopback URL inside the container',
    );
    assert.equal(
      internalRewrites.fallback[0].destination,
      'http://atom-backend:8000/api/:path*',
      'fallback rewrites must also use the internal BACKEND_URL',
    );
  } finally {
    for (const key of Object.keys(process.env)) {
      if (!(key in saved)) delete process.env[key];
    }
    Object.assign(process.env, saved);
    delete require.cache[projectConfigPath];
  }
});

test('production Compose supplies frontend build args and runtime web auth env', () => {
  const composePath = path.resolve(root, '..', 'infra', 'docker-compose.prod.yml');
  const compose = fs.readFileSync(composePath, 'utf8');
  const dockerfile = fs.readFileSync(path.join(root, 'Dockerfile.production'), 'utf8');

  assert.match(
    compose,
    /NEXT_PUBLIC_API_URL:\s+\$\{NEXT_PUBLIC_API_URL:-http:\/\/localhost:8001\}/,
    'Compose must pass the existing browser public origin as a build arg',
  );
  assert.match(
    compose,
    /NEXT_PUBLIC_ALLOW_LOOPBACK:\s+\$\{NEXT_PUBLIC_ALLOW_LOOPBACK:-0\}/,
    'Compose must keep the loopback opt-in explicit with a default of 0',
  );
  assert.match(
    compose,
    /BACKEND_URL:\s+http:\/\/atom-backend:8000/,
    'Compose must build server rewrites against the backend service DNS',
  );
  assert.match(
    compose,
    /BACKEND_URL=http:\/\/atom-backend:8000/,
    'Compose must provide the backend service DNS to runtime web auth',
  );
  assert.match(
    compose,
    /NEXTAUTH_SECRET=\$\{NEXTAUTH_SECRET\}/,
    'Compose must pass the configured web auth secret at runtime',
  );
  assert.match(
    compose,
    /NEXTAUTH_URL=\$\{NEXTAUTH_URL:-http:\/\/localhost:3000\}/,
    'Compose must pass the existing web auth runtime URL',
  );
  assert.match(dockerfile, /ARG NEXT_PUBLIC_API_URL\b/, 'Dockerfile must accept the public build arg');
  assert.match(dockerfile, /ARG NEXT_PUBLIC_ALLOW_LOOPBACK\b/, 'Dockerfile must accept the loopback build arg');
  assert.match(dockerfile, /ARG BACKEND_URL\b/, 'Dockerfile must accept the internal build arg');
  assert.doesNotMatch(dockerfile, /NEXTAUTH_SECRET/, 'Dockerfile must not bake the web auth secret into the image');
});

test('installed next build fails only on the injected type error; valid twin builds', () => {
  assertResourceGate('heavy');
  fs.mkdirSync(logDir, { recursive: true });
  const baseDir = fs.mkdtempSync(path.join(root, '.production-type-gate-'));

  try {
    const negative = runBuild(
      'negative',
      baseDir,
      'const answer: number = "deliberate-type-gate-error";\n\n' +
        'export default function Page() {\n' +
        '  return <div>{answer}</div>;\n' +
        '}\n',
    );

    assert.notEqual(
      negative.status,
      0,
      `negative fixture must fail the production build; log: ${negative.logPath}\n` +
        negative.output.slice(-4000),
    );
    assert.match(negative.output, /Running TypeScript \.\.\./, 'type-check stage must run');
    assert.match(negative.output, /Failed to type check\./, 'type-check failure must be explicit');
    assert.match(
      negative.output,
      /Type error: Type 'string' is not assignable to type 'number'\./,
      'the injected number/string type error must be the reported error',
    );
    assert.match(negative.output, /pages[\\/]index\.tsx:1:7/, 'type error must point at the fixture page');
    assert.equal(
      (negative.output.match(/Type error:/g) || []).length,
      1,
      'exactly the one injected type error must be reported',
    );
    assert.doesNotMatch(negative.output, /Skipping validation of types/i, 'type check must not be skipped');
    assertNoEslintOptionWarning(negative.output, 'negative');
    assertNoEnvironmentFailure(negative.output, 'negative');

    const positive = runBuild(
      'valid',
      baseDir,
      'const answer: number = 42;\n\n' +
        'export default function Page() {\n' +
        '  return <div>{answer}</div>;\n' +
        '}\n',
    );

    assert.equal(
      positive.status,
      0,
      `valid twin must build; log: ${positive.logPath}\n` + positive.output.slice(-4000),
    );
    assert.match(positive.output, /Running TypeScript \.\.\./, 'valid build must run the type-check stage');
    assert.match(
      positive.output,
      /Compiled successfully|Generating static pages/,
      'valid twin must complete an optimized production build',
    );
    assert.doesNotMatch(
      positive.output,
      /Type error:|Failed to type check|Failed to compile|Skipping validation of types/i,
      'valid build must not report type errors or skip type validation',
    );
    assertNoEslintOptionWarning(positive.output, 'valid');
    assertNoEnvironmentFailure(positive.output, 'valid');
  } finally {
    fs.rmSync(baseDir, { recursive: true, force: true });
  }
});
