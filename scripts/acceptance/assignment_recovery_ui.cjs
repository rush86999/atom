#!/usr/bin/env node
/**
 * Browser-level practical-assignment recovery journey.
 *
 * Setup and assertions use the real assignment routes; user actions go through
 * the real Assignments page. The backend is the standalone acceptance server
 * (real executor + real routes on a scratch SQLite world, controlled outbox).
 *
 * Scenarios:
 *   1. wait -> backend restart -> resume from the browser
 *   2. changed source revision invalidates stale mapping work; completed work survives
 *   3. ambiguous mapping identity is visible/refused without identity, then resolved
 *   4. cancellation survives reload and refuses a late response
 *   5. duplicate concurrent resume/response dispatches once
 *
 * This is not a broad campaign. It exercises only the practical boundaries.
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
const UI = process.env.ASSIGNMENT_UI_BASE || 'http://127.0.0.1:3003';
const API = process.env.ASSIGNMENT_API_BASE || 'http://127.0.0.1:8090';
const WORLD = process.env.ASSIGNMENT_RECOVERY_WORLD
  || '/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/assignment-recovery-browser';
const OUT = process.env.ASSIGNMENT_RECOVERY_OUT
  || path.join(ROOT, 'docs/acceptance/evidence/durable_assignment_20261031/assignment-recovery-browser');
const PYTHON = process.env.ASSIGNMENT_PYTHON
  || '/Users/rushiparikh/projects/atom-phase-d/backend/venv/bin/python';
const SERVER = path.join(ROOT, 'backend/scripts/assignment_browser_acceptance_server.py');
const PORT = Number(new URL(API).port || 8090);
const SCREENSHOTS = path.join(OUT, 'screenshots');
const checks = [];
let server = null;

function log(...args) {
  console.log(new Date().toISOString(), ...args);
}

function record(name, ok, detail) {
  checks.push({ name, ok: !!ok, detail });
  log(ok ? 'PASS' : 'FAIL', name, detail === undefined ? '' : JSON.stringify(detail).slice(0, 900));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getJson(url, init) {
  const response = await fetch(url, init);
  const text = await response.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = text; }
  return { status: response.status, body };
}

async function waitFor(predicate, timeoutMs = 30000, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try {
      last = await predicate();
      if (last) return last;
    } catch (error) {
      last = error;
    }
    await sleep(intervalMs);
  }
  throw new Error(`timed out waiting: ${last && last.message ? last.message : last}`);
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
    cwd: path.join(ROOT, 'backend'),
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const logPath = path.join(OUT, reset ? 'backend-reset.log' : 'backend-restart.log');
  fs.mkdirSync(OUT, { recursive: true });
  const stream = fs.createWriteStream(logPath, { flags: 'a' });
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

async function state() {
  return (await getJson(`${API}/_acceptance/state`)).body;
}

async function outboxCount() {
  const body = await state();
  return Number(body.outbox_lines || 0);
}

async function newPage(browser) {
  const context = await browser.newContext();
  await context.addCookies([{
    name: 'auth_token', value: 'browser-acceptance-token',
    domain: '127.0.0.1', path: '/',
  }]);
  return { context, page: await context.newPage() };
}

async function openAssignments(page) {
  const health = (await getJson(`${API}/api/health`)).body;
  await page.goto(
    `${UI}/assignments?agent=${encodeURIComponent(health.agent_id)}`,
    { waitUntil: 'networkidle', timeout: 120000 },
  );
  await waitFor(async () => {
    const select = page.locator('[data-testid="assignment-source-select"]');
    if (await select.count() === 0) return false;
    return await select.evaluate((element) => (
      !element.disabled
      && Array.from(element.options).some((option) => option.value)
    ));
  }, 45000);
  return health;
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
  await page.waitForTimeout(500);
}

async function startAssignment(page, options) {
  await page.getByLabel('Assignment objective').fill(options.objective);
  await page.getByTestId('assignment-source-select').selectOption({ index: 0 });
  if (options.measureLabel) {
    await page.getByTestId('assignment-measure-select')
      .selectOption({ label: options.measureLabel });
  }
  await page.locator('details summary').click();
  if (options.content) {
    await page.getByLabel('Artifact content').fill(options.content);
  }
  if (options.expression) {
    await page.getByLabel('Calculation expression').fill(options.expression);
  }
  if (options.correlation) {
    await page.getByLabel('Correlation id').fill(options.correlation);
  }
  if (options.missingFact) {
    await page.getByLabel('Missing fact').fill(options.missingFact);
  }
  await page.getByTestId('assignment-start-button').click();
  await waitFor(async () => {
    const header = page.locator('[data-testid="assignment-detail-objective"]');
    if (await header.count() === 0) return false;
    return (await header.innerText()).includes(options.objective);
  }, 30000);
  await page.waitForTimeout(700);
  return assignmentDetail(page);
}

async function assignmentDetail(page) {
  const text = await page.locator('[data-testid="assignment-detail"]').innerText();
  const summary = await page.evaluate(() => {
    const button = Array.from(document.querySelectorAll('[data-testid^="assignment-summary-"]'))
      .find((element) => element.getAttribute('data-testid'));
    return button ? button.getAttribute('data-testid') : null;
  });
  return { text, runId: summary ? summary.replace('assignment-summary-', '') : null };
}

async function runIdForObjective(objective) {
  const list = (await getJson(`${API}/api/assignments?include_terminal=true`)).body;
  const row = (list || []).find((item) => item.assignment
    && item.assignment.objective === objective);
  return row ? row.run_id : null;
}

async function assignmentStatus(runId) {
  const response = await getJson(`${API}/api/assignments/${runId}`);
  return response.body;
}

function statusText(detail) {
  return String(detail.assignment.status || '');
}

async function screenshot(page, name) {
  fs.mkdirSync(SCREENSHOTS, { recursive: true });
  const target = path.join(SCREENSHOTS, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  return target;
}

async function correctMapping(page, column) {
  const cards = await page.locator('[data-testid^="mapping-current-"]').all();
  let opened = false;
  for (const card of cards) {
    const button = card.getByRole('button', { name: /Correct mapping/ });
    if (!(await button.isDisabled().catch(() => true))) {
      await button.click();
      opened = true;
      break;
    }
  }
  if (!opened) throw new Error('no correctable mapping card');
  await page.waitForTimeout(400);
  const selects = await page.getByTestId('mapping-correction-column').all();
  let index = -1;
  for (let i = 0; i < selects.length; i += 1) {
    const values = await selects[i].locator('option').evaluateAll(
      (options) => options.map((option) => option.value));
    if (values.includes(column)) { index = i; break; }
  }
  if (index < 0) throw new Error(`column ${column} not offered by any correction form`);
  await selects[index].selectOption(column);
  await page.getByTestId('mapping-correction-submit').nth(index).click();
  await page.waitForTimeout(1200);
}

async function scenarioWaitRestartResume(browser) {
  const objective = `Recovery wait restart resume ${Date.now()}`;
  const correlation = `corr-restart-${Date.now()}`;
  const { context, page } = await newPage(browser);
  try {
    await openAssignments(page);
    await startAssignment(page, {
      objective,
      expression: '2*10 + 3*20',
      content: '## Summary\n\nTotal ${calculate.value}\n\n## Sources\n\n- scotch-parts.xlsx',
      correlation,
    });
    const runId = await runIdForObjective(objective);
    const pid1 = (await state()).pid;
    const waiting = (await assignmentStatus(runId)).assignment.status === 'waiting';
    const before = await screenshot(page, '01-wait-before-restart');

    await stopServer();
    server = await startServer(false);
    const pid2 = (await state()).pid;

    await page.reload({ waitUntil: 'networkidle', timeout: 120000 });
    await waitFor(async () => (
      await page.locator('[data-testid^="assignment-summary-"]').count() > 0
    ), 45000);
    await selectAssignment(page, objective);
    const afterRestart = await assignmentDetail(page);
    const durable = /waiting/.test(afterRestart.text);

    await page.getByLabel('Correlated response')
      .fill('delivery_term: DDP within 14 days');
    await page.getByRole('button', { name: /Deliver/ }).click();
    await waitFor(async () => (
      /completed/.test(await page.locator('[data-testid="assignment-detail"]').innerText())
    ), 45000);
    const finished = await assignmentDetail(page);
    const after = await screenshot(page, '02-wait-resumed-after-restart');
    const ok = waiting && durable && pid1 !== pid2
      && /completed/.test(finished.text) && /80/.test(finished.text);
    record('wait -> restart -> resume', ok, {
      objective, pid1, pid2, waiting, durable,
      completed: /completed/.test(finished.text),
      result80: /80/.test(finished.text),
      screenshots: [before, after],
    });
    return { objective, runId };
  } finally {
    await context.close();
  }
}

async function scenarioRevisionInvalidation(browser) {
  const objective = `Recovery revision invalidation ${Date.now()}`;
  const { context, page } = await newPage(browser);
  try {
    await openAssignments(page);
    const started = await startAssignment(page, {
      objective,
      measureLabel: 'Sum Total',
      content: '## Summary\n\nTotal ${source-1.value}\n\n## Sources\n\n- scotch-parts.xlsx',
    });
    const runId = await runIdForObjective(objective);
    const cards = await page.locator('[data-testid^="mapping-current-"]').count();
    const before = await screenshot(page, '03-mapping-before-revision');
    const current = (await state()).dataset_version;
    const changed = 'b'.repeat(40);
    const set = await getJson(`${API}/_acceptance/source-version`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_name: 'scotch_parts_price_list', content_hash: changed,
      }),
    });
    await correctMapping(page, 'Unit Price');
    const errorText = (await page.locator('.text-rose-700').allInnerTexts()).join(' ');
    const after = await screenshot(page, '04-revision-refused');
    const detail = await assignmentDetail(page);
    const mappingText = (await page.locator('[data-testid^="mapping-current-"]').allInnerTexts()).join(' ');
    const refused = /stale|changed|revision|version/i.test(errorText);
    const completedPreserved = /completed/.test(detail.text) && /85\.00/.test(detail.text);
    const mappingPreserved = /Total → Total/.test(mappingText)
      && !/Total → Unit Price/.test(mappingText);
    await getJson(`${API}/_acceptance/source-version`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_name: 'scotch_parts_price_list', content_hash: current,
      }),
    });
    const ok = set.status === 200 && cards >= 2 && refused
      && completedPreserved && mappingPreserved;
    record('changed source revision invalidates stale work', ok, {
      objective, runId, cards, errorText,
      completedPreserved, mappingPreserved,
      screenshots: [before, after],
    });
    return { objective, runId };
  } finally {
    await context.close();
  }
}

async function scenarioAmbiguity(browser) {
  const objective = `Recovery ambiguous mapping ${Date.now()}`;
  const { context, page } = await newPage(browser);
  try {
    await openAssignments(page);
    await startAssignment(page, {
      objective,
      measureLabel: 'Sum Total',
      content: '## Summary\n\nTotal ${source-1.value}\n\n## Sources\n\n- scotch-parts.xlsx',
    });
    const runId = await runIdForObjective(objective);
    const cards = await page.locator('[data-testid^="mapping-current-"]').all();
    let correctable = 0;
    let disabled = 0;
    for (const card of cards) {
      const button = card.getByRole('button', { name: /Correct mapping/ });
      if (await button.isDisabled()) disabled += 1;
      else correctable += 1;
    }
    const before = await screenshot(page, '05-ambiguous-mappings');
    const unbound = await getJson(`${API}/api/assignments/${runId}/mappings/correct`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        concept: 'Total', expected_revision: 1, column: 'Unit Price',
      }),
    });
    const ambiguousRefusal = unbound.status === 409
      && /more than one confirmed mapping/i.test(JSON.stringify(unbound.body));
    await correctMapping(page, 'Unit Price');
    await page.waitForTimeout(1200);
    const mappingText = (await page.locator('[data-testid^="mapping-current-"]').allInnerTexts()).join(' ');
    const resolved = /Total → Unit Price/.test(mappingText);
    const after = await screenshot(page, '06-ambiguous-resolved');
    const ok = cards.length >= 2 && correctable === 1 && disabled >= 1
      && ambiguousRefusal && resolved;
    record('ambiguous mapping identity', ok, {
      objective, runId, cards: cards.length, correctable, disabled,
      unboundStatus: unbound.status, unboundBody: unbound.body,
      ambiguousRefusal, resolved,
      screenshots: [before, after],
    });
    return { objective, runId };
  } finally {
    await context.close();
  }
}

async function scenarioCancellation(browser) {
  const objective = `Recovery cancellation ${Date.now()}`;
  const correlation = `corr-cancel-${Date.now()}`;
  const { context, page } = await newPage(browser);
  try {
    await openAssignments(page);
    await startAssignment(page, {
      objective,
      expression: '2*10 + 3*20',
      content: '## Summary\n\nTotal ${calculate.value}\n\n## Sources\n\n- scotch-parts.xlsx',
      correlation,
    });
    const runId = await runIdForObjective(objective);
    const beforeEffects = await outboxCount();
    await page.getByRole('button', { name: /^Cancel$/ }).click();
    await waitFor(async () => (
      /cancelled/.test(await page.locator('[data-testid="assignment-detail"]').innerText())
    ), 20000);
    const cancelled = await screenshot(page, '07-cancelled');
    await page.reload({ waitUntil: 'networkidle', timeout: 120000 });
    await waitFor(async () => (
      await page.locator('[data-testid^="assignment-summary-"]').count() > 0
    ), 45000);
    await selectAssignment(page, objective);
    const afterReload = await assignmentDetail(page);
    const persisted = /cancelled/.test(afterReload.text);
    const late = await getJson(
      `${API}/api/assignments/${runId}/responses/${encodeURIComponent(correlation)}`,
      {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response: 'late reply after cancellation' }),
      },
    );
    const lateBodyText = JSON.stringify(late.body);
    const lateRefused = late.status >= 400
      || /cancel|unmatched|closed|not.*open/i.test(lateBodyText);
    const afterEffects = await outboxCount();
    const ok = persisted && lateRefused && beforeEffects === afterEffects;
    record('cancellation refuses a late response', ok, {
      objective, runId, persisted, lateStatus: late.status,
      lateBody: late.body, beforeEffects, afterEffects,
      screenshots: [cancelled],
    });
    return { objective, runId };
  } finally {
    await context.close();
  }
}

async function scenarioDuplicateResume(browser) {
  const objective = `Recovery duplicate resume ${Date.now()}`;
  const correlation = `corr-dup-${Date.now()}`;
  const first = await newPage(browser);
  const second = await newPage(browser);
  try {
    await openAssignments(first.page);
    await startAssignment(first.page, {
      objective,
      expression: '2*10 + 3*20',
      content: '## Summary\n\nTotal ${calculate.value}\n\n## Sources\n\n- scotch-parts.xlsx',
      correlation,
    });
    const runId = await runIdForObjective(objective);
    await openAssignments(second.page);
    await selectAssignment(second.page, objective);
    await selectAssignment(first.page, objective);
    await first.page.getByLabel('Correlated response').fill('duplicate reply one');
    await second.page.getByLabel('Correlated response').fill('duplicate reply one');
    const beforeEffects = await outboxCount();
    const clicks = await Promise.allSettled([
      first.page.getByRole('button', { name: /Deliver/ }).click(),
      second.page.getByRole('button', { name: /Deliver/ }).click(),
    ]);
    await waitFor(async () => {
      const detail = await assignmentStatus(runId);
      const status = detail && detail.assignment && detail.assignment.status;
      return status === 'completed' || status === 'partial' || status === 'waiting';
    }, 45000).catch(() => {});
    await first.page.waitForTimeout(2500);
    const detail = await assignmentStatus(runId);
    const steps = (detail.assignment && detail.assignment.steps) || [];
    const calcSteps = steps.filter((step) => step.adapter === 'formula.calculate');
    const calcResults = calcSteps.reduce(
      (count, step) => count + (step.status === 'applied' ? 1 : 0), 0);
    const priorResults = calcSteps.reduce(
      (count, step) => count + Number(step.prior_result_count || 0), 0);
    const afterEffects = await outboxCount();
    const shot = await screenshot(first.page, '08-duplicate-resume');
    const ok = clicks.filter((item) => item.status === 'fulfilled').length >= 1
      && calcSteps.length === 1 && calcResults === 1 && priorResults === 0
      && beforeEffects === afterEffects
      && ['completed', 'partial'].includes(detail.assignment.status);
    record('duplicate concurrent resume dispatches once', ok, {
      objective, runId, clicks: clicks.map((item) => item.status),
      calcSteps: calcSteps.length, calcResults, priorResults,
      status: detail.assignment.status, beforeEffects, afterEffects,
      screenshots: [shot],
    });
    return { objective, runId };
  } finally {
    await first.context.close();
    await second.context.close();
  }
}

function fileHash(relative) {
  const absolute = path.join(ROOT, relative);
  if (!fs.existsSync(absolute)) return null;
  return crypto.createHash('sha256').update(fs.readFileSync(absolute)).digest('hex');
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  fs.mkdirSync(SCREENSHOTS, { recursive: true });
  server = await startServer(true);
  const resetPid = (await state()).pid;
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  let results = [];
  try {
    results.push(await scenarioWaitRestartResume(browser));
    results.push(await scenarioRevisionInvalidation(browser));
    results.push(await scenarioAmbiguity(browser));
    results.push(await scenarioCancellation(browser));
    results.push(await scenarioDuplicateResume(browser));
  } finally {
    await browser.close();
    await stopServer();
  }
  const passed = checks.filter((item) => item.ok).length;
  const payload = {
    schema: 'atom-assignment-recovery-browser-1',
    generated_at: new Date().toISOString(),
    ui_base: UI,
    api_base: API,
    world: WORLD,
    backend_reset_pid: resetPid,
    scenarios: results,
    checks,
    passed,
    failed: checks.length - passed,
    outbox_effects: 0,
    source: {
      backend_head: process.env.ASSIGNMENT_SOURCE_HEAD || null,
      files: {
        'backend/scripts/assignment_browser_acceptance_server.py':
          fileHash('backend/scripts/assignment_browser_acceptance_server.py'),
        'backend/core/assignment_executor.py':
          fileHash('backend/core/assignment_executor.py'),
        'backend/api/assignment_routes.py':
          fileHash('backend/api/assignment_routes.py'),
        'frontend-nextjs/components/assignments/AssignmentPanel.tsx':
          fileHash('frontend-nextjs/components/assignments/AssignmentPanel.tsx'),
      },
    },
  };
  fs.writeFileSync(path.join(OUT, 'browser-recovery.json'),
    JSON.stringify(payload, null, 2) + '\n');
  log(`EVIDENCE ${path.join(OUT, 'browser-recovery.json')}`);
  log(`RESULT ${passed}/${checks.length} checks passed`);
  process.exit(passed === checks.length ? 0 : 1);
})().catch(async (error) => {
  console.error(error);
  await stopServer();
  process.exit(2);
});
