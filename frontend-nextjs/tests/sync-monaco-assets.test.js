/**
 * Guards for the Monaco asset bundler that lets the canvas editor load with no
 * external traffic: it copies the installed `monaco-editor` AMD build into
 * `public/monaco/vs`, version-stamped so restarts are cheap and upgrades
 * re-copy. A stale or half-written tree would break the editor offline, so the
 * stamp/atomic-swap behaviour is pinned here (no browser, no Next server).
 */
const fs = require('fs');
const os = require('os');
const path = require('path');

const { syncMonacoAssets } = require('../scripts/sync-monaco-assets');

function writeTree(root, files) {
  for (const [relative, content] of Object.entries(files)) {
    const target = path.join(root, relative);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content);
  }
}

function makeSource(root, marker = 'v1') {
  const source = path.join(root, 'source');
  writeTree(source, {
    'loader.js': `// ${marker}`,
    'editor/editor.main.js': `// ${marker}`,
    'assets/editor.worker.js': `// ${marker}`,
  });
  return source;
}

describe('syncMonacoAssets', () => {
  let tmp;
  const originalSkip = process.env.ATOM_SKIP_MONACO_ASSET_SYNC;

  beforeEach(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'monaco-assets-'));
    delete process.env.ATOM_SKIP_MONACO_ASSET_SYNC;
  });

  afterEach(() => {
    fs.rmSync(tmp, { recursive: true, force: true });
    if (originalSkip === undefined) delete process.env.ATOM_SKIP_MONACO_ASSET_SYNC;
    else process.env.ATOM_SKIP_MONACO_ASSET_SYNC = originalSkip;
  });

  test('copies the editor build under public/monaco/vs and stamps the version', () => {
    const source = makeSource(tmp);
    const publicRoot = path.join(tmp, 'public', 'monaco');

    const result = syncMonacoAssets({ source, publicRoot, version: '1.2.3' });

    expect(result.status).toBe('copied');
    expect(fs.readFileSync(path.join(publicRoot, 'vs', 'loader.js'), 'utf8')).toContain('v1');
    expect(fs.existsSync(path.join(publicRoot, 'vs', 'editor', 'editor.main.js'))).toBe(true);
    expect(fs.readFileSync(path.join(publicRoot, '.version'), 'utf8').trim()).toBe('1.2.3');
    // The staging directory is renamed away, never left behind.
    expect(fs.readdirSync(publicRoot).filter((name) => name.includes('.tmp-'))).toEqual([]);
  });

  test('a matching stamp makes repeat runs a no-op', () => {
    const source = makeSource(tmp);
    const publicRoot = path.join(tmp, 'public', 'monaco');
    syncMonacoAssets({ source, publicRoot, version: '1.2.3' });

    const result = syncMonacoAssets({ source, publicRoot, version: '1.2.3' });

    expect(result.status).toBe('current');
  });

  test('an upgraded editor version replaces the stale tree', () => {
    const publicRoot = path.join(tmp, 'public', 'monaco');
    syncMonacoAssets({ source: makeSource(tmp), publicRoot, version: '1.2.3' });

    const upgraded = makeSource(tmp, 'v2');
    const result = syncMonacoAssets({ source: upgraded, publicRoot, version: '1.2.4' });

    expect(result.status).toBe('copied');
    expect(fs.readFileSync(path.join(publicRoot, 'vs', 'loader.js'), 'utf8')).toContain('v2');
    expect(fs.readFileSync(path.join(publicRoot, '.version'), 'utf8').trim()).toBe('1.2.4');
  });

  test('a deleted asset tree is rebuilt even when the stamp survives', () => {
    const source = makeSource(tmp);
    const publicRoot = path.join(tmp, 'public', 'monaco');
    syncMonacoAssets({ source, publicRoot, version: '1.2.3' });
    fs.rmSync(path.join(publicRoot, 'vs'), { recursive: true, force: true });

    const result = syncMonacoAssets({ source, publicRoot, version: '1.2.3' });

    expect(result.status).toBe('copied');
    expect(fs.existsSync(path.join(publicRoot, 'vs', 'loader.js'))).toBe(true);
  });

  test('the explicit skip flag leaves the tree untouched', () => {
    process.env.ATOM_SKIP_MONACO_ASSET_SYNC = '1';
    const publicRoot = path.join(tmp, 'public', 'monaco');

    const result = syncMonacoAssets({ source: makeSource(tmp), publicRoot, version: '1.2.3' });

    expect(result.status).toBe('skipped');
    expect(fs.existsSync(publicRoot)).toBe(false);
  });

  test('a missing editor build fails loudly instead of shipping a broken page', () => {
    expect(() => syncMonacoAssets({
      source: path.join(tmp, 'absent'),
      publicRoot: path.join(tmp, 'public', 'monaco'),
      version: '1.2.3',
    })).toThrow(/missing .*absent/);
  });
});
