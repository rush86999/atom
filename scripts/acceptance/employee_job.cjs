const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const BASE = process.env.UI_BASE || 'http://127.0.0.1:3120';
const API = 'http://127.0.0.1:8061';
const WORLD = '/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/expanded_core_final_20261028';
const PW = fs.readFileSync(WORLD + '/backend_root/logs/bootstrap_admin_password.txt', 'utf8').trim();
const OUT = process.env.UI_OUT_DIR || path.join(ROOT, 'docs/acceptance/evidence/whole_app_20261028/expanded_core_final_20261028');
const DOWNLOADS = path.join(OUT, 'downloads');
const slices = JSON.parse(fs.readFileSync(path.join(OUT, 'ui_slices.json'), 'utf8'));
const capability = JSON.parse(fs.readFileSync(path.join(OUT, 'capability_ui.json'), 'utf8'));
const checks = [];
const record = (name, ok, detail) => {
  checks.push({ name, ok: !!ok, detail });
  console.log((ok ? 'PASS' : 'FAIL'), name, detail === undefined ? '' : JSON.stringify(detail).slice(0, 600));
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
  for (let i = 0; i < 8; i++) {
    const d = p.locator('[role="dialog"]').first();
    if (await d.count() === 0) { await p.waitForTimeout(300); if (await p.locator('[role="dialog"]').count() === 0) return; continue; }
    const btn = d.getByRole('button', { name: /Start Automating|Next|Finish|Done|Get started|Continue|Close/i }).last();
    if (await btn.count()) { await btn.evaluate(el => el.click()); await p.waitForTimeout(600); }
    else { await p.keyboard.press('Escape'); await p.waitForTimeout(350); }
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
async function openCanvas(p, id, readyTestId) {
  await p.goto(BASE + `/canvas/${id}`, { waitUntil: 'networkidle', timeout: 90000 });
  if (readyTestId) await p.locator(`[data-testid="${readyTestId}"]`).first().waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(p);
  await p.waitForTimeout(800);
}
async function download(p, testid, name) {
  const dlP = p.waitForEvent('download', { timeout: 90000 });
  await p.locator(`[data-testid="${testid}"]`).click();
  const dl = await dlP;
  const target = path.join(DOWNLOADS, name);
  await dl.saveAs(target);
  return target;
}

(async () => {
  const loginApi = await api('POST', '/api/auth/login', { username: 'admin@example.com', password: PW });
  TOKEN = loginApi.body.access_token;
  record('admin login API', loginApi.status === 200 && !!TOKEN, loginApi.status);

  const workbookId = slices.workbook_canvas_id;
  const emailId = slices.email_canvas_id;
  const docId = slices.doc_canvas_id;
  const deckId = slices.pptx_canvas_id;
  const capAUrl = capability.canvas_a.url;
  const capBUrl = capability.canvas_b.url;
  const capAId = capAUrl.split('/').pop();
  const capBId = capBUrl.split('/').pop();
  const agentsResp = await api('GET', `/api/canvas/${capAId}/agents`);
  AGENT = agentsResp.body?.agents?.[0]?.agent_id;
  record('employee attached to job canvas', !!AGENT, AGENT);

  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e).slice(0, 300)));
  await login(page);

  // 1. Teach the employee a task policy through the training surface.
  await openCanvas(page, capAId, 'canvas-side-tab-training');
  await page.locator('[data-testid="canvas-side-tab-training"]').dispatchEvent('click');
  await page.waitForTimeout(2200);
  const lesson = 'For pipeline assessments, approve only Open records with Amount at or above 100; review Open records from 50 to 99; deny Closed records or records below 50. Cite the row and policy.';
  await page.fill('[data-testid="teach-lesson-input"]', lesson);
  await page.fill('[data-testid="teach-topic-input"]', 'pipeline approval policy');
  await page.locator('[data-testid="teach-submit"]').dispatchEvent('click');
  await page.waitForTimeout(3500);
  await page.waitForTimeout(1500);
  const teachCtx = await api('GET', `/api/maturity/training/context?canvas_id=${capAId}`);
  const taught = (teachCtx.body?.teaching_points || []).find((tp) => String(tp.topic || '').includes('pipeline approval policy'));
  record('task policy taught through training UI', !!taught && String(taught.text || taught.lesson || '').includes('approve only Open records'), { count: teachCtx.body?.teaching_points?.length, topic: taught?.topic });

  // 2. Inspect the workbook evidence and calculate in the spreadsheet canvas.
  await openCanvas(page, workbookId, 'excel-cell-/Orders/C2');
  const cell = async (ref) => page.locator(`[data-testid="excel-cell-/Orders/${ref}"]`).inputValue();
  // Normalize the fixture to its imported quantity so the job's own
  // calculation is what changes the total.
  const resetQty = page.locator('[data-testid="excel-cell-/Orders/C2"]');
  await resetQty.fill('4');
  const resetP = page.waitForResponse(r => r.url().includes('/api/v1/office/sync-update') && r.request().method() === 'POST', { timeout: 120000 }).catch(() => null);
  await resetQty.blur();
  await resetP;
  await page.waitForTimeout(2200);
  record('workbook evidence visible before job edit', (await cell('C2')) === '4' && Number(await cell('E6')) === 122.5, { c2: await cell('C2'), e6: await cell('E6') });
  const qty = page.locator('[data-testid="excel-cell-/Orders/C2"]');
  await qty.fill('6');
  const syncP = page.waitForResponse(r => r.url().includes('/api/v1/office/sync-update') && r.request().method() === 'POST', { timeout: 120000 }).catch(() => null);
  await qty.blur();
  await syncP;
  await page.waitForTimeout(2200);
  const jobTotal = Number(await cell('E6'));
  record('employee calculation updated the workbook total', jobTotal === 147.5 && Number(await cell('E2')) === 75, { e2: await cell('E2'), e6: await cell('E6') });
  const workbookJobDownload = await download(page, 'office-download', 'employee-job-workbook.xlsx');

  // 3. Re-run the taught assessment and apply one authorized correction.
  await openCanvas(page, capAId, 'canvas-capability-panel');
  const panelA = page.locator('[data-testid="canvas-capability-panel"]');
  await panelA.getByRole('button', { name: /Data operations/i }).dispatchEvent('click');
  await panelA.locator('[data-testid="capability-ask"]').fill('assess Open rows');
  const assess1P = page.waitForResponse(r => r.url().includes('/capability/assess') && r.request().method() === 'POST', { timeout: 180000 });
  await panelA.locator('[data-testid="capability-assess"]').dispatchEvent('click');
  const assess1 = await (await assess1P).json();
  const decisions1 = Object.fromEntries((assess1.assessments || []).map(a => [a.subject_id, a.decision]));
  record('employee assessment before correction', assess1.certified === true && decisions1['A-101'] === 'APPROVE' && decisions1['A-102'] === 'APPROVE', decisions1);
  // Normalize the affected row first so the correction is a real change.
  await panelA.locator('[data-testid="capability-edit-row"]').fill('5');
  await panelA.locator('[data-testid="capability-edit-column"]').fill('Amount');
  await panelA.locator('[data-testid="capability-edit-value"]').fill('95');
  const resetEditP = page.waitForResponse(r => r.url().includes('/capability/edit') && r.request().method() === 'POST', { timeout: 60000 });
  await panelA.locator('[data-testid="capability-edit"]').dispatchEvent('click');
  await resetEditP;
  await panelA.locator('[data-testid="capability-ask"]').fill('assess Open rows');
  const assessResetP = page.waitForResponse(r => r.url().includes('/capability/assess') && r.request().method() === 'POST', { timeout: 180000 });
  await panelA.locator('[data-testid="capability-assess"]').dispatchEvent('click');
  const assessReset = await (await assessResetP).json();
  const decisionsReset = Object.fromEntries((assessReset.assessments || []).map(a => [a.subject_id, a.decision]));
  record('baseline assessment before correction', assessReset.certified === true && decisionsReset['A-104'] === 'REVIEW', decisionsReset);
  await panelA.locator('[data-testid="capability-edit-row"]').fill('5');
  await panelA.locator('[data-testid="capability-edit-column"]').fill('Amount');
  await panelA.locator('[data-testid="capability-edit-value"]').fill('120');
  const editP = page.waitForResponse(r => r.url().includes('/capability/edit') && r.request().method() === 'POST', { timeout: 60000 });
  await panelA.locator('[data-testid="capability-edit"]').dispatchEvent('click');
  const editBody = await (await editP).json();
  record('authorized correction read back from authoritative store', editBody?.edits?.[0]?.readback_matches === true && String(editBody?.edits?.[0]?.readback) === '120', editBody?.edits);
  await panelA.locator('[data-testid="capability-ask"]').fill('assess Open rows');
  const assess2P = page.waitForResponse(r => r.url().includes('/capability/assess') && r.request().method() === 'POST', { timeout: 180000 });
  await panelA.locator('[data-testid="capability-assess"]').dispatchEvent('click');
  const assess2 = await (await assess2P).json();
  const decisions2 = Object.fromEntries((assess2.assessments || []).map(a => [a.subject_id, a.decision]));
  record('correction changed the affected assessment', assess2.certified === true && decisions2['A-104'] === 'APPROVE', decisions2);

  // 4. Unfamiliar variation: the differently-shaped second canvas.
  await openCanvas(page, capBId, 'canvas-capability-panel');
  const panelB = page.locator('[data-testid="canvas-capability-panel"]');
  await panelB.getByRole('button', { name: /Data operations/i }).dispatchEvent('click');
  await panelB.locator('[data-testid="capability-ask"]').fill('assess Open rows');
  const assessBP = page.waitForResponse(r => r.url().includes('/capability/assess') && r.request().method() === 'POST', { timeout: 180000 });
  await panelB.locator('[data-testid="capability-assess"]').dispatchEvent('click');
  const assessB = await (await assessBP).json();
  const decisionsB = Object.fromEntries((assessB.assessments || []).map(a => [a.subject_id, a.decision]));
  record('unfamiliar variation assessed with different vocabulary', assessB.certified === true && decisionsB['T-900'] === 'ACCEPT' && decisionsB['T-901'] === 'ESCALATE', decisionsB);

  // 5. Produce the reply draft with grounded facts and sources.
  await openCanvas(page, emailId, 'email-import-banner');
  const bodyEditor = page.getByTestId('canvas-email-body-editor');
  await bodyEditor.fill('Hi Maya, ORD-1001 is approved for 6 widgets. The recalculated order total is 147.50. Pipeline review: A-101 APPROVE, A-102 APPROVE, A-104 APPROVE. Source: orders.xlsx Orders rows 2-5; order-detail.csv; pipeline_a.csv. Nothing has been sent; this is the reply draft.');
  const emailSaveP = page.waitForResponse(r => r.url().includes(`/api/canvas/${emailId}`) && r.request().method() === 'PUT', { timeout: 30000 }).catch(() => null);
  await bodyEditor.blur();
  await emailSaveP;
  await page.waitForTimeout(1200);
  await page.reload({ waitUntil: 'networkidle', timeout: 90000 });
  await page.getByTestId('email-import-banner').waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(page);
  const emailBody = await page.getByTestId('canvas-email-body-editor').innerText();
  record('reply draft produced and persisted with grounded facts', emailBody.includes('147.50') && emailBody.includes('A-104 APPROVE') && emailBody.includes('pipeline_a.csv'), emailBody.slice(0, 260));

  // 6. Produce a real document and presentation, then correct the document.
  const genDoc = await api('POST', '/api/chat/to-canvas', {
    content: '# Order 1001 decision memo\n\nMaya Chen requested approval for ORD-1001. The employee approved 6 widgets after the workbook recalculation; the order total is 147.50.\n\n| Subject | Decision | Evidence |\n|---|---|---|\n| A-101 | APPROVE | pipeline_a.csv row 2 |\n| A-102 | APPROVE | pipeline_a.csv row 3 |\n| A-104 | APPROVE | pipeline_a.csv row 5 |\n\n## Sources\n- orders.xlsx Orders rows 2-6\n- order-detail.csv\n- pipeline_a.csv\n',
    title: 'Employee job memo',
    canvas_type: 'office_word',
  });
  record('employee produced a real DOCX through product boundary', genDoc.status < 300 && !!genDoc.body?.canvas_id, genDoc.status);
  await openCanvas(page, genDoc.body.canvas_id, 'docx-text');
  const genDocText = await page.locator('[data-testid="docx-text"]').inputValue();
  const genDocTable = await page.locator('[data-testid="docx-tables"]').innerText();
  record('generated DOCX carries grounded facts and table', genDocText.includes('147.50') && genDocTable.includes('A-101') && genDocTable.includes('APPROVE'), { table: genDocTable.slice(0, 160) });
  const docEditor = page.locator('[data-testid="docx-text"]');
  await docEditor.fill(genDocText + '\nCorrection: final approval confirmed by Maya Chen for 6 widgets.');
  await docEditor.blur();
  await page.waitForTimeout(2600);
  const docJobDownload = await download(page, 'office-download', 'employee-job-memo-corrected.docx');

  const genDeck = await api('POST', '/api/chat/to-canvas', {
    content: 'Slide 1: Order decision\n- ORD-1001 approved for 6 widgets; total 147.50.\n| Subject | Decision |\n|---|---|\n| A-101 | APPROVE |\n| A-102 | APPROVE |\n| A-104 | APPROVE |\nNotes: Sources orders.xlsx, order-detail.csv, pipeline_a.csv.\n\nSlide 2: Recommendation\nProceed with dispatch and send the prepared reply after human review. Source: pipeline_a.csv.\n',
    title: 'Employee job deck',
    canvas_type: 'office_pptx',
  });
  record('employee produced a real PPTX through product boundary', genDeck.status < 300 && !!genDeck.body?.canvas_id, genDeck.status);
  await openCanvas(page, genDeck.body.canvas_id, 'pptx-title-1');
  const deckTitle1 = await page.getByTestId('pptx-title-1').inputValue();
  const deckTitle2 = await page.getByTestId('pptx-title-2').inputValue();
  const deckTable = await page.locator('[data-testid="pptx-tables"]').first().innerText();
  const deckNotes = await page.locator('[data-testid="pptx-notes"]').first().innerText();
  record('generated PPTX has grounded slides, table and sources', deckTitle1 === 'Order decision' && deckTitle2 === 'Recommendation' && deckTable.includes('A-104') && deckNotes.includes('pipeline_a.csv'), { deckTitle1, deckTitle2, deckTable: deckTable.slice(0, 120), deckNotes: deckNotes.slice(0, 120) });
  const deckJobDownload = await download(page, 'office-download', 'employee-job-deck.pptx');

  // 7. API-level durable receipts for the restart verifier.
  const workbookState = await api('GET', `/api/canvas/${workbookId}`);
  const emailState = await api('GET', `/api/canvas/${emailId}`);
  const capAState = await api('GET', `/api/canvas/${capAId}/capability`);
  const capBState = await api('GET', `/api/canvas/${capBId}/capability`);
  const wbSha = workbookState.body?.content?.source_identity?.file_sha256 || workbookState.body?.content?.source_identity?.sha256;
  const emailSha = emailState.body?.content?.source_identity?.sha256 || emailState.body?.content?.source_identity?.file_sha256;
  record('job receipts carry source and artifact identity', !!wbSha && !!emailSha, { workbook: wbSha, email: emailSha });

  const job = {
    status: checks.every(c => c.ok) ? 'pre_restart_passed' : 'failed',
    checks,
    ids: {
      agent_id: AGENT,
      workbook_canvas_id: workbookId,
      email_canvas_id: emailId,
      doc_canvas_id: docId,
      pptx_canvas_id: deckId,
      capability_a_canvas_id: capAId,
      capability_b_canvas_id: capBId,
      generated_doc_canvas_id: genDoc.body?.canvas_id,
      generated_pptx_canvas_id: genDeck.body?.canvas_id,
    },
    expected: {
      workbook_c2: '6', workbook_e6: '147.5',
      email_contains: '147.50',
      cap_a_decision_a104: 'APPROVE',
      cap_b_decision_t901: 'ESCALATE',
      teaching_contains: 'pipeline approval policy',
      doc_correction: 'final approval confirmed',
    },
    downloads: [workbookJobDownload, docJobDownload, deckJobDownload],
    page_errors: pageErrors,
  };
  fs.writeFileSync(path.join(OUT, 'employee_job.json'), JSON.stringify(job, null, 1));
  console.log('STATUS', job.status.toUpperCase(), `${checks.filter(c => c.ok).length}/${checks.length}`);
  await browser.close();
  process.exit(checks.every(c => c.ok) ? 0 : 1);
})().catch(e => {
  console.error('FATAL', e);
  fs.writeFileSync(path.join(OUT, 'employee_job.json'), JSON.stringify({ status: 'fatal', error: String(e), checks }, null, 1));
  process.exit(2);
});
