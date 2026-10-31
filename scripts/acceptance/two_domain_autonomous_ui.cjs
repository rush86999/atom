#!/usr/bin/env node
/**
 * Integrated two-domain autonomous journey.
 *
 * One explicit bounded standing-authority grant per domain covers its send.
 * The user teaches nothing new in the browser (the employee has the seeded
 * document/presentation standards), starts two unfamiliar-dataset jobs, leaves
 * while both wait, the backend restarts, and each job completes from the page
 * without a per-send approval.
 *
 * Setup/assertions use the real assignment routes; user actions are the normal
 * Assignments page. Controlled outbox only; no provider or real send.
 */
const { spawn } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
let playwright;
try {
  playwright = require('playwright');
} catch {
  playwright = require(path.join(ROOT, 'frontend-nextjs/node_modules/playwright'));
}
const { chromium } = playwright;

const UI = process.env.ASSIGNMENT_UI_BASE || 'http://127.0.0.1:3004';
const API = process.env.ASSIGNMENT_API_BASE || 'http://127.0.0.1:8090';
const WORLD = process.env.ASSIGNMENT_TWO_DOMAIN_WORLD
  || '/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/two-domain-autonomous';
const OUT = process.env.ASSIGNMENT_TWO_DOMAIN_OUT
  || path.join(ROOT, 'docs/acceptance/evidence/durable_assignment_20261031/two-domain-autonomous-journey');
const PYTHON = process.env.ASSIGNMENT_PYTHON
  || '/Users/rushiparikh/projects/atom-phase-d/backend/venv/bin/python';
const SERVER = path.join(ROOT, 'backend/scripts/assignment_browser_acceptance_server.py');
const PORT = Number(new URL(API).port || 8090);
const SHOTS = path.join(OUT, 'screenshots');
const checks = [];
let server = null;

function log(...args) { console.log(new Date().toISOString(), ...args); }
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function record(name, ok, detail) {
  checks.push({ name, ok: !!ok, detail });
  log(ok ? 'PASS' : 'FAIL', name, JSON.stringify(detail).slice(0, 1200));
}

async function getJson(url, init) {
  const response = await fetch(url, init);
  const text = await response.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = text; }
  return { status: response.status, body };
}

async function waitFor(predicate, timeoutMs = 45000, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try {
      last = await predicate();
      if (last) return last;
    } catch (error) { last = error; }
    await sleep(intervalMs);
  }
  throw new Error(`timed out: ${last && last.message ? last.message : last}`);
}

