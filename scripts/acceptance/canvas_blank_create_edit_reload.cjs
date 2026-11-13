const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Playwright is an existing dependency of the frontend workspace. Resolve it
// from there when this script is run from scripts/ (no root node_modules).
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  ({ chromium } = require(path.join(__dirname, '..', '..', 'frontend-nextjs', 'node_modules', 'playwright')));
}

/**
 * WA-045 — blank canvas create -> edit -> save -> reload on an isolated world.
 *
 * This is the plain-document path the readiness ledger left unproven: the
 * gallery's "New canvas" button (POST /api/canvas), the native Monaco editor,
 * the panel's verified audit-trail save (PUT /api/canvas/{id}), and the
 * /canvas/{id} page's read-back after a real browser reload.
 *
 * Every assertion is exact: the artifact id must agree across the create
 * response, the URL, GET /api/canvas/{id}, and the audit history; the saved
 * text must match byte-for-byte in the PUT body, the durable read-back, and
 * the editor after reload.
 *
 * Env (set by scripts/acceptance/canvas_blank_lifecycle.py):
 *   CANVAS_BLANK_BASE            frontend origin (http://127.0.0.1:PORT)
 *   CANVAS_BLANK_API             backend origin
 *   CANVAS_BLANK_ADMIN_PASSWORD  scratch-admin login, injected by the driver
 *                                through this process's environment
 *   CANVAS_BLANK_OUT             directory for this run's harness JSON
 *   CANVAS_BLANK_MONACO_CDN      optional: "allow" (default) pins the editor
 *                                asset CDN; "deny" refuses every non-loopback
 *                                request and fails if the editor needs it
 *
 * The harness records every request origin. Loopback is the app. In "deny"
 * mode all non-loopback traffic is aborted before it leaves the browser; the
 * editor must render entirely from the frontend's bundled /monaco/vs assets.
 */

const BASE = process.env.CANVAS_BLANK_BASE || 'http://127.0.0.1:3181';
const API = process.env.CANVAS_BLANK_API || 'http://127.0.0.1:8181';
const PW = process.env.CANVAS_BLANK_ADMIN_PASSWORD;
const OUT = process.env.CANVAS_BLANK_OUT
  ? path.resolve(process.env.CANVAS_BLANK_OUT)
  : path.join(__dirname, '..', '..', 'tmp-wa045');
const MONACO_CDN_POLICY = (process.env.CANVAS_BLANK_MONACO_CDN || 'allow').trim().toLowerCase();
if (!['allow', 'deny'].includes(MONACO_CDN_POLICY)) {
  console.error(`FATAL CANVAS_BLANK_MONACO_CDN must be "allow" or "deny", got ${JSON.stringify(MONACO_CDN_POLICY)}`);
  process.exit(2);
}

const EXACT_TEXT = [
  'WA-045 canvas durability check',
  '',
  'Line 1 exact: ORD-WA045-ALPHA',
  'Line 2 exact: 17 * 3 = 51',
  'End marker: WA045-END',
].join('\n');

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const MONACO_CDN_RE = /^https:\/\/cdn\.jsdelivr\.net\/npm\/monaco-editor@[^/]+\/min\/vs\//;

const checks = [];
const record = (name, ok, detail) => {
  checks.push({ name, ok: !!ok, detail });
  console.log((ok ? 'PASS' : 'FAIL'), name, detail === undefined ? '' : JSON.stringify(detail).slice(0, 500));
};
const fail = (name, detail) => record(name, false, detail);

const sha256 = (value) => crypto.createHash('sha256').update(value, 'utf8').digest('hex');

if (!PW) {
  console.error('FATAL CANVAS_BLANK_ADMIN_PASSWORD is required');
  process.exit(2);
}
fs.mkdirSync(OUT, { recursive: true });

