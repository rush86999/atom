const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const BASE = process.env.UI_BASE || 'http://127.0.0.1:3121';
const API = 'http://127.0.0.1:8061';
const WORLD = '/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/expanded_core_final_20261028';
const PW = fs.readFileSync(WORLD + '/backend_root/logs/bootstrap_admin_password.txt', 'utf8').trim();
const OUT = process.env.UI_OUT_DIR || path.join(ROOT, 'docs/acceptance/evidence/whole_app_20261028/expanded_core_final_20261028');
const DOWNLOADS = path.join(OUT, 'downloads');
const job = JSON.parse(fs.readFileSync(path.join(OUT, 'employee_job.json'), 'utf8'));
const checks = [];
const record = (name, ok, detail) => {
  checks.push({ name, ok: !!ok, detail });
  console.log((ok ? 'PASS' : 'FAIL'), name, detail === undefined ? '' : JSON.stringify(detail).slice(0, 600));
};
let TOKEN = null;

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
  await p.locator(`[data-testid="${readyTestId}"]`).first().waitFor({ state: 'attached', timeout: 90000 });
  await dismiss(p);
  await p.waitForTimeout(900);
}
async function download(p, name) {
  const dlP = p.waitForEvent('download', { timeout: 90000 });
  await p.locator('[data-testid="office-download"]').click();
  const dl = await dlP;
  const target = path.join(DOWNLOADS, name);
  await dl.saveAs(target);
  return target;
}

