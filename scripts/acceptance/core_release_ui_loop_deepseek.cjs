const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const BASE = 'http://127.0.0.1:3114';
const API = 'http://127.0.0.1:8061';
const WORLD = '/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds/core_release_deepseek_20261028';
const PW = fs.readFileSync(WORLD + '/backend_root/logs/bootstrap_admin_password.txt', 'utf8').trim();
const OUT = process.env.UI_OUT_DIR
  ? path.resolve(process.env.UI_OUT_DIR)
  : path.join(ROOT, 'docs/acceptance/evidence/whole_app_20261028/core_release_ui_loop_deepseek_20261028_attempt2');
const FIXTURES = path.join(ROOT, 'docs/acceptance/evidence/whole_app_20261028/core_release_ui_loop_deepseek_20261028/fixtures');
const GRANTS = path.join(FIXTURES, 'grants_loop.csv');
const VENDOR = path.join(FIXTURES, 'vendor_loop.csv');
const RESTART = path.join(ROOT, 'scripts/acceptance/core_release_ui_restart_deepseek.py');
const DB_CHECK = path.join(ROOT, 'scripts/acceptance/core_release_db_check_deepseek.py');
const ORIGINAL = 'Use exactly these decision labels: FUND, HOLD, DECLINE. Requested amount at or above 10000 is FUND. 5000 to 9999 is HOLD. Below 5000 is DECLINE. Cite the reference and amount from the row.';
const CORRECTED = 'Use exactly these decision labels: FUND, HOLD, DECLINE. Requested amount at or above 10000 is HOLD for CFO review. 5000 to 9999 is HOLD. Below 5000 is DECLINE. Cite the reference and amount from the row.';
const GRANT_ASK = 'Assess each Submitted application in grants_loop.csv under the taught threshold rule. Give a table with reference, amount and decision.';
const VENDOR_ASK = 'Assess each Open invoice in vendor_loop.csv under the taught threshold rule. Give a table with vendor reference, amount and decision.';
const CALC_ASK = 'What is the total Invoice Amount for Open invoices in vendor_loop.csv? Use a sum and cite the rows.';
const EXPECTED_TOTAL = '22200';
const EXPECTED_MODEL = process.env.UI_EXPECTED_MODEL || 'deepseek-v4-pro';
let AGENT = null;
const checks = [];
const record = (name, ok, detail) => {
  checks.push({name, ok: !!ok, detail});
  console.log((ok ? 'PASS' : 'FAIL'), name, detail === undefined ? '' : JSON.stringify(detail));
};
async function api(method, p, token, body) {
  const r = await fetch(API + p, {method, headers: {'Content-Type': 'application/json', ...(token ? {Authorization: 'Bearer ' + token} : {})}, body: body ? JSON.stringify(body) : undefined});
  return {status: r.status, body: await r.json().catch(() => ({}))};
}
async function dismiss(p) {
  for (let i = 0; i < 12; i++) {
    const d = p.locator('[role="dialog"]').first();
    if (await d.count() === 0) { await p.waitForTimeout(450); if (await p.locator('[role="dialog"]').count() === 0) return; continue; }
    const btn = d.getByRole('button', {name: /Start Automating|Next|Finish|Done|Get started|Continue/i}).last();
    if (await btn.count()) { await btn.evaluate(el => el.click()); await p.waitForTimeout(900); }
    else { await p.keyboard.press('Escape'); await p.waitForTimeout(500); }
  }
}
async function login(p) {
  await p.goto(BASE + '/login', {waitUntil: 'networkidle', timeout: 90000});
  if (!/\/login/.test(p.url())) return;
  await p.fill('[data-testid="login-email-input"]', 'admin@example.com');
  await p.fill('[data-testid="login-password-input"]', PW);
  await p.locator('[data-testid="login-submit-button"]').evaluate(el => el.click());
  await p.waitForTimeout(9000); await dismiss(p);
}
async function newCanvas(p) {
  await p.goto(BASE + '/canvas', {waitUntil: 'networkidle', timeout: 90000});
  await p.waitForTimeout(3500); await dismiss(p);
  await p.locator('[data-testid="new-blank-canvas-button"]').evaluate(el => el.click());
  await p.waitForTimeout(6000); await dismiss(p);
  const url = p.url();
  await p.locator('[data-testid="add-agent-button"], [data-testid="banner-add-agent-button"]').first().evaluate(el => el.click());
  await p.waitForTimeout(1500);
  await p.locator(`[data-testid="attach-agent-option-${AGENT}"]`).evaluate(el => el.click());
  await p.waitForTimeout(4500);
  return url;
}
async function uploadViaChat(p, file) {
  await p.goto(BASE + '/chat?agent_id=' + AGENT, {waitUntil: 'networkidle', timeout: 90000});
  await p.waitForTimeout(3500); await dismiss(p);
  const upP = p.waitForResponse(r => r.url().includes('/api/documents/upload') && r.request().method() === 'POST', {timeout: 120000});
  await p.locator('#chat-file-upload').setInputFiles(file);
  const up = await upP;
  await p.waitForTimeout(3000);
  return {status: up.status(), body: await up.json().catch(() => ({}))};
}
async function canvasAsk(p, ask, timeout = 300000) {
  const respP = p.waitForResponse(r => {
    if (!r.url().includes('/api/chat/message') || r.request().method() !== 'POST') return false;
    try { return JSON.parse(r.request().postData() || '{}').message === ask; } catch { return false; }
  }, {timeout});
  await p.locator('textarea[placeholder="Ask the agent to edit…"]').fill(ask);
  await p.locator('button[aria-label="Send message"]').evaluate(el => el.click());
  const resp = await respP;
  const json = await resp.json();
  await p.waitForTimeout(1200);
  return {status: resp.status(), json};
}
function decisions(json) {
  const r = json?.metadata?.review_result || json?.review_result || {};
  const out = {};
  for (const a of r.assessments || []) out[a.subject_id] = a.decision;
  return {review: r, decisions: out, contract: json?.metadata?.review_contract || json?.review_contract};
}
function routeOk(turn) {
  return turn?.json?.model === EXPECTED_MODEL && turn?.json?.provider === 'deepseek';
}