async function login(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle', timeout: 120000 });
  await page.getByTestId('login-email-input').waitFor({ state: 'visible', timeout: 60000 });
  await page.waitForTimeout(800);
  await page.getByTestId('login-email-input').fill('admin@example.com');
  await page.getByTestId('login-password-input').fill(PW);
  const loginP = page.waitForResponse(
    (response) => response.url().includes('/api/auth/login') && response.request().method() === 'POST',
    { timeout: 60000 },
  ).catch(() => null);
  await page.getByTestId('login-submit-button').evaluate((el) => el.click());
  const loginResponse = await loginP;
  try {
    await page.waitForURL('**/dashboard', { timeout: 90000 });
  } catch (error) {
    const formError = await page.getByTestId('login-error-message').innerText({ timeout: 1000 }).catch(() => '');
    throw new Error([
      'login did not reach the dashboard',
      `url=${page.url()}`,
      `login_status=${loginResponse ? loginResponse.status() : 'none'}`,
      `form_error=${JSON.stringify(formError).slice(0, 300)}`,
    ].join(' '));
  }
}

async function apiGet(token, pathname) {
  const response = await fetch(API + pathname, {
    headers: { Authorization: 'Bearer ' + token },
  });
  const body = await response.json().catch(() => ({}));
  return { status: response.status, body };
}

/**
 * The displayed editor's model value. The element exposes its model URI in
 * data-uri; fall back to the single model when a host page has several.
 */
async function editorValue(page) {
  const uri = await page.locator('.monaco-editor').first().getAttribute('data-uri');
  return page.evaluate((modelUri) => {
    const monaco = window.monaco;
    if (!monaco || !monaco.editor) return null;
    const models = monaco.editor.getModels();
    const byUri = modelUri
      ? models.find((m) => m.uri.toString() === modelUri)
      : null;
    const model = byUri || models[models.length - 1];
    return model ? model.getValue() : null;
  }, uri);
}

async function waitForEditorValue(page, expected, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let value = null;
  while (Date.now() < deadline) {
    value = await editorValue(page).catch(() => null);
    if (value === expected) return value;
    await page.waitForTimeout(250);
  }
  return value;
}

