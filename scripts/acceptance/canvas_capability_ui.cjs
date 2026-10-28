const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const BASE = process.env.UI_BASE || 'http://127.0.0.1:3119';
const API = 'http://127.0.0.1:8061';
const WORLD = '/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/expanded_core_final_20261028';
const PW = fs.readFileSync(WORLD + '/backend_root/logs/bootstrap_admin_password.txt', 'utf8').trim();
const OUT = process.env.UI_OUT_DIR || path.join(ROOT, 'docs/acceptance/evidence/whole_app_20261028/expanded_core_final_20261028');
const FIX = path.join(OUT, 'fixtures');
const DOWNLOADS = path.join(OUT, 'downloads');
fs.mkdirSync(DOWNLOADS, { recursive: true });
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

async function newCanvas(p) {
  await p.goto(BASE + '/canvas', { waitUntil: 'networkidle', timeout: 90000 });
  await p.waitForTimeout(2500);
  await dismiss(p);
  await p.locator('[data-testid="new-blank-canvas-button"]').evaluate(el => el.click());
  await p.waitForTimeout(4500);
  await dismiss(p);
  await p.locator('[data-testid="add-agent-button"], [data-testid="banner-add-agent-button"]').first().evaluate(el => el.click());
  await p.waitForTimeout(1200);
  await p.locator(`[data-testid="attach-agent-option-${AGENT}"]`).dispatchEvent('click');
  await p.waitForTimeout(2500);
  await p.locator('[data-testid="canvas-capability-panel"]').waitFor({ state: 'attached', timeout: 60000 });
  return p.url();
}

async function openPanel(p) {
  const panel = p.locator('[data-testid="canvas-capability-panel"]');
  await panel.waitFor({ state: 'attached', timeout: 60000 });
  const button = panel.getByRole('button', { name: /Data operations/i });
  await button.dispatchEvent('click');
  await p.waitForTimeout(400);
}

async function configure(p, manifest) {
  const panel = p.locator('[data-testid="canvas-capability-panel"]');
  if (await panel.locator('[data-testid="capability-enable"]').count()) {
    await panel.locator('[data-testid="capability-enable"]').dispatchEvent('click');
    await p.waitForTimeout(1200);
  }
  await panel.locator('[data-testid="capability-manifest"]').fill(JSON.stringify(manifest, null, 2));
  await panel.locator('[data-testid="capability-save-manifest"]').dispatchEvent('click');
  await p.waitForTimeout(1500);
  const effective = await panel.locator('[data-testid="capability-effective"]').innerText();
  return effective;
}

async function bind(p, file) {
  const panel = p.locator('[data-testid="canvas-capability-panel"]');
  const respP = p.waitForResponse(r => r.url().includes('/capability/bind') && r.request().method() === 'POST', { timeout: 120000 });
  await panel.locator('input[type="file"]').setInputFiles(file);
  const resp = await respP;
  const body = await resp.json().catch(() => ({}));
  await p.waitForTimeout(1800);
  return { status: resp.status(), body };
}

async function runOp(p, buttonTestId, ask, waitText) {
  const panel = p.locator('[data-testid="canvas-capability-panel"]');
  await panel.locator('[data-testid="capability-ask"]').fill(ask);
  const respP = p.waitForResponse(r => r.url().includes(`/capability/${buttonTestId}`) && r.request().method() === 'POST', { timeout: 180000 }).catch(() => null);
  await panel.locator(`[data-testid="capability-${buttonTestId}"]`).dispatchEvent('click');
  const resp = await respP;
  const body = resp ? await resp.json().catch(() => ({})) : {};
  await p.waitForTimeout(600);
  const text = await panel.locator('[data-testid="capability-result"]').innerText().catch(() => '');
  if (waitText) record(`result rendered for ${buttonTestId}`, text.includes(waitText), text.slice(0, 400));
  return { status: resp?.status(), body, text };
}