async function startServer(reset) {
  const env = {
    ...process.env,
    ATOM_ASSIGNMENT_BROWSER_WORLD: WORLD,
    ATOM_ASSIGNMENT_BROWSER_WORLD_RESET: reset ? '1' : '0',
    ATOM_ASSIGNMENT_BROWSER_PORT: String(PORT),
    ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS: '1',
    ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT: WORLD,
    ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT: '1',
    ATOM_ASSIGNMENT_OUTBOX: path.join(WORLD, 'outbox.jsonl'),
    PYTHONPATH: [
      ROOT,
      path.join(ROOT, 'backend'),
      process.env.ASSIGNMENT_PYTHON_OVERLAY
        || '/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-pyoverlay',
      process.env.PYTHONPATH || '',
    ].filter(Boolean).join(':'),
  };
  const child = spawn(PYTHON, [SERVER], {
    cwd: path.join(ROOT, 'backend'), env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  fs.mkdirSync(OUT, { recursive: true });
  const stream = fs.createWriteStream(
    path.join(OUT, reset ? 'backend-reset.log' : 'backend-restart.log'),
    { flags: 'a' });
  child.stdout.pipe(stream);
  child.stderr.pipe(stream);
  await waitFor(async () => {
    const state = await getJson(`${API}/_acceptance/state`).catch(() => null);
    return state && state.status === 200 && state.body.ok ? state.body : null;
  }, 45000);
  return child;
}

async function stopServer() {
  if (!server) return;
  const pid = server.pid;
  server.kill('SIGTERM');
  await waitFor(() => {
    try { process.kill(pid, 0); return false; } catch { return true; }
  }, 20000).catch(() => {});
  server = null;
  await sleep(700);
}

async function state() { return (await getJson(`${API}/_acceptance/state`)).body; }
async function outbox() { return (await getJson(`${API}/_acceptance/outbox`)).body.lines; }

async function openAssignments(page, health) {
  await page.goto(
    `${UI}/assignments?agent=${encodeURIComponent(health.agent_id)}`,
    { waitUntil: 'networkidle', timeout: 120000 });
  await waitFor(async () => {
    const select = page.locator('[data-testid="assignment-source-select"]');
    if (await select.count() === 0) return false;
    return await select.evaluate((element) => {
      if (element.disabled) return false;
      return Array.from(element.options).some((option) => option.value);
    });
  }, 45000);
}

async function selectAssignment(page, objective) {
  const summary = page.locator('[data-testid^="assignment-summary-"]')
    .filter({ hasText: objective }).first();
  await summary.waitFor({ state: 'visible', timeout: 30000 });
  await summary.evaluate((element) => element.click());
  await waitFor(async () => {
    const header = page.locator('[data-testid="assignment-detail-objective"]');
    if (await header.count() === 0) return false;
    return (await header.innerText()).includes(objective);
  }, 20000);
  await page.waitForTimeout(400);
}

async function startDomain(page, domain) {
  await page.getByLabel('Assignment objective').fill(domain.objective);
  await page.getByTestId('assignment-source-select')
    .selectOption({ label: domain.sourceLabel });
  await page.getByTestId('assignment-measure-select')
    .selectOption({ label: domain.measureLabel });
  await page.locator('details').evaluate((element) => {
    element.open = true;
  });
  await page.getByLabel('Artifact content').fill(domain.content);
  await page.getByLabel('Send recipient').fill(domain.recipient);
  await page.getByLabel('Correlation id').fill(domain.correlation);
  await page.getByLabel('Standing authority recipients').fill(domain.recipient);
  await page.getByLabel('Standing authority max sends').fill('1');
  await page.getByTestId('assignment-start-button').click();
  await waitFor(async () => {
    const detail = page.locator('[data-testid="assignment-detail"]');
    if (await detail.count() === 0) return false;
    const text = await detail.innerText();
    return text.includes(domain.objective)
      && text.includes('Standing authority: 0/1 sends used');
  }, 30000);
  await page.waitForTimeout(500);
  const runId = await runIdForObjective(domain.objective);
  const status = (await getJson(`${API}/api/assignments/${runId}`)).body;
  return { runId, status: status.assignment.status };
}

async function runIdForObjective(objective) {
  const list = (await getJson(`${API}/api/assignments?include_terminal=true`)).body;
  return (list.find((item) => item.assignment
    && item.assignment.objective === objective) || {}).run_id;
}

async function assignment(runId) {
  return (await getJson(`${API}/api/assignments/${runId}`)).body;
}

async function deliver(page, domain, responseText) {
  await selectAssignment(page, domain.objective);
  await page.getByLabel('Correlated response').fill(responseText);
  await page.getByRole('button', { name: /Deliver/ }).click();
  await waitFor(async () => {
    const detail = await assignment(domain.runId);
    return detail.assignment.status === 'completed';
  }, 45000);
  await page.waitForTimeout(700);
  return page.locator('[data-testid="assignment-detail"]').innerText();
}

async function screenshot(page, name) {
  fs.mkdirSync(SHOTS, { recursive: true });
  const target = path.join(SHOTS, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  return target;
}

function hashFile(relative) {
  const file = path.join(ROOT, relative);
  return fs.existsSync(file)
    ? crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
    : null;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  server = await startServer(true);
  const pid1 = (await state()).pid;
  const health = (await getJson(`${API}/api/health`)).body;
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const context = await browser.newContext();
  await context.addCookies([{
    name: 'auth_token', value: 'browser-acceptance-token',
    domain: '127.0.0.1', path: '/',
  }]);
  const page = await context.newPage();
  const domains = [
    {
      key: 'sales',
      objective: 'Sales: sum the scotch parts total',
      sourceLabel: 'scotch-parts.xlsx / US$ SCOTCH PARTS · 3 rows',
      measureLabel: 'Sum Total',
      content: '## Summary\n\nTotal ${source-1.value}\n\n## Sources\n\n- scotch-parts.xlsx',
      recipient: 'sales@example.invalid',
      correlation: 'corr-sales-two-domain',
      expected: '85',
    },
    {
      key: 'grants',
      objective: 'Grants: sum the approved applications',
      sourceLabel: 'grant-applications.xlsx / GRANT APPLICATIONS · 3 rows',
      measureLabel: 'Sum Approved Amount',
      content: 'Slide 1: Overview\n- Grant applications\n\nSlide 2: Findings\n- total ${source-1.value}\n\nSlide 3: Sources\n- grant-applications.xlsx',
      recipient: 'grants@example.invalid',
      correlation: 'corr-grants-two-domain',
      expected: '4250',
    },
  ];
  try {
    await openAssignments(page, health);
    for (const domain of domains) {
      const started = await startDomain(page, domain);
      domain.runId = started.runId;
      record(`${domain.key} starts and waits`, started.status === 'waiting', {
        runId: domain.runId, status: started.status,
      });
    }
    const startedShot = await screenshot(page, '01-two-domains-waiting');

    await stopServer();
    server = await startServer(false);
    const pid2 = (await state()).pid;
    await page.reload({ waitUntil: 'networkidle', timeout: 120000 });
    await waitFor(async () => (
      await page.locator('[data-testid^="assignment-summary-"]').count() >= 2
    ), 45000);

    for (const domain of domains) {
      const text = await deliver(page, domain, 'approved_reference: REF-2026');
      const detail = await assignment(domain.runId);
      const stepStatuses = (detail.assignment.steps || []).map(
        (step) => `${step.step_id}:${step.status}`);
      const sendStep = (detail.assignment.steps || []).find(
        (step) => step.effect === 'external');
      const grant = detail.assignment.standing_authority || {};
      const completed = detail.assignment.status === 'completed';
      const covered = !!sendStep && sendStep.status === 'applied'
        && !!sendStep.standing_authority_receipt;
      const noApprovalUi = !text.includes('Approval required');
      const usedOnce = Number(grant.used_effects) === 1
        && Number(grant.max_effects) === 1
        && grant.status === 'exhausted';
      const expectedResult = text.includes(domain.expected)
        || ((sendStep || {}).result || {}).value === domain.expected;
      record(`${domain.key} completes under bounded standing authority`,
        completed && covered && noApprovalUi && usedOnce && expectedResult, {
          runId: domain.runId, status: detail.assignment.status,
          stepStatuses, usedOnce, covered, noApprovalUi, expectedResult,
        });
      domain.shot = await screenshot(page, `02-${domain.key}-completed`);
    }

    const effects = await outbox();
    const finalState = await state();
    const recipients = effects.map((item) => (item.to || []).join(','));
    const both = recipients.includes('sales@example.invalid')
      && recipients.includes('grants@example.invalid');
    record('two domains produced exactly two covered effects and no approval',
      effects.length === 2 && both
        && Number(finalState.hitl_assignment_approvals) === 0,
      {
        effects: effects.length, recipients,
        hitlAssignmentApprovals: finalState.hitl_assignment_approvals,
        pid1, pid2, restarted: pid1 !== pid2,
        screenshots: [startedShot, ...domains.map((d) => d.shot)],
      });

    const payload = {
      schema: 'atom-two-domain-autonomous-journey-1',
      generated_at: new Date().toISOString(),
      ui_base: UI, api_base: API, world: WORLD,
      backend_pids: [pid1, pid2],
      domains: domains.map((domain) => ({
        key: domain.key, objective: domain.objective,
        run_id: domain.runId, recipient: domain.recipient,
        expected: domain.expected,
      })),
      outbox: effects,
      hitl_assignment_approvals: finalState.hitl_assignment_approvals,
      checks,
      passed: checks.filter((item) => item.ok).length,
      failed: checks.filter((item) => !item.ok).length,
      source: {
        backend_head: process.env.ASSIGNMENT_SOURCE_HEAD || null,
        files: {
          'backend/scripts/assignment_browser_acceptance_server.py':
            hashFile('backend/scripts/assignment_browser_acceptance_server.py'),
          'backend/core/assignment_executor.py':
            hashFile('backend/core/assignment_executor.py'),
          'backend/core/assignment_plan.py':
            hashFile('backend/core/assignment_plan.py'),
          'backend/api/assignment_routes.py':
            hashFile('backend/api/assignment_routes.py'),
          'frontend-nextjs/components/assignments/AssignmentPanel.tsx':
            hashFile('frontend-nextjs/components/assignments/AssignmentPanel.tsx'),
        },
      },
    };
    fs.writeFileSync(path.join(OUT, 'two-domain.json'),
      JSON.stringify(payload, null, 2) + '\n');
    log(`EVIDENCE ${path.join(OUT, 'two-domain.json')}`);
    log(`RESULT ${payload.passed}/${checks.length} checks passed`);
    process.exit(payload.failed === 0 ? 0 : 1);
  } finally {
    await context.close();
    await browser.close();
    await stopServer();
  }
})().catch(async (error) => {
  console.error(error);
  await stopServer();
  process.exit(2);
});