(async () => {
  const recordFile = path.join(OUT, 'canvas-blank-harness.json');
  const write = (payload) => fs.writeFileSync(recordFile, JSON.stringify(payload, null, 2) + '\n');

  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  page.setDefaultTimeout(60000);
  page.setDefaultNavigationTimeout(120000);

  const pageErrors = [];
  const consoleErrors = [];
  const origins = new Set();
  const nonLoopback = [];
  page.on('pageerror', (error) => pageErrors.push(String(error).slice(0, 300)));
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (/401 \(Unauthorized\)|404 \(Not Found\)|ERR_CANCELED|Failed to load resource/.test(text)) return;
    consoleErrors.push(text.slice(0, 300));
  });
  let localMonacoAssets = 0;
  page.on('request', (request) => {
    let url;
    try { url = new URL(request.url()); } catch { return; }
    if (url.protocol === 'blob:' || url.protocol === 'data:') {
      origins.add(url.protocol);
      return;
    }
    origins.add(url.origin);
    if (['127.0.0.1', 'localhost'].includes(url.hostname)) {
      if (url.pathname.startsWith('/monaco/vs/')) localMonacoAssets += 1;
      return;
    }
    nonLoopback.push({ method: request.method(), url: request.url() });
  });

  // Offline proof: in deny mode nothing leaves the machine. Aborting (rather
  // than only observing) means a CDN regression fails the journey at the
  // editor instead of quietly passing with an unrecorded download.
  const blockedExternal = [];
  if (MONACO_CDN_POLICY === 'deny') {
    await page.route('**/*', async (route) => {
      const request = route.request();
      let url;
      try { url = new URL(request.url()); } catch { return route.continue(); }
      if (url.protocol === 'blob:' || url.protocol === 'data:') return route.continue();
      if (['127.0.0.1', 'localhost'].includes(url.hostname)) return route.continue();
      blockedExternal.push({ method: request.method(), url: request.url() });
      await route.abort('blockedbyclient').catch(() => {});
    });
  }

  let evidence = { status: 'failed', checks };

  try {
    await login(page);
    record('signed in through the login form', true, { origin: BASE });
    await page.evaluate(() => sessionStorage.setItem('atom.onboarding.dismissed', '1'));

    // ── Create: the gallery's own button, not an API shortcut ───────────
    await page.goto(BASE + '/canvas', { waitUntil: 'domcontentloaded', timeout: 120000 });
    const newButton = page.getByTestId('new-blank-canvas-button');
    await newButton.waitFor({ state: 'visible', timeout: 90000 });
    await page.waitForTimeout(1000);
    const createP = page.waitForResponse(
      (response) => response.url().endsWith('/api/canvas') && response.request().method() === 'POST',
      { timeout: 60000 },
    );
    await newButton.evaluate((el) => el.click());
    const createResponse = await createP;
    const createBody = await createResponse.json().catch(() => ({}));
    const canvasId = createBody.canvas_id;
    record('blank canvas created by the UI button', createResponse.status() === 200 && createBody.success === true && UUID_RE.test(canvasId || ''), {
      status: createResponse.status(),
      canvas_id: canvasId,
      url: createBody.url,
    });
    if (!UUID_RE.test(canvasId || '')) throw new Error('create response did not carry a canvas id');

    await page.waitForURL(new RegExp('/canvas/' + canvasId + '$'), { timeout: 90000 });
    const urlId = (page.url().match(/\/canvas\/([^/?#]+)/) || [])[1] || null;
    record('created artifact id is the URL identity', urlId === canvasId, { url: page.url(), canvas_id: canvasId });

    const container = page.getByTestId('canvas-container');
    await container.waitFor({ state: 'attached', timeout: 120000 });
    const editor = page.locator('.monaco-editor').first();
    await editor.waitFor({ state: 'visible', timeout: 120000 });
    record('native document editor rendered for the blank canvas', true, { selector: '.monaco-editor' });

    const token = await page.evaluate(() => localStorage.getItem('auth_token'));
    record('signed-in browser token present', typeof token === 'string' && token.length > 0, { length: (token || '').length });

    const initialRead = await apiGet(token, `/api/canvas/${canvasId}`);
    record('initial durable content is the empty document envelope',
      initialRead.status === 200 && initialRead.body.success === true
        && JSON.stringify(initialRead.body.content) === JSON.stringify({ content: '' }),
      { status: initialRead.status, content: initialRead.body.content, audit_id: initialRead.body.audit_id });
    const createAuditId = initialRead.body.audit_id;
    record('initial audit row is the create event', initialRead.body.action_type === 'create', initialRead.body.action_type);

    const emptyEditor = await waitForEditorValue(page, '', 30000);
    record('editor opens with the exact empty body', emptyEditor === '', { value: emptyEditor });

    // ── Edit: type as a user, then save through the panel ───────────────
    const putP = page.waitForResponse(
      (response) => response.url().includes(`/api/canvas/${canvasId}`) && response.request().method() === 'PUT',
      { timeout: 45000 },
    );
    await editor.click();
    await page.waitForTimeout(250);
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
    await page.keyboard.insertText(EXACT_TEXT);

    let savePath = 'autosave';
    for (let attempt = 0; attempt < 24; attempt++) {
      const button = page.getByRole('button', { name: /Save Changes/ });
      if (await button.count() > 0 && await button.first().isVisible().catch(() => false)
          && !(await button.first().isDisabled().catch(() => true))) {
        await button.first().evaluate((el) => el.click());
        savePath = 'save_changes_button';
        break;
      }
      await page.waitForTimeout(100);
    }

    const put = await putP;
    const putRequest = put.request();
    const putBodyText = putRequest.postData() || '';
    let putBody = null;
    try { putBody = JSON.parse(putBodyText); } catch { putBody = null; }
    const putResponse = await put.json().catch(() => ({}));
    record('edited text reached the durable save endpoint', put.status() === 200 && putResponse.success === true,
      { status: put.status(), save_path: savePath });
    record('save body is the exact native document envelope, byte-for-byte',
      putBody !== null
        && Object.keys(putBody).length === 1
        && putBody.content === EXACT_TEXT,
      { body_keys: putBody ? Object.keys(putBody) : null, content_sha256: sha256(putBody?.content || ''), expected_sha256: sha256(EXACT_TEXT) });
    record('save receipt is verified for this exact canvas',
      putResponse.verification?.status === 'verified'
        && putResponse.canvas_id === canvasId
        && UUID_RE.test(putResponse.audit_id || '')
        && typeof putResponse.operation_id === 'string' && putResponse.operation_id.length > 0,
      {
        verification: putResponse.verification?.status,
        canvas_id: putResponse.canvas_id,
        audit_id: putResponse.audit_id,
        operation_id: putResponse.operation_id,
      });
    record('save bound the prior create revision (optimistic concurrency)',
      putRequest.url().includes('expected_prior_audit_id=' + encodeURIComponent(createAuditId)),
      { expected_prior_audit_id: createAuditId });

    let savedStatus = '';
    for (let attempt = 0; attempt < 40; attempt++) {
      // The final "Saved" indicator intentionally has no data-testid; the
      // testid marks the transient saving/pending/blocked/error states.
      const saved = container.getByText('Saved', { exact: true }).first();
      if (await saved.isVisible({ timeout: 750 }).catch(() => false)) {
        savedStatus = 'Saved';
        break;
      }
      savedStatus = await page.getByTestId('canvas-autosave-status').first()
        .innerText({ timeout: 500 }).catch(() => '');
      await page.waitForTimeout(250);
    }
    record('panel reports the edit saved', /Saved/.test(savedStatus), savedStatus.slice(0, 80));

    // ── Reload: the durable read-back the ledger asks for ───────────────
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.locator('.monaco-editor').first().waitFor({ state: 'visible', timeout: 120000 });
    const reloadedValue = await waitForEditorValue(page, EXACT_TEXT, 60000);
    record('editor value after reload is the exact saved text', reloadedValue === EXACT_TEXT, {
      value_sha256: sha256(reloadedValue || ''),
      expected_sha256: sha256(EXACT_TEXT),
      length: (reloadedValue || '').length,
    });

    const reloadedRead = await apiGet(token, `/api/canvas/${canvasId}`);
    record('GET read-back after reload returns the exact saved envelope',
      reloadedRead.status === 200 && reloadedRead.body.success === true
        && reloadedRead.body.canvas_id === canvasId
        && JSON.stringify(reloadedRead.body.content) === JSON.stringify({ content: EXACT_TEXT })
        && reloadedRead.body.content?.content === EXACT_TEXT,
      {
        status: reloadedRead.status,
        canvas_id: reloadedRead.body.canvas_id,
        content_sha256: sha256(reloadedRead.body.content?.content || ''),
        audit_id: reloadedRead.body.audit_id,
      });
    record('read-back is the update revision the save returned',
      reloadedRead.body.revision_audit_id === putResponse.audit_id
        && reloadedRead.body.audit_id === putResponse.audit_id,
      { revision_audit_id: reloadedRead.body.revision_audit_id, saved_audit_id: putResponse.audit_id });

    const history = await apiGet(token, `/api/canvas/${canvasId}/history`);
    const rows = history.body.history || [];
    const actions = rows.map((row) => row.action_type);
    const latest = rows[0] || {};
    record('audit history belongs to the created artifact', history.status === 200
      && history.body.canvas_id === canvasId
      && rows.every((row) => row.canvas_id === canvasId), { canvas_id: history.body.canvas_id, count: rows.length });
    record('history has exactly the create and update revisions', history.body.count === 2
      && actions.includes('create') && actions.includes('update'), actions);
    record('latest revision carries the exact saved text',
      JSON.stringify(latest.details?.content) === JSON.stringify({ content: EXACT_TEXT })
        && latest.audit_id === putResponse.audit_id,
      { audit_id: latest.audit_id, content_sha256: sha256(latest.details?.content?.content || '') });

    const title = await container.locator('h3').first().innerText().catch(() => '');
    record('canvas title is the created artifact title', title.trim() === 'Untitled canvas', title.trim());
    const versionText = await container.getByText('v2', { exact: true }).count();
    record('reloaded version badge reflects both revisions', versionText > 0, { expected: 'v2', matches: versionText });

    // ── Isolation: no workspace data left the loopback origins ──────────
    const external = nonLoopback.filter((entry) => !MONACO_CDN_RE.test(entry.url));
    const monacoAssets = nonLoopback.filter((entry) => MONACO_CDN_RE.test(entry.url));
    record('no non-loopback request other than pinned Monaco editor assets',
      external.length === 0 && monacoAssets.every((entry) => entry.method === 'GET'),
      {
        external: external.slice(0, 5),
        monaco_asset_requests: monacoAssets.length,
        monaco_asset_policy: MONACO_CDN_POLICY,
      });
    if (MONACO_CDN_POLICY === 'deny') {
      record('Monaco asset CDN was not contacted (deny policy)', monacoAssets.length === 0, monacoAssets.slice(0, 3));
      record('external traffic was refused end-to-end (zero non-loopback attempts)',
        nonLoopback.length === 0 && blockedExternal.length === 0,
        { attempted: nonLoopback.slice(0, 5), blocked: blockedExternal.slice(0, 5) });
      record('editor rendered from the bundled same-origin build', localMonacoAssets > 0, {
        expected_asset_root: '/monaco/vs',
        local_asset_requests: localMonacoAssets,
        non_loopback_requests: nonLoopback.length,
      });
    }
    record('no browser page errors', pageErrors.length === 0, pageErrors.slice(0, 3));

    const passed = checks.every((check) => check.ok);
    evidence = {
      schema: 'atom-canvas-blank-create-edit-reload-1',
      status: passed ? 'passed' : 'failed',
      frontend: BASE,
      backend: API,
      canvas_id: canvasId,
      canvas_url: page.url(),
      title: title.trim(),
      exact_text: EXACT_TEXT,
      exact_text_sha256: sha256(EXACT_TEXT),
      create: {
        status: createResponse.status(),
        canvas_id: canvasId,
        url: createBody.url,
        audit_id: createAuditId,
      },
      save: {
        status: put.status(),
        save_path: savePath,
        request_body: putBody,
        canvas_id: putResponse.canvas_id,
        audit_id: putResponse.audit_id,
        operation_id: putResponse.operation_id,
        verification: putResponse.verification,
        expected_prior_audit_id: createAuditId,
      },
      reload: {
        editor_value_sha256: sha256(reloadedValue || ''),
        get_content_sha256: sha256(reloadedRead.body.content?.content || ''),
        revision_audit_id: reloadedRead.body.revision_audit_id,
        version_badge: 'v2',
        action_types: actions,
        history_count: history.body.count,
      },
      origins: [...origins].sort(),
      non_loopback: nonLoopback.slice(0, 20),
      external_traffic: {
        policy: MONACO_CDN_POLICY,
        blocked: blockedExternal.slice(0, 20),
        blocked_count: blockedExternal.length,
        attempted_count: nonLoopback.length,
        local_monaco_asset_requests: localMonacoAssets,
      },
      page_errors: pageErrors,
      console_errors: consoleErrors,
      checks,
    };
    write(evidence);
    console.log('STATUS', evidence.status.toUpperCase(), `${checks.filter((check) => check.ok).length}/${checks.length}`);
    await browser.close().catch(() => {});
    process.exit(passed ? 0 : 1);
  } catch (error) {
    fail('journey completed without an exception', String(error).slice(0, 500));
    evidence = {
      schema: 'atom-canvas-blank-create-edit-reload-1',
      status: 'failed',
      frontend: BASE,
      backend: API,
      exact_text: EXACT_TEXT,
      exact_text_sha256: sha256(EXACT_TEXT),
      error: String(error).slice(0, 800),
      origins: [...origins].sort(),
      non_loopback: nonLoopback.slice(0, 20),
      external_traffic: {
        policy: MONACO_CDN_POLICY,
        blocked: blockedExternal.slice(0, 20),
        blocked_count: blockedExternal.length,
        attempted_count: nonLoopback.length,
      },
      page_errors: pageErrors,
      console_errors: consoleErrors,
      checks,
    };
    write(evidence);
    await browser.close().catch(() => {});
    process.exit(1);
  }
})().catch((error) => {
  console.error('FATAL', error);
  process.exit(2);
});
