/**
 * Every Monaco editor surface must opt into the bundled build.
 *
 * The loader's default is the jsDelivr CDN. A new editor host that imports
 * `@monaco-editor/react` without calling `configureLocalMonaco()` would look
 * fine online and fail exactly where the offline promise matters (air-gapped
 * install, desktop bundle, WA-045 acceptance with external traffic refused).
 * This guard makes that omission a test failure instead of a silent fallback.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SOURCE_ROOTS = ['components', 'pages'];
const SKIP_DIRS = new Set(['__tests__', '__mocks__', 'node_modules']);
const EDITOR_IMPORT = /from\s+['"]@monaco-editor\/react['"]/;

function walk(dir, found = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const target = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      walk(target, found);
    } else if (/\.(ts|tsx|js|jsx)$/.test(entry.name)) {
      found.push(target);
    }
  }
  return found;
}

const sources = SOURCE_ROOTS.flatMap((root) => walk(path.join(ROOT, root)));
const editorFiles = sources.filter((file) => EDITOR_IMPORT.test(fs.readFileSync(file, 'utf8')));

describe('Monaco editor import surfaces', () => {
  test('at least the canvas document editor is discovered', () => {
    expect(editorFiles.map((file) => path.relative(ROOT, file)))
      .toContain(path.join('components', 'canvas', 'CanvasPanel.tsx'));
  });

  test('every surface that renders the editor configures the local build', () => {
    expect(editorFiles.length).toBeGreaterThan(0);
    for (const file of editorFiles) {
      expect({
        file: path.relative(ROOT, file),
        local: fs.readFileSync(file, 'utf8').includes('configureLocalMonaco'),
      }).toEqual({ file: path.relative(ROOT, file), local: true });
    }
  });

  test('the Next config materializes the bundled assets for dev and build', () => {
    expect(fs.readFileSync(path.join(ROOT, 'next.config.js'), 'utf8'))
      .toContain('syncMonacoAssets');
  });
});