(async () => {
  const loginApi = await api('POST', '/api/auth/login', { username: 'admin@example.com', password: PW });
  TOKEN = loginApi.body.access_token;
  record('admin login API', loginApi.status === 200 && !!TOKEN, loginApi.status);
  const created = await api('POST', '/api/agents/custom', {
    name: 'Capability Acceptance Hire',
    description: 'Runs user-created canvas operations.',
    category: 'Operations',
    configuration: { system_prompt: 'You assess bound rows under the task policy and never invent sources.' },
    schedule_config: {},
  });
  AGENT = created.body?.data?.agent_id;
  record('employee created through product API', !!AGENT, created.status);

  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e).slice(0, 300)));
  await login(page);
  const panel = page.locator('[data-testid="canvas-capability-panel"]');

  // ── Canvas A ───────────────────────────────────────────────────────
  const urlA = await newCanvas(page);
  record('first user-created canvas created through UI', /\/canvas\//.test(urlA), urlA);
  await openPanel(page);
  const manifestA = {
    schema_version: 1,
    base_component: 'table',
    operations: ['read', 'select', 'calculate', 'assess', 'edit', 'export', 'bind'],
    data_binding: { subject_field: 'Ref', measure_field: 'Amount', status_field: 'Status' },
    editable_fields: ['Amount', 'Status'],
    teaching_binding: { agent_id: AGENT, scope_id: 'task-a' },
    decision_options: ['APPROVE', 'REVIEW', 'DENY'],
    task_policy: 'Approve Amount >= 100 when Status is Open. Review 50-99. Deny below 50 or Closed.',
    outputs: ['xlsx'],
    required_approvals: [],
  };
  await configure(page, manifestA);
  const bindA = await bind(page, path.join(FIX, 'pipeline_a.csv'));
  const effA = await panel.locator('[data-testid="capability-effective"]').innerText();
  record('manifest installed and effective operations rendered', effA.includes('assess') && effA.includes('edit'), effA);
  record('dataset bound through UI', bindA.status < 300 && bindA.body?.row_count === 4, { status: bindA.status, rows: bindA.body?.row_count });

  const selectA = await runOp(page, 'select', 'list Open rows with Ref and Amount', 'A-101');
  // The generic table selection may render a compact result; verify source identity instead.
  record('selection receipt carries source identity', selectA.body?.source?.source_version && selectA.body?.selected_count >= 1, { selected: selectA.body?.selected_count, source: selectA.body?.source?.source_version });
  const calcA = await runOp(page, 'calculate', 'sum Amount for Open rows', '290');
  record('deterministic calculation over full dataset', calcA.body?.total_values?.['(unstated)'] === '290.00' && calcA.body?.selected_count === 3, { total: calcA.body?.total_values, selected: calcA.body?.selected_count });
  const assessA = await runOp(page, 'assess', 'assess Open rows', 'APPROVE');
  const decisionsA = Object.fromEntries((assessA.body?.assessments || []).map(a => [a.subject_id, a.decision]));
  record('assessment certified with task-defined decisions', assessA.body?.certified === true && decisionsA['A-101'] === 'APPROVE' && decisionsA['A-102'] === 'REVIEW' && decisionsA['A-104'] === 'REVIEW', decisionsA);
  record('assessment served DeepSeek Flash', assessA.body?.route?.served_model === 'deepseek-flash' && assessA.body?.route?.served_provider === 'deepseek', { model: assessA.body?.route?.served_model, provider: assessA.body?.route?.served_provider });

  await panel.locator('[data-testid="capability-edit-row"]').fill('3');
  await panel.locator('[data-testid="capability-edit-column"]').fill('Amount');
  await panel.locator('[data-testid="capability-edit-value"]').fill('110');
  const editRespP = page.waitForResponse(r => r.url().includes('/capability/edit') && r.request().method() === 'POST', { timeout: 60000 });
  await panel.locator('[data-testid="capability-edit"]').dispatchEvent('click');
  const editResp = await editRespP;
  const editBody = await editResp.json().catch(() => ({}));
  await page.waitForTimeout(800);
  record('authorized edit applied with authoritative readback', editBody?.success === true && String(editBody?.edits?.[0]?.readback) === '110' && editBody?.edits?.[0]?.readback_matches === true, editBody?.edits);
  const calcA2 = await runOp(page, 'calculate', 'sum Amount for Open rows', '325');
  record('edit changed the deterministic total', calcA2.body?.total_values?.['(unstated)'] === '325.00', calcA2.body?.total_values);
  const assessA2 = await runOp(page, 'assess', 'assess Open rows', 'APPROVE');
  const decisionsA2 = Object.fromEntries((assessA2.body?.assessments || []).map(a => [a.subject_id, a.decision]));
  record('re-assessment uses the corrected state', assessA2.body?.certified === true && decisionsA2['A-102'] === 'APPROVE', decisionsA2);

  const dlP = page.waitForEvent('download', { timeout: 90000 });
  await panel.locator('[data-testid="capability-export"]').dispatchEvent('click');
  const dl = await dlP;
  const exportPath = path.join(DOWNLOADS, 'capability-a-export.xlsx');
  await dl.saveAs(exportPath);
  record('export produced a real downloadable XLSX', fs.statSync(exportPath).size > 1000, fs.statSync(exportPath).size);

  await page.reload({ waitUntil: 'networkidle', timeout: 90000 });
  await page.locator('[data-testid="canvas-capability-panel"]').waitFor({ state: 'attached', timeout: 90000 });
  await openPanel(page);
  const revA = await panel.locator('[data-testid="capability-revision"]').innerText();
  record('manifest, binding and revision persist across reload', revA.includes('4 rows') && revA.includes('revision 2'), revA);

  // ── Canvas B — different fields, decisions and policy ──────────────
  const urlB = await newCanvas(page);
  record('second user-created canvas created through UI', /\/canvas\//.test(urlB) && urlB !== urlA, urlB);
  await openPanel(page);
  const manifestB = {
    schema_version: 1,
    base_component: 'table',
    operations: ['read', 'select', 'calculate', 'assess', 'edit', 'export', 'bind'],
    data_binding: { subject_field: 'Ticket', measure_field: 'Hours', status_field: 'State' },
    editable_fields: ['Hours', 'State'],
    teaching_binding: { agent_id: AGENT, scope_id: 'task-b' },
    decision_options: ['ACCEPT', 'ESCALATE', 'REJECT', 'REVIEW'],
    task_policy: 'ACCEPT Hours <= 3 when State is Open. ESCALATE Hours >= 8. REVIEW other Open tickets. REJECT Closed tickets.',
    outputs: ['xlsx'],
    required_approvals: [],
  };
  await configure(page, manifestB);
  const bindB = await bind(page, path.join(FIX, 'pipeline_b.csv'));
  const effB = await panel.locator('[data-testid="capability-effective"]').innerText();
  record('second manifest uses different vocabulary', effB.includes('assess') && effB.includes('edit'), effB);
  record('second differently-shaped dataset bound', bindB.status < 300 && bindB.body?.row_count === 4, { status: bindB.status, rows: bindB.body?.row_count });
  const calcB = await runOp(page, 'calculate', 'sum Hours for Open rows', '12.5');
  record('second calculation uses its own measure', calcB.body?.total_values?.['(unstated)'] === '12.50', calcB.body?.total_values);
  const assessB = await runOp(page, 'assess', 'assess Open rows', 'ACCEPT');
  const decisionsB = Object.fromEntries((assessB.body?.assessments || []).map(a => [a.subject_id, a.decision]));
  record('second assessment uses different decision labels', assessB.body?.certified === true && decisionsB['T-900'] === 'ACCEPT' && decisionsB['T-901'] === 'REVIEW' && decisionsB['T-903'] === 'REVIEW', decisionsB);
  record('second assessment served DeepSeek Flash', assessB.body?.route?.served_model === 'deepseek-flash' && assessB.body?.route?.served_provider === 'deepseek', { model: assessB.body?.route?.served_model });

  await panel.locator('[data-testid="capability-edit-row"]').fill('3');
  await panel.locator('[data-testid="capability-edit-column"]').fill('Hours');
  await panel.locator('[data-testid="capability-edit-value"]').fill('8');
  const editBRespP = page.waitForResponse(r => r.url().includes('/capability/edit') && r.request().method() === 'POST', { timeout: 60000 });
  await panel.locator('[data-testid="capability-edit"]').dispatchEvent('click');
  const editBResp = await editBRespP;
  const editBBody = await editBResp.json().catch(() => ({}));
  await page.waitForTimeout(700);
  record('second edit read back from store', String(editBBody?.edits?.[0]?.readback) === '8' && editBBody?.edits?.[0]?.readback_matches === true, editBBody?.edits);
  const assessB2 = await runOp(page, 'assess', 'assess Open rows', 'ESCALATE');
  const decisionsB2 = Object.fromEntries((assessB2.body?.assessments || []).map(a => [a.subject_id, a.decision]));
  record('corrected second canvas escalates the edited row', assessB2.body?.certified === true && decisionsB2['T-901'] === 'ESCALATE', decisionsB2);

  const dlBP = page.waitForEvent('download', { timeout: 90000 });
  await panel.locator('[data-testid="capability-export"]').dispatchEvent('click');
  const dlB = await dlBP;
  const exportBPath = path.join(DOWNLOADS, 'capability-b-export.xlsx');
  await dlB.saveAs(exportBPath);
  record('second export produced a real XLSX', fs.statSync(exportBPath).size > 1000, fs.statSync(exportBPath).size);

  await page.reload({ waitUntil: 'networkidle', timeout: 90000 });
  await page.locator('[data-testid="canvas-capability-panel"]').waitFor({ state: 'attached', timeout: 90000 });
  await openPanel(page);
  const revB = await panel.locator('[data-testid="capability-revision"]').innerText();
  record('second canvas state persists across reload', revB.includes('4 rows') && revB.includes('revision 2'), revB);

  record('no browser page errors', pageErrors.length === 0, pageErrors.slice(0, 3));
  const out = {
    status: checks.every(c => c.ok) ? 'passed' : 'failed',
    checks,
    canvas_a: { url: urlA, decisions_initial: decisionsA, decisions_after_edit: decisionsA2, export: exportPath },
    canvas_b: { url: urlB, decisions_initial: decisionsB, decisions_after_edit: decisionsB2, export: exportBPath },
    page_errors: pageErrors,
  };
  fs.writeFileSync(path.join(OUT, 'capability_ui.json'), JSON.stringify(out, null, 1));
  console.log('STATUS', out.status.toUpperCase(), `${checks.filter(c => c.ok).length}/${checks.length}`);
  await browser.close();
  process.exit(out.status === 'passed' ? 0 : 1);
})().catch(e => {
  console.error('FATAL', e);
  fs.writeFileSync(path.join(OUT, 'capability_ui.json'), JSON.stringify({ status: 'fatal', error: String(e), checks }, null, 1));
  process.exit(2);
});
