// Real installed Next CLI production type-gate contract.
//
// Two throwaway pages-router fixtures reuse this project's actual
// next.config.js (through a one-line require shim) and its existing
// node_modules (through a symlink). No dependency is installed, no network
// request is made, and the fixtures render static text only: no backend,
// database, provider, runtime key, or credential is touched.
//
// Why --webpack: the fixtures live outside the project tree, and installed
// Next 16.2.2 / Turbopack rejects a node_modules symlink that points outside
// the fixture's filesystem root ("Symlink [project]/node_modules is invalid"),
// even for the valid twin. --webpack is the same installed `next build` CLI
// and runs the same production TypeScript validation stage before bundling;
// it is not a type-check bypass.
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
    `module.exports = require(${JSON.stringify(projectConfigPath)});\n`,
  );
  fs.writeFileSync(path.join(directory, 'tsconfig.json'), JSON.stringify(TSCONFIG, null, 2));
  fs.writeFileSync(path.join(directory, 'pages', 'index.tsx'), pageSource);
}

function runBuild(label, baseDir, pageSource) {
  const fixtureDir = path.join(baseDir, label);
  writeFixture(fixtureDir, pageSource);
  const logPath = path.join(logDir, `${label}.log`);
  const result = spawnSync(process.execPath, [nextBin, 'build', '--webpack'], {
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

test('installed next build fails only on the injected type error; valid twin builds', () => {
  assertResourceGate('heavy');
  fs.mkdirSync(logDir, { recursive: true });
  const baseDir = fs.mkdtempSync(path.join(tempRoot, 'atom-production-type-gate-'));

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
