#!/usr/bin/env node
/**
 * Bundle the Monaco editor's static assets with the app.
 *
 * `@monaco-editor/react` configures `@monaco-editor/loader` with
 * `https://cdn.jsdelivr.net/npm/monaco-editor@<version>/min/vs` by default, so
 * a canvas page cannot render its editor without internet access — an
 * air-gapped install, the desktop/Tauri bundle, a firewalled deployment, and
 * the WA-045 "external traffic refused" acceptance run all failed there.
 *
 * This copies the already-installed `monaco-editor` package's AMD build into
 * `public/monaco/vs`, where the browser loads it same-origin. The loader is
 * pointed at that path by `lib/monaco-local.ts`.
 *
 * Called from `next.config.js` so EVERY `next dev` / `next build` invocation
 * gets the assets — including the acceptance harness, Docker builds and Tauri
 * — without depending on an npm lifecycle script that callers can skip.
 *
 * The copy is version-stamped and idempotent. The generated tree is gitignored
 * (~15 MB of vendor files); it is rebuilt from the installed package.
 */
const fs = require('fs');
const path = require('path');

const FRONTEND = path.resolve(__dirname, '..');
const PACKAGE_DIR = path.join(FRONTEND, 'node_modules', 'monaco-editor');
const DEFAULT_SOURCE = path.join(PACKAGE_DIR, 'min', 'vs');
const DEFAULT_PUBLIC_ROOT = path.join(FRONTEND, 'public', 'monaco');
const STAMP_FILE = '.version';

function readPackageVersion() {
  const manifest = path.join(PACKAGE_DIR, 'package.json');
  if (!fs.existsSync(manifest)) return null;
  try {
    return JSON.parse(fs.readFileSync(manifest, 'utf8')).version || null;
  } catch {
    return null;
  }
}

/**
 * @param {{
 *   source?: string,
 *   publicRoot?: string,
 *   version?: string,
 *   log?: (message: string) => void,
 * }} [options]
 * @returns {{status: 'current'|'copied'|'skipped', version: string|null, dest: string}}
 */
function syncMonacoAssets(options = {}) {
  const source = options.source || DEFAULT_SOURCE;
  const publicRoot = options.publicRoot || DEFAULT_PUBLIC_ROOT;
  const dest = path.join(publicRoot, 'vs');
  const log = options.log || (() => {});

  if (process.env.ATOM_SKIP_MONACO_ASSET_SYNC === '1') {
    log('monaco assets: skipped by ATOM_SKIP_MONACO_ASSET_SYNC');
    return { status: 'skipped', version: null, dest };
  }

  const version = options.version || readPackageVersion();
  if (!version) {
    throw new Error(
      `[monaco-assets] cannot resolve the installed monaco-editor version ` +
      `(${PACKAGE_DIR}); the canvas editor cannot be served offline`);
  }
  if (!fs.existsSync(source)) {
    throw new Error(`[monaco-assets] missing ${source}; run npm install`);
  }

  const stampPath = path.join(publicRoot, STAMP_FILE);
  const current = fs.existsSync(dest)
    && fs.existsSync(stampPath)
    && fs.readFileSync(stampPath, 'utf8').trim() === version;
  if (current) return { status: 'current', version, dest };

  fs.mkdirSync(publicRoot, { recursive: true });
  // Stage then rename so a concurrent dev server never serves a half-copied
  // tree; the rename is atomic within the same filesystem.
  const staging = `${dest}.tmp-${process.pid}`;
  fs.rmSync(staging, { recursive: true, force: true });
  fs.cpSync(source, staging, { recursive: true });
  fs.rmSync(dest, { recursive: true, force: true });
  fs.renameSync(staging, dest);
  fs.writeFileSync(stampPath, `${version}\n`);
  log(`monaco assets: copied monaco-editor@${version} -> public/monaco/vs`);
  return { status: 'copied', version, dest };
}

module.exports = { syncMonacoAssets, DEFAULT_SOURCE, DEFAULT_PUBLIC_ROOT };

if (require.main === module) {
  try {
    syncMonacoAssets({ log: (message) => console.log(message) });
  } catch (error) {
    console.error(String(error && error.message ? error.message : error));
    process.exit(1);
  }
}