(async () => {
  const loginApi = await api('POST', '/api/auth/login', { username: 'admin@example.com', password: PW });
  TOKEN = loginApi.body.access_token;
  record('admin login after restart', loginApi.status === 200 && !!TOKEN, loginApi.status);
  const ids = job.ids;

  // Teaching survives.
  const teachCtx = await api('GET', `/api/maturity/training/context?canvas_id=${ids.capability_a_canvas_id}`);
  const taught = (teachCtx.body?.teaching_points || []).find((tp) => String(tp.topic || '').includes('pipeline approval policy'));
  record('teaching survives restart', !!taught && String(taught.text || '').includes('approve only Open records'), { topic: taught?.topic, id: taught?.id });

  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e).slice(0, 300)));
  await login(page);

  // Workbook state survives.
  await openCanvas(page, ids.workbook_canvas_id, 'excel-cell-/Orders/C2');
  const cell = async (ref) => page.locator(`[data-testid="excel-cell-/Orders/${ref}"]`).inputValue();
  record('workbook values survive restart', (await cell('C2')) === '6' && Number(await cell('E6')) === 147.5, { c2: await cell('C2'), e6: await cell('E6') });
  await page.getByTestId('excel-cell-/Orders/E6').focus();
  record('workbook formulas survive restart', (await page.getByLabel('Formula bar').inputValue()) === '=SUM(E2:E5)', await page.getByLabel('Formula bar').inputValue());
  await page.getByRole('button', { name: 'Notes' }).click();
  await page.waitForTimeout(400);
  const notesA1 = await page.locator('[data-testid="excel-cell-/Notes/A1"]').inputValue();
  record('unrelated workbook sheet survives restart', notesA1 === 'Unrelated sheet must survive', notesA1);
  const workbookDownload = await download(page, 'employee-job-workbook-after-restart.xlsx');

  // Email draft and references survive; no send occurred.
  await openCanvas(page, ids.email_canvas_id, 'email-import-banner');
  const emailBody = await page.getByTestId('canvas-email-body-editor').innerText();
  const banner = await page.locator('[data-testid="email-import-banner"]').innerText();
  const strip = await page.locator('[data-testid="email-attachment-strip"]').innerText();
  record('reply draft survives restart', emailBody.includes('147.50') && emailBody.includes('pipeline_a.csv'), emailBody.slice(0, 220));
  record('email source references survive restart', banner.includes('maya.chen@example.com') && strip.includes('order-detail.csv'), { banner: banner.slice(0, 140), attachment: strip.slice(0, 80) });
  const emailHistory = await api('GET', `/api/canvas/${ids.email_canvas_id}/history`);
  record('drafting after restart did not send', !(emailHistory.body?.history || []).some((h) => h.action_type === 'email_send'), (emailHistory.body?.history || []).map((h) => h.action_type));

  // Capability manifests and corrected state survive; assessments still run.
  const capA = await api('GET', `/api/canvas/${ids.capability_a_canvas_id}/capability`);
  const capB = await api('GET', `/api/canvas/${ids.capability_b_canvas_id}/capability`);
  record('first capability manifest survives restart', capA.body?.manifest?.task_policy?.includes('Approve Amount') && capA.body?.revision >= 3, { revision: capA.body?.revision, policy: capA.body?.policy_revision });
  record('second capability manifest survives restart', capB.body?.manifest?.decision_options?.includes('ESCALATE') && capB.body?.revision >= 2, { revision: capB.body?.revision, decisions: capB.body?.manifest?.decision_options });
  const calcA = await api('POST', `/api/canvas/${ids.capability_a_canvas_id}/capability/calculate`, { ask: 'sum Amount for Open rows' });
  record('corrected calculation survives restart', calcA.body?.total_values?.['(unstated)'] === '350.00', calcA.body?.total_values);
  const assessA = await api('POST', `/api/canvas/${ids.capability_a_canvas_id}/capability/assess`, { ask: 'assess Open rows' });
  const decisionsA = Object.fromEntries((assessA.body?.assessments || []).map(a => [a.subject_id, a.decision]));
  record('assessment still certifies after restart', assessA.body?.certified === true && decisionsA['A-104'] === 'APPROVE', decisionsA);
  record('post-restart assessment used DeepSeek Flash', assessA.body?.route?.served_model === 'deepseek-flash' && assessA.body?.route?.served_provider === 'deepseek', { model: assessA.body?.route?.served_model, provider: assessA.body?.route?.served_provider });
  const assessB = await api('POST', `/api/canvas/${ids.capability_b_canvas_id}/capability/assess`, { ask: 'assess Open rows' });
  const decisionsB = Object.fromEntries((assessB.body?.assessments || []).map(a => [a.subject_id, a.decision]));
  record('unfamiliar variation still certifies after restart', assessB.body?.certified === true && decisionsB['T-901'] === 'ESCALATE', decisionsB);

  // Deliverables survive and reopen/download.
  await openCanvas(page, ids.generated_doc_canvas_id, 'docx-text');
  const docText = await page.locator('[data-testid="docx-text"]').inputValue();
  const docTable = await page.locator('[data-testid="docx-tables"]').innerText();
  record('generated document survives restart', docText.includes('147.50') && docText.includes('Correction: final approval confirmed') && docTable.includes('A-104'), { correction: docText.includes('Correction: final approval confirmed'), table: docTable.slice(0, 140) });
  const docDownload = await download(page, 'employee-job-memo-after-restart.docx');

  await openCanvas(page, ids.generated_pptx_canvas_id, 'pptx-title-1');
  const deckTitle1 = await page.getByTestId('pptx-title-1').inputValue();
  const deckTitle2 = await page.getByTestId('pptx-title-2').inputValue();
  const deckTable = await page.locator('[data-testid="pptx-tables"]').first().innerText();
  const deckNotes = await page.locator('[data-testid="pptx-notes"]').first().innerText();
  record('generated presentation survives restart', deckTitle1 === 'Order decision' && deckTitle2 === 'Recommendation' && deckTable.includes('A-104') && deckNotes.includes('pipeline_a.csv'), { deckTitle1, deckTitle2, table: deckTable.slice(0, 100) });
  const deckDownload = await download(page, 'employee-job-deck-after-restart.pptx');

  record('no browser page errors after restart', pageErrors.length === 0, pageErrors.slice(0, 3));
  const out = {
    status: checks.every(c => c.ok) ? 'passed' : 'failed',
    checks,
    downloads: [workbookDownload, docDownload, deckDownload],
    teaching_point_id: taught?.id,
    page_errors: pageErrors,
  };
  fs.writeFileSync(path.join(OUT, 'employee_job_after_restart.json'), JSON.stringify(out, null, 1));
  console.log('STATUS', out.status.toUpperCase(), `${checks.filter(c => c.ok).length}/${checks.length}`);
  await browser.close();
  process.exit(out.status === 'passed' ? 0 : 1);
})().catch(e => {
  console.error('FATAL', e);
  fs.writeFileSync(path.join(OUT, 'employee_job_after_restart.json'), JSON.stringify({ status: 'fatal', error: String(e), checks }, null, 1));
  process.exit(2);
});
