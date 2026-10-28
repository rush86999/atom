const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const BASE = process.env.UI_BASE || 'http://127.0.0.1:3115';
const API = 'http://127.0.0.1:8061';
const WORLD = '/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/expanded_core_20261028';
const PW = fs.readFileSync(WORLD + '/backend_root/logs/bootstrap_admin_password.txt', 'utf8').trim();
const OUT = process.env.UI_OUT_DIR
  ? path.resolve(process.env.UI_OUT_DIR)
  : path.join(ROOT, 'docs/acceptance/evidence/whole_app_20261028/expanded_core_20261028');
const FIX = path.join(OUT, 'fixtures');
const DOWNLOADS = path.join(OUT, 'downloads');
fs.mkdirSync(DOWNLOADS, { recursive: true });

const checks = [];
const record = (name, ok, detail) => {
  checks.push({ name, ok: !!ok, detail });
  console.log((ok ? 'PASS' : 'FAIL'), name, detail === undefined ? '' : JSON.stringify(detail).slice(0, 500));
};
let TOKEN = null;
let AGENT = null;

async function api(method, p, body) {
  const r = await fetch(API + p, {
    method,
    headers: { 'Content-Type': 'application/json', ...(TOKEN ? { Authorization: 'Bearer ' + TOKEN } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: r.status, body: await r.json().catch(() => ({})) };
}

async function dismiss(p) {
  for (let i = 0; i < 10; i++) {
    const d = p.locator('[role="dialog"]').first();
    if (await d.count() === 0) { await p.waitForTimeout(350); if (await p.locator('[role="dialog"]').count() === 0) return; continue; }
    const btn = d.getByRole('button', { name: /Start Automating|Next|Finish|Done|Get started|Continue|Close/i }).last();
    if (await btn.count()) { await btn.evaluate(el => el.click()); await p.waitForTimeout(700); }
    else { await p.keyboard.press('Escape'); await p.waitForTimeout(400); }
  }
}

async function login(p) {
  await p.goto(BASE + '/login', { waitUntil: 'networkidle', timeout: 90000 });
  if (!/\/login/.test(p.url())) return;
  await p.fill('[data-testid="login-email-input"]', 'admin@example.com');
  await p.fill('[data-testid="login-password-input"]', PW);
  await p.locator('[data-testid="login-submit-button"]').evaluate(el => el.click());
  await p.waitForTimeout(7000);
  await dismiss(p);
}

async function newCanvas(p) {
  await p.goto(BASE + '/canvas', { waitUntil: 'networkidle', timeout: 90000 });
  await p.waitForTimeout(2500);
  await dismiss(p);
  await p.locator('[data-testid="new-blank-canvas-button"]').evaluate(el => el.click());
  await p.waitForTimeout(5000);
  await dismiss(p);
  await p.locator('[data-testid="add-agent-button"], [data-testid="banner-add-agent-button"]').first().evaluate(el => el.click());
  await p.waitForTimeout(1200);
  await p.locator(`[data-testid="attach-agent-option-${AGENT}"]`).dispatchEvent('click');
  await p.waitForTimeout(3000);
  await p.locator('[data-testid="canvas-upload-input"]').waitFor({ state: 'attached', timeout: 60000 });
  return p.url();
}

async function uploadToCanvas(p, file, canvasUrl) {
  if (canvasUrl) await p.goto(canvasUrl, { waitUntil: 'networkidle', timeout: 90000 });
  await p.locator('[data-testid="canvas-upload-input"]').waitFor({ state: 'attached', timeout: 60000 });
  await dismiss(p);
  const respP = p.waitForResponse(r => r.url().includes('/data/upload') && r.request().method() === 'POST', { timeout: 180000 });
  await p.locator('[data-testid="canvas-upload-input"]').setInputFiles(file);
  const resp = await respP;
  const json = await resp.json().catch(() => ({}));
  await p.waitForTimeout(3000);
  return { status: resp.status(), body: json };
}

async function downloadArtifact(p, name) {
  const dlP = p.waitForEvent('download', { timeout: 90000 });
  await p.locator('[data-testid="office-download"]').click();
  const dl = await dlP;
  const target = path.join(DOWNLOADS, name);
  await dl.saveAs(target);
  return target;
}

async function canvasIdFromUrl(url) {
  const m = String(url || '').match(/\/canvas\/([^/?#]+)/);
  return m ? m[1] : null;
}

(async () => {
  const loginApi = await api('POST', '/api/auth/login', { username: 'admin@example.com', password: PW });
  TOKEN = loginApi.body.access_token;
  record('admin login API', loginApi.status === 200 && !!TOKEN, loginApi.status);
  const created = await api('POST', '/api/agents/custom', {
    name: 'Expanded Core Acceptance Hire',
    description: 'UI acceptance hire for common employee materials.',
    category: 'Operations',
    configuration: { system_prompt: 'You work across email, documents, decks and workbooks; cite the source and never claim an action you did not take.' },
    schedule_config: {},
  });
  AGENT = created.body?.data?.agent_id;
  record('agent created through product API', !!AGENT, created.status);

  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e).slice(0, 300)));
  await login(page);

  // ── Workbook canvas ────────────────────────────────────────────────
  const workbookCanvas = await newCanvas(page);
  const up = await uploadToCanvas(page, path.join(FIX, 'orders.xlsx'), workbookCanvas);
  record('workbook uploaded through UI data-loading surface', up.status < 300 && !!up.body?.office_canvas, { status: up.status, canvas: up.body?.office_canvas?.canvas_type });
  const workbookId = up.body?.office_canvas?.canvas_id || await canvasIdFromUrl(page.url());
  await page.goto(BASE + `/canvas/${workbookId}`, { waitUntil: 'networkidle', timeout: 90000 });
  await page.locator('[data-testid="excel-cell-/Orders/A1"]').waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(page);
  record('workbook canvas opened as real XLSX', up.body?.office_canvas?.canvas_type === 'sheets', up.body?.office_canvas?.canvas_type);
  const cell = async (ref) => page.locator(`[data-testid="excel-cell-/Orders/${ref}"]`).inputValue().catch(() => null);
  record('headers and text identifiers preserved', (await cell('A1')) === 'Order ID' && (await cell('A2')) === 'ORD-1001', { a1: await cell('A1'), a2: await cell('A2') });
  record('blank cell preserved as blank', (await cell('C5')) === '', await cell('C5'));
  record('numeric cell preserved as a number', Number(await cell('D2')) === 12.5, await cell('D2'));
  record('formula cell displays computed value', Number(await cell('E2')) === 50, await cell('E2'));

  // Filter (view only) over actual rows.
  await page.getByLabel('Filter column').selectOption({ label: 'Status' });
  await page.getByLabel('Filter value').fill('Open');
  await page.waitForTimeout(300);
  const filterCount = await page.locator('[data-testid="excel-filter-count"]').innerText();
  record('select/filter rows through the canvas UI', filterCount.includes('3 of 6'), filterCount);
  await page.getByLabel('Filter value').fill('');
  await page.getByLabel('Filter column').selectOption({ label: 'No filter' });

  // Edit a precedent value and verify dependent formulas update.
  const qty = page.locator('[data-testid="excel-cell-/Orders/C2"]');
  await qty.fill('5');
  await qty.blur();
  await page.waitForResponse(r => r.url().includes('/api/v1/office/sync-update') && r.request().method() === 'POST', { timeout: 120000 }).catch(() => null);
  await page.waitForTimeout(2500);
  record('authorized cell edit propagated dependent formula', Number(await cell('E2')) === 62.5, await cell('E2'));
  record('dependent grand total recalculated', Number(await cell('E6')) === 135, await cell('E6'));
  await page.getByTestId('excel-cell-/Orders/E6').focus();
  record('formula source preserved separately from computed value', (await page.getByLabel('Formula bar').inputValue()) === '=SUM(E2:E5)', await page.getByLabel('Formula bar').inputValue());
  await page.getByRole('button', { name: 'Notes' }).click();
  await page.waitForTimeout(500);
  record('unrelated sheet preserved', (await page.locator('[data-testid="excel-cell-/Notes/A1"]').inputValue()) === 'Unrelated sheet must survive', await page.locator('[data-testid="excel-cell-/Notes/A1"]').inputValue());
  await page.getByRole('button', { name: 'Orders' }).click();
  const workbookDownload = await downloadArtifact(page, 'orders-after-edit.xlsx');
  record('XLSX download produced a file', fs.statSync(workbookDownload).size > 1000, fs.statSync(workbookDownload).size);

  // ── Email import + reply draft ─────────────────────────────────────
  const emailCanvas = await newCanvas(page);
  const emailUp = await uploadToCanvas(page, path.join(FIX, 'request.eml'), emailCanvas);
  record('EML uploaded and bound as email canvas', emailUp.status < 300 && !!emailUp.body?.email_canvas, { status: emailUp.status, canvas: emailUp.body?.email_canvas?.canvas_id });
  await page.waitForTimeout(3000);
  const emailId = emailUp.body?.email_canvas?.canvas_id || await canvasIdFromUrl(page.url());
  await page.goto(BASE + `/canvas/${emailId}`, { waitUntil: 'networkidle', timeout: 90000 });
  await page.locator('[data-testid="email-import-banner"]').waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(page);
  const banner = await page.locator('[data-testid="email-import-banner"]').innerText().catch(() => '');
  record('sender/recipients/thread visible at UI boundary', banner.includes('maya.chen@example.com') && banner.includes('pilot@atom.test') && banner.includes('ops@example.com'), banner.slice(0, 200));
  const replyTo = await page.getByTestId('canvas-email-to').inputValue();
  record('editable reply draft prefilled with reply recipient', replyTo === 'maya.chen@example.com', replyTo);
  const subj = await page.locator('input[placeholder="Email Subject"]').inputValue();
  record('reply subject preserved', /^Re: Approve ORD-1001/.test(subj), subj);
  const strip = await page.locator('[data-testid="email-attachment-strip"]').innerText();
  record('attachment association preserved in composer', strip.includes('order-detail.csv'), strip.slice(0, 200));
  const bodyEditor = page.getByTestId('canvas-email-body-editor');
  await bodyEditor.fill('Reply draft: ORD-1001 is approved for 4 widgets. Source: order-detail.csv.');
  const saveP = page.waitForResponse(r => r.url().includes(`/api/canvas/${emailId}`) && r.request().method() === 'PUT', { timeout: 30000 }).catch(() => null);
  await bodyEditor.blur();
  await saveP;
  await page.waitForTimeout(1000);
  await page.reload({ waitUntil: 'networkidle', timeout: 90000 });
  await page.getByTestId('email-import-banner').waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(page);
  const bodyAfter = await page.getByTestId('canvas-email-body-editor').innerText().catch(() => '');
  record('reply draft persists across reload', bodyAfter.includes('ORD-1001 is approved'), bodyAfter.slice(0, 160));
  const emailState = await api('GET', `/api/canvas/${emailId}`);
  const imported = emailState.body?.content || {};
  record('imported envelope preserved in durable canvas state', imported.imported_from === 'maya.chen@example.com' && (imported.imported_to || []).includes('pilot@atom.test') && (imported.imported_cc || []).includes('ops@example.com'), { from: imported.imported_from, to: imported.imported_to, cc: imported.imported_cc });
  const history = await api('GET', `/api/canvas/${emailId}/history`);
  const actions = (history.body?.history || []).map((h) => h.action_type);
  record('no send occurred during import/draft', !actions.includes('email_send'), actions);

  // ── DOCX read + edit + download ────────────────────────────────────
  const docCanvas = await newCanvas(page);
  const docUp = await uploadToCanvas(page, path.join(FIX, 'brief.docx'), docCanvas);
  const docId = docUp.body?.office_canvas?.canvas_id || await canvasIdFromUrl(page.url());
  await page.goto(BASE + `/canvas/${docId}`, { waitUntil: 'networkidle', timeout: 90000 });
  await page.locator('[data-testid="docx-text"]').waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(page);
  const docTable = await page.locator('[data-testid="docx-tables"]').innerText();
  record('DOCX table read at UI boundary', docTable.includes('ORD-1001') && docTable.includes('Qty'), docTable.slice(0, 160));
  const docText = page.locator('[data-testid="docx-text"]');
  await docText.click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nCorrection: approved for dispatch.');
  await docText.blur();
  await page.waitForTimeout(3000);
  const docDownload = await downloadArtifact(page, 'brief-corrected.docx');
  record('DOCX corrected artifact downloaded', fs.statSync(docDownload).size > 1000, fs.statSync(docDownload).size);

  // Generate a real DOCX through the product boundary.
  const genDoc = await api('POST', '/api/chat/to-canvas', {
    content: '# Order decision memo\n\nORD-1001 is approved for 4 widgets at 12.50 each; line total 50.00.\n\n| Order | Qty | Line total |\n|---|---|---|\n| ORD-1001 | 4 | 50.00 |\n| ORD-1002 | 2 | 60.00 |\n\n## Sources\n- orders.xlsx Orders rows 2-3\n- order-detail.csv\n',
    title: 'Order decision memo',
    canvas_type: 'office_word',
  });
  record('DOCX generated through product boundary', genDoc.status < 300 && !!genDoc.body?.canvas_id, genDoc.status);
  if (genDoc.body?.canvas_id) {
    await page.goto(BASE + `/canvas/${genDoc.body.canvas_id}`, { waitUntil: 'networkidle', timeout: 90000 });
    await page.locator('[data-testid="docx-text"]').waitFor({ state: 'attached', timeout: 90000 });
    await dismiss(page);
    const genTable = await page.locator('[data-testid="docx-tables"]').innerText();
    const genText = await page.locator('[data-testid="docx-text"]').inputValue();
    record('generated DOCX has requested headings and real table', genText.includes('Order decision memo') && genTable.includes('ORD-1001') && genTable.includes('50.00'), { table: genTable.slice(0, 120) });
    const genDownload = await downloadArtifact(page, 'generated-order-memo.docx');
    record('generated DOCX downloadable', fs.statSync(genDownload).size > 1000, fs.statSync(genDownload).size);
  }

  // ── PPTX read + edit + download ────────────────────────────────────
  const deckCanvas = await newCanvas(page);
  const deckUp = await uploadToCanvas(page, path.join(FIX, 'brief.pptx'), deckCanvas);
  const deckId = deckUp.body?.office_canvas?.canvas_id || await canvasIdFromUrl(page.url());
  await page.goto(BASE + `/canvas/${deckId}`, { waitUntil: 'networkidle', timeout: 90000 });
  await page.locator('[data-testid="pptx-title-1"]').waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(page);
  record('PPTX slide order/title read', (await page.getByTestId('pptx-title-1').inputValue()) === 'Order briefing' && (await page.getByTestId('pptx-title-2').inputValue()) === 'Risk', { s1: await page.getByTestId('pptx-title-1').inputValue(), s2: await page.getByTestId('pptx-title-2').inputValue() });
  const deckTables = await page.locator('[data-testid="pptx-tables"]').first().innerText();
  record('PPTX table read at UI boundary', deckTables.includes('ORD-1001') && deckTables.includes('Qty'), deckTables.slice(0, 160));
  const notes = await page.locator('[data-testid="pptx-notes"]').first().innerText();
  record('PPTX speaker notes read at UI boundary', notes.includes('orders.xlsx'), notes.slice(0, 160));
  const slide2 = page.getByTestId('pptx-content-2');
  await slide2.fill((await slide2.inputValue()) + ' Correction: confirm stock before dispatch.');
  await slide2.blur();
  await page.waitForTimeout(3000);
  const deckDownload = await downloadArtifact(page, 'brief-corrected.pptx');
  record('PPTX corrected artifact downloaded', fs.statSync(deckDownload).size > 1000, fs.statSync(deckDownload).size);

  const genDeck = await api('POST', '/api/chat/to-canvas', {
    content: 'Slide 1: Order summary\n- Approved ORD-1001 for 4 widgets; line total 50.00.\n| Order | Qty | Line total |\n|---|---|---|\n| ORD-1001 | 4 | 50.00 |\n| ORD-1002 | 2 | 60.00 |\nNotes: Source orders.xlsx Orders rows 2-3 and order-detail.csv.\n\nSlide 2: Recommendation\nProceed with dispatch after stock confirmation. Source: orders.xlsx Notes.\n',
    title: 'Order review deck',
    canvas_type: 'office_pptx',
  });
  record('PPTX generated through product boundary', genDeck.status < 300 && !!genDeck.body?.canvas_id, genDeck.status);
  if (genDeck.body?.canvas_id) {
    await page.goto(BASE + `/canvas/${genDeck.body.canvas_id}`, { waitUntil: 'networkidle', timeout: 90000 });
    await page.locator('[data-testid="pptx-title-1"]').waitFor({ state: 'attached', timeout: 90000 });
    await dismiss(page);
    record('generated PPTX has correct slide order', (await page.getByTestId('pptx-title-1').inputValue()) === 'Order summary' && (await page.getByTestId('pptx-title-2').inputValue()) === 'Recommendation', { s1: await page.getByTestId('pptx-title-1').inputValue(), s2: await page.getByTestId('pptx-title-2').inputValue() });
    const genDeckTable = await page.locator('[data-testid="pptx-tables"]').first().innerText();
    record('generated PPTX contains a real table', genDeckTable.includes('ORD-1001') && genDeckTable.includes('50.00'), genDeckTable.slice(0, 120));
    const genDeckNotes = await page.locator('[data-testid="pptx-notes"]').first().innerText();
    record('generated PPTX carries source notes', genDeckNotes.includes('orders.xlsx'), genDeckNotes.slice(0, 160));
    const genDeckDownload = await downloadArtifact(page, 'generated-order-deck.pptx');
    record('generated PPTX downloadable', fs.statSync(genDeckDownload).size > 1000, fs.statSync(genDeckDownload).size);
  }

  record('no browser page errors', pageErrors.length === 0, pageErrors.slice(0, 3));
  fs.writeFileSync(path.join(OUT, 'ui_slices.json'), JSON.stringify({
    status: checks.every(c => c.ok) ? 'passed' : 'failed',
    checks,
    workbook_canvas_id: workbookId,
    email_canvas_id: emailId,
    doc_canvas_id: docId,
    pptx_canvas_id: deckId,
    downloads: fs.readdirSync(DOWNLOADS),
    page_errors: pageErrors,
  }, null, 1));
  console.log('STATUS', checks.every(c => c.ok) ? 'PASS' : 'FAIL', `${checks.filter(c => c.ok).length}/${checks.length}`);
  await browser.close();
  process.exit(checks.every(c => c.ok) ? 0 : 1);
})().catch(e => {
  console.error('FATAL', e);
  fs.writeFileSync(path.join(OUT, 'ui_slices.json'), JSON.stringify({ status: 'fatal', error: String(e), checks }, null, 1));
  process.exit(2);
});
