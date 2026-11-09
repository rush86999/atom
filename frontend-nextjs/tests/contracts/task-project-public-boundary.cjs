// Controlled handler boundary: real route bytes and real scratch files. No live DB.
const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const ts = require(process.env.ATOM_TYPESCRIPT_MODULE || 'typescript');
const root = path.resolve(__dirname, '../..');
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'atom-web-task-boundary-'));
const originalCwd = process.cwd();
fs.mkdirSync(path.join(scratch, 'data'));
fs.writeFileSync(path.join(scratch, 'data/tasks.json'), JSON.stringify([{ id: 'private-task', title: 'private account task' }]));
fs.writeFileSync(path.join(scratch, 'data/projects.json'), JSON.stringify([{ id: 'private-project', name: 'private account project' }]));
process.chdir(scratch);
after(() => { process.chdir(originalCwd); });
function loadRoute(relative) {
  const source = path.join(root, 'pages/api/v1', relative + '.ts');
  const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText;
  const output = path.join(scratch, relative.replaceAll('/', '-') + '.cjs');
  fs.writeFileSync(output, compiled);
  return require(output).default;
}
const routes = {
  tasks: loadRoute('tasks'), task: loadRoute('tasks/[id]'),
  projects: loadRoute('projects'), project: loadRoute('projects/[id]'),
};
for (const [name, method, id] of [
  ['tasks', 'GET'], ['tasks', 'POST'], ['task', 'PUT', 'private-task'], ['task', 'DELETE', 'private-task'],
  ['projects', 'GET'], ['projects', 'POST'], ['project', 'PUT', 'private-project'],
]) {
  test(`anonymous ${method} ${name} refuses without reading or changing private records`, async () => {
    const before = ['tasks', 'projects'].map(x => fs.readFileSync(path.join(scratch, `data/${x}.json`), 'utf8'));
    let status = 200, payload;
    const req = { method, query: id ? { id } : {}, headers: {}, cookies: {}, body: { title: 'unauthorized change', name: 'unauthorized project' } };
    const res = { status(value) { status = value; return this; }, json(value) { payload = value; return this; }, setHeader() {} };
    await routes[name](req, res);
    assert.equal(status, 401, JSON.stringify({ status, payload }));
    assert.ok(!JSON.stringify(payload).includes('private account'));
    assert.deepEqual(['tasks', 'projects'].map(x => fs.readFileSync(path.join(scratch, `data/${x}.json`), 'utf8')), before);
  });
}
