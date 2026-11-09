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
require.extensions['.ts'] = (module, filename) => {
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText;
  module._compile(compiled, filename);
};
function loadRoute(relative) {
  return require(path.join(root, 'pages/api/v1', relative + '.ts')).default;
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

async function invoke(name, method, extras = {}) {
  let status, payload;
  const req = { method, query: {}, headers: {}, cookies: {}, ...extras };
  const res = { status(value) { status = value; return this; }, json(value) { payload = value; return this; }, setHeader() {} };
  await routes[name](req, res);
  return { status, payload };
}
for (const [name, method, query] of [['tasks', 'GET', {}], ['task', 'PUT', { id: 'record?opaque' }], ['projects', 'POST', {}], ['project', 'PUT', { id: 'project#opaque' }]]) {
  test(`authenticated ${name} forwards exact request once and preserves backend verdict`, async () => {
    const priorFetch = global.fetch, priorBase = process.env.BACKEND_URL;
    const observed = [];
    process.env.BACKEND_URL = 'https://controlled-backend.invalid';
    const body = { title: 'actual material', workspace_id: 'untrusted body scope' };
    global.fetch = async (url, options) => {
      observed.push({ url, options });
      return { status: 409, json: async () => ({ code: 'AUTHORITATIVE_CONFLICT' }) };
    };
    try {
      const response = await invoke(name, method, { query, cookies: { auth_token: 'controlled-session' }, body });
      assert.deepEqual(response, { status: 409, payload: { code: 'AUTHORITATIVE_CONFLICT' } });
      assert.equal(observed.length, 1);
      assert.equal(observed[0].options.headers.Authorization, 'Bearer controlled-session');
      assert.equal(observed[0].options.method, method);
      assert.equal(observed[0].options.redirect, 'error');
      if (method !== 'GET') assert.deepEqual(JSON.parse(observed[0].options.body), body);
      if (query.id) assert.equal(new URL(observed[0].url).pathname.split('/').at(-1), encodeURIComponent(query.id));
    } finally {
      global.fetch = priorFetch;
      if (priorBase === undefined) delete process.env.BACKEND_URL; else process.env.BACKEND_URL = priorBase;
    }
  });
}
test('mutation confirmation loss returns unknown and never resends', async () => {
  const priorFetch = global.fetch, priorBase = process.env.BACKEND_URL;
  process.env.BACKEND_URL = 'https://controlled-backend.invalid';
  let calls = 0;
  global.fetch = async () => { calls++; throw new Error('controlled confirmation loss'); };
  try {
    const result = await invoke('tasks', 'POST', { headers: { authorization: 'Bearer controlled-session' }, body: { title: 'once' } });
    assert.equal(calls, 1);
    assert.equal(result.status, 503);
    assert.equal(result.payload.effect, 'unknown');
    assert.equal(result.payload.replay, 'do_not_repeat');
    assert.ok(!JSON.stringify(result).includes('controlled confirmation loss'));
  } finally {
    global.fetch = priorFetch;
    if (priorBase === undefined) delete process.env.BACKEND_URL; else process.env.BACKEND_URL = priorBase;
  }
});
test('dot-segment record ids cannot change the authoritative target path', async () => {
  for (const name of ['task', 'project']) {
    for (const id of ['.', '..']) {
      const result = await invoke(name, 'PUT', { query: { id }, headers: { authorization: 'Bearer controlled-session' } });
      assert.equal(result.status, 400);
    }
  }
});