(async () => {
  const loginApi = await api('POST', '/api/auth/login', null, {username: 'admin@example.com', password: PW});
  record('admin login API', loginApi.status === 200 && !!loginApi.body.access_token, loginApi.status);
  const token = loginApi.body.access_token;
  const created = await api('POST', '/api/agents/custom', token, {name: 'Core Release DeepSeek Assessor', description: 'UI acceptance hire.', category: 'Operations', configuration: {system_prompt: 'You assess tabular records against the policy you were taught and cite the source row.'}, schedule_config: {}});
  AGENT = created.body?.data?.agent_id;
  record('agent created through product API', !!AGENT, created.status);

  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  const page = await browser.newPage({viewport: {width: 1600, height: 1000}});
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e).slice(0, 300)));
  await login(page);

  const upGrants = await uploadViaChat(page, GRANTS);
  const upVendor = await uploadViaChat(page, VENDOR);
  record('grants material uploaded through UI', upGrants.status < 300, upGrants.status);
  record('vendor material uploaded through UI', upVendor.status < 300, upVendor.status);

  const canvas1 = await newCanvas(page);
  record('first canvas created and agent attached via UI', /\/canvas\//.test(canvas1));
  await page.locator('[data-testid="canvas-side-tab-training"]').evaluate(el => el.click());
  await page.waitForTimeout(2500);
  await page.fill('[data-testid="teach-lesson-input"]', ORIGINAL);
  await page.fill('[data-testid="teach-topic-input"]', 'grant threshold rule');
  await page.locator('[data-testid="teach-submit"]').evaluate(el => el.click());
  await page.waitForTimeout(4500);
  record('policy taught through UI', await page.locator('[data-testid="teaching-point"]').count() === 1);

  await page.goto(canvas1, {waitUntil: 'networkidle', timeout: 90000});
  await page.waitForTimeout(3000); await dismiss(page);
  await page.locator('[data-testid="canvas-side-tab-chat"]').evaluate(el => el.click());
  await page.waitForTimeout(1000);
  const grantTurn = await canvasAsk(page, GRANT_ASK);
  const grant = decisions(grantTurn.json);
  record('first assessment validated', grant.review.ok === true, grant.review.errors);
  record('first assessment follows original policy', grant.decisions['GR-2026-014'] === 'FUND' && grant.decisions['GR-2026-021'] === 'HOLD' && grant.decisions['GR-2026-033'] === 'DECLINE', grant.decisions);
  record('first assessment used declared DeepSeek route', routeOk(grantTurn), {model: grantTurn.json?.model, provider: grantTurn.json?.provider});

  await page.locator('[data-testid="canvas-side-tab-training"]').evaluate(el => el.click());
  await page.waitForTimeout(2500);
  await page.locator('[data-testid="teaching-point-edit"]').first().evaluate(el => el.click());
  await page.waitForTimeout(800);
  const before = await page.locator('[data-testid="teaching-point-text-input"]').inputValue();
  await page.locator('[data-testid="teaching-point-text-input"]').fill(CORRECTED);
  const patchP = page.waitForResponse(r => r.url().includes('/teaching-points/') && r.request().method() === 'PATCH', {timeout: 60000});
  await page.locator('[data-testid="teaching-point-save"]').evaluate(el => el.click());
  const patch = await patchP;
  const patchBody = await patch.json().catch(() => ({}));
  await page.waitForTimeout(2500);
  const pointText = await page.locator('[data-testid="teaching-points-section"]').innerText();
  record('in-place correction saved', patch.status() === 200 && pointText.includes('HOLD for CFO review'), patch.status());
  record('correction kept one teaching point', pointText.includes('1 recorded'));

  const canvas2 = await newCanvas(page);
  record('second canvas created and agent attached via UI', /\/canvas\//.test(canvas2));
  await page.locator('[data-testid="canvas-side-tab-chat"]').evaluate(el => el.click());
  await page.waitForTimeout(1200);
  const vendorTurn = await canvasAsk(page, VENDOR_ASK);
  const vendor = decisions(vendorTurn.json);
  const vendorBody = await page.locator('body').innerText();
  record('different unfamiliar assessment validated', vendor.review.ok === true, vendor.review.errors);
  record('different assessment follows correction', vendor.decisions['IN-7301'] === 'DECLINE' && vendor.decisions['IN-7302'] === 'HOLD' && vendor.decisions['IN-7303'] === 'HOLD', vendor.decisions);
  record('different assessment excludes Closed row', !JSON.stringify(vendor.decisions).includes('IN-7304'));
  record('different assessment delivered a table', vendorBody.includes('VALIDATED REVIEW') && vendorBody.includes('IN-7303'));
  record('different assessment used declared DeepSeek route', routeOk(vendorTurn), {model: vendorTurn.json?.model, provider: vendorTurn.json?.provider});

  const calcTurn = await canvasAsk(page, CALC_ASK);
  const calcText = String(calcTurn.json.message || '');
  record('calculation delivers exact total', new RegExp('\\b' + EXPECTED_TOTAL + '\\b').test(calcText), calcText.slice(0, 260));
  record('calculation cites selected rows', calcText.includes('IN-7301') && calcText.includes('IN-7302') && calcText.includes('IN-7303'));
  record('calculation binds source version', calcText.includes('0a84a5f50661'));

  fs.writeFileSync(OUT + '/pre_restart_final.json', JSON.stringify({
    agent_id: AGENT, canvas1, canvas2, before, corrected: CORRECTED,
    grant: {status: grantTurn.status, model: grantTurn.json?.model, provider: grantTurn.json?.provider, review: grant.review, contract: grant.contract, decisions: grant.decisions},
    correction: {status: patch.status(), body: patchBody, pointText},
    vendor: {status: vendorTurn.status, model: vendorTurn.json?.model, provider: vendorTurn.json?.provider, review: vendor.review, contract: vendor.contract, decisions: vendor.decisions},
    calculation: {status: calcTurn.status, message: calcText, metadata: calcTurn.json.metadata},
    checks: [...checks],
  }, null, 2));

  const restartOut = execFileSync('python3', [RESTART], {encoding: 'utf8', timeout: 240000});
  const restart = JSON.parse(restartOut.trim().split('\n').pop());
  record('backend restart healthy', restart.ok === true, restart.pid);
  await page.waitForTimeout(3000);
  await page.reload({waitUntil: 'networkidle', timeout: 90000});
  await page.waitForTimeout(5000);
  if (/\/login/.test(page.url())) { await login(page); await page.goto(canvas2, {waitUntil: 'networkidle', timeout: 90000}); await page.waitForTimeout(4000); }
  await dismiss(page);
  await page.locator('[data-testid="canvas-side-tab-training"]').evaluate(el => el.click());
  await page.waitForTimeout(2500);
  const restored = await page.locator('[data-testid="teaching-points-section"]').innerText();
  record('corrected policy persists after restart', restored.includes('HOLD for CFO review'));
  await page.locator('[data-testid="canvas-side-tab-chat"]').evaluate(el => el.click());
  await page.waitForTimeout(3500);
  const historyText = await page.locator('body').innerText();
  record('pre-restart assessment history persists', historyText.includes('IN-7301') && historyText.includes('VALIDATED REVIEW'));
  record('pre-restart calculation history persists', historyText.includes(EXPECTED_TOTAL));

  const freshTurn = await canvasAsk(page, VENDOR_ASK);
  const fresh = decisions(freshTurn.json);
  record('fresh post-restart assessment validated', fresh.review.ok === true, fresh.review.errors);
  record('fresh post-restart assessment follows correction', fresh.decisions['IN-7301'] === 'DECLINE' && fresh.decisions['IN-7302'] === 'HOLD' && fresh.decisions['IN-7303'] === 'HOLD', fresh.decisions);
  record('fresh post-restart assessment used declared DeepSeek route', routeOk(freshTurn), {model: freshTurn.json?.model, provider: freshTurn.json?.provider});

  fs.writeFileSync(OUT + '/fresh_after_restart_ui.text', await page.locator('body').innerText());
  await page.screenshot({path: OUT + '/final_after_restart.png', fullPage: true});
  let dbCheck = null;
  try { dbCheck = JSON.parse(execFileSync('python3', [DB_CHECK], {encoding: 'utf8', timeout: 60000})); } catch (e) { dbCheck = {error: String(e)}; }
  record('zero unauthorized writes', dbCheck.zero_unauthorized_writes === true, dbCheck.side_effect_counts);

  const summary = {
    status: checks.every(c => c.ok) ? 'passed' : 'failed',
    base: BASE, backend: API, agent_id: AGENT, canvas1, canvas2,
    source_materials: {grants: GRANTS, vendor: VENDOR},
    expected_model: EXPECTED_MODEL,
    checks,
    grant: {status: grantTurn.status, model: grantTurn.json?.model, provider: grantTurn.json?.provider, review: grant.review, contract: grant.contract, decisions: grant.decisions},
    correction: {status: patch.status(), before, after: CORRECTED, pointText},
    vendor: {status: vendorTurn.status, model: vendorTurn.json?.model, provider: vendorTurn.json?.provider, review: vendor.review, contract: vendor.contract, decisions: vendor.decisions},
    calculation: {status: calcTurn.status, message: calcText, metadata: calcTurn.json.metadata},
    restart,
    fresh: {status: freshTurn.status, model: freshTurn.json?.model, provider: freshTurn.json?.provider, review: fresh.review, contract: fresh.contract, decisions: fresh.decisions},
    history_survives: {vendor: historyText.includes('IN-7301'), calculation: historyText.includes(EXPECTED_TOTAL)},
    db_check: dbCheck,
    page_errors: pageErrors,
  };
  fs.writeFileSync(OUT + '/ui_loop_final.json', JSON.stringify(summary, null, 2));
  console.log('STATUS', summary.status);
  await browser.close();
  process.exit(summary.status === 'passed' ? 0 : 2);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
