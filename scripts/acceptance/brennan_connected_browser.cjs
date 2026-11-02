#!/usr/bin/env node
/**
 * Browser gate: connected bytes -> parsed evidence -> clarification -> leave
 * -> backend restart -> changed source -> corrected continuation -> verified
 * estimate -> Outlook draft (no send).
 *
 * The backend is the standalone assignment acceptance server (real routes,
 * executor, sqlite world) with controlled connected providers. User actions
 * go through the real Assignments page.
 */
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "../..");
let playwright;
try {
  playwright = require("playwright");
} catch {
  playwright = require(path.join(ROOT, "frontend-nextjs/node_modules/playwright"));
}
const { chromium } = playwright;

const UI = process.env.BRENNAN_UI_BASE || "http://127.0.0.1:3003";
const API = process.env.BRENNAN_API_BASE || "http://127.0.0.1:8090";
const WORLD = process.env.BRENNAN_BROWSER_WORLD
  || "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    + "brennan-connected-browser";
const OUT = process.env.BRENNAN_BROWSER_OUT
  || path.join(ROOT, "docs/acceptance/evidence/brennan_connected_browser_20261101");
const PYTHON = process.env.BRENNAN_PYTHON
  || "/Users/rushiparikh/projects/atom/backend/venv314/bin/python";
const SERVER = path.join(
  ROOT, "backend/scripts/assignment_browser_acceptance_server.py");
const PORT = Number(new URL(API).port || 8090);
const checks = [];
let server = null;

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function log(...args) {
  console.log(new Date().toISOString(), ...args);
}
function record(name, ok, detail) {
  checks.push({ name, ok: !!ok, detail });
  log(ok ? "PASS" : "FAIL", name,
      detail === undefined ? "" : JSON.stringify(detail).slice(0, 1200));
}
async function getJson(url, init) {
  const response = await fetch(url, init);
  const text = await response.text();
  let body;
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
    } catch (error) { last = error; }
    await sleep(intervalMs);
  }
  throw new Error(`timed out: ${last && last.message ? last.message : last}`);
}

async function startServer(reset) {
  const env = {
    ...process.env,
    ATOM_ASSIGNMENT_BROWSER_WORLD: WORLD,
    ATOM_ASSIGNMENT_BROWSER_WORLD_RESET: reset ? "1" : "0",
    ATOM_ASSIGNMENT_BROWSER_PORT: String(PORT),
    ATOM_ASSIGNMENT_ALLOW_PROPOSED_STEPS: "1",
    ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS: "1",
    ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT: WORLD,
    ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT: "1",
    ATOM_ASSIGNMENT_OUTBOX: path.join(WORLD, "outbox.jsonl"),
    PYTHONPATH: [
      ROOT, path.join(ROOT, "backend"), process.env.PYTHONPATH || "",
    ].filter(Boolean).join(":"),
  };
  fs.mkdirSync(OUT, { recursive: true });
  const child = spawn(PYTHON, [SERVER], {
    cwd: path.join(ROOT, "backend"), env, stdio: ["ignore", "pipe", "pipe"],
  });
  const logPath = path.join(
    OUT, reset ? "backend-reset.log" : "backend-restart.log");
  const stream = fs.createWriteStream(logPath, { flags: "a" });
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
  server.kill("SIGTERM");
  await waitFor(() => {
    try { process.kill(pid, 0); return false; } catch { return true; }
  }, 20000).catch(() => {});
  server = null;
  await sleep(700);
}

async function screenshot(page, name) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

const SOURCE_V1 = [
  "sku,category,quantity,unit,pack,unit_price,currency,discount_percent",
  "A,A,2,each,1,100.00,USD,0",
  "B,B,3,each,1,50.00,USD,0",
].join("\n");
const SOURCE_V2 = SOURCE_V1.replace("B,B,3,each,1,50.00", "B,B,3,each,1,55.00");

function planSteps(objective, ref) {
  return [
    {
      step_id: "read", title: "Read connected price bytes",
      operation_type: "retrieve", adapter: "action.registry",
      inputs: { action: "connected.workdrive.read_file",
                arguments: { file_id: "price-file", evidence_kind: "price_rows" } },
      effect: "read_only",
    },
    {
      step_id: "map", title: "Map parsed rows to quote lines",
      operation_type: "calculate", adapter: "quote.lines_from_rows",
      depends_on: ["read"],
      inputs: {
        rows: { $ref: "read.data.rows" },
        columns: {
          item_id: "sku", quantity: "quantity", unit: "unit",
          pack_size: "pack", unit_price: "unit_price",
          currency: "currency", description: "sku",
          category: "category", discount: "discount_percent",
        },
        defaults: { price_basis: "contract" },
        discount_mode: "percent", discount_authority: "price-list:v1",
        source_ref: { resource_id: "price-file", version: "v1" },
      },
      effect: "local",
    },
    {
      step_id: "calculate", title: "Calculate the quote",
      operation_type: "calculate", adapter: "quote.calculate",
      depends_on: ["map"],
      inputs: {
        line_items: { $ref: "map.line_items" },
        currency: "USD", freight: "20.00", tax: { basis: "none" },
        discount_rules: [
          { lesson_id: "general-b", revision: 1, name: "general B",
            when: { category: "B" }, rate: "0.05" },
          { lesson_id: "licensed-b", revision: 1, name: "licensed B",
            when: { category: "B", qualification: "licensed" },
            rate: "0.10" },
        ],
        rounding: "half_up", scale: 2,
        rounding_authority: "agreement:round-half-up-2dp",
      },
      effect: "local",
    },
    {
      step_id: "prepare-lines", title: "Prepare provider estimate lines",
      operation_type: "calculate", adapter: "quote.estimate_lines",
      depends_on: ["calculate"],
      inputs: { rows: { $ref: "calculate.rows" },
                account_map: { A: "acct-1", B: "acct-1" } },
      effect: "local",
    },
    {
      step_id: "estimate", title: "Create the verified estimate",
      operation_type: "outbound", adapter: "action.registry",
      depends_on: ["prepare-lines"],
      inputs: {
        action: "connected.books.create_estimate",
        arguments: {
          organization_id: "org-browser",
          estimate_data: {
            customer_id: "customer-1",
            reference_number: ref,
            date: "2026-11-01", currency_code: "USD",
            total: "${calculate.value}",
            sub_total: "${calculate.value}",
            tax_total: "0.00",
            line_items: { $ref: "prepare-lines.line_items" },
          },
          authority_reference: "grant-browser-1",
          operation_id: `op-browser-${ref}`,
        },
      },
      effect: "external", approval_required: true,
      approval_purpose: "Create the estimate",
    },
    {
      step_id: "email-draft", title: "Create the Outlook draft",
      operation_type: "outbound", adapter: "action.registry",
      depends_on: ["estimate"],
      inputs: {
        action: "connected.outlook.create_draft",
        arguments: {
          to: ["buyer@example.invalid"],
          subject: `Quote ${ref}`,
          body: "Quoted total: ${calculate.value} USD",
          operation_id: `op-draft-${ref}`,
        },
      },
      effect: "external", approval_required: true,
      approval_purpose: "Create the Outlook draft",
    },
  ];
}

async function startConnectedAssignment(health, label) {
  const objective = `Browser control ${label} ${Date.now()}`;
  const ref = `RFQ-CONTROL-${label}-${Date.now()}`;
  const planResponse = await getJson(
    `${API}/_acceptance/connected/plan?objective=${encodeURIComponent(objective)}&ref=${encodeURIComponent(ref)}`);
  if (planResponse.status !== 200) {
    throw new Error(`control plan failed: ${planResponse.status} ${JSON.stringify(planResponse.body)}`);
  }
  const created = await getJson(`${API}/api/assignments`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      objective, agent_id: health.agent_id,
      sources: [{
        kind: "document", representation: "file",
        internal_fixture: true, path: health.document,
        resource_id: "browser-source",
      }],
      proposed_steps: planResponse.body.steps,
      authorized_actions: ["calculate", "outbound"],
      deliverables: [{
        kind: "email_draft", step_id: "email-draft",
        description: "Quote email",
        to: ["buyer@example.invalid"],
        subject: `Quote ${ref}`,
        body: "Quoted total: ${calculate.value} USD",
      }],
      task_context: { audience: "quote-reviewer" },
    }),
  });
  if (created.status !== 200) {
    throw new Error(`control start failed: ${created.status} ${JSON.stringify(created.body)}`);
  }
  return { runId: created.body.run_id, objective, ref };
}

async function waitForOpenGap(runId, concept) {
  return waitFor(async () => {
    const state = await getJson(`${API}/api/assignments/${runId}`);
    if (state.status !== 200) return null;
    return (state.body.open_gaps || []).find(
      (gap) => gap.status === "open" && gap.concept === concept) || null;
  }, 30000);
}

async function resolveGap(runId, gap, resolution) {
  return getJson(
    `${API}/api/assignments/${runId}/gaps/${gap.question_id}/resolve`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ resolution }),
    });
}

async function waitForPreparedApproval(runId, stepId) {
  return waitFor(async () => {
    const state = await getJson(`${API}/api/assignments/${runId}`);
    if (state.status !== 200) return null;
    const step = (state.body.assignment.steps || []).find(
      (item) => item.step_id === stepId);
    const request = (step && step.approval_request) || {};
    return step && request.hitl_action_id ? step : null;
  }, 30000);
}

async function approvalState(runId, stepId) {
  const state = await getJson(`${API}/api/assignments/${runId}`);
  return {
    status: state.body.assignment?.status,
    step: (state.body.assignment?.steps || []).find(
      (item) => item.step_id === stepId),
    operations: state.body.operations || [],
  };
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  server = await startServer(true);
  const oldPid = server.pid;
  const health = (await getJson(`${API}/api/health`)).body;
  const objective = `Browser connected quote ${Date.now()}`;
  const ref = `RFQ-BROWSER-${Date.now()}`;
  const planResponse = await getJson(
    `${API}/_acceptance/connected/plan?objective=${encodeURIComponent(objective)}&ref=${encodeURIComponent(ref)}`);
  if (planResponse.status !== 200) {
    throw new Error(`plan failed: ${planResponse.status} ${JSON.stringify(planResponse.body)}`);
  }
  const created = await getJson(`${API}/api/assignments`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      objective, agent_id: health.agent_id,
      sources: [{
        kind: "document", representation: "file",
        internal_fixture: true, path: health.document,
        resource_id: "browser-source",
      }],
      proposed_steps: planResponse.body.steps,
      authorized_actions: ["calculate", "outbound"],
      deliverables: [{
        kind: "email_draft", step_id: "email-draft",
        description: "Quote email",
        to: ["buyer@example.invalid"],
        subject: `Quote ${ref}`,
        body: "Quoted total: ${calculate.value} USD",
      }],
      task_context: { audience: "quote-reviewer" },
    }),
  });
  if (created.status !== 200) {
    throw new Error(`start failed: ${created.status} ${JSON.stringify(created.body)}`);
  }
  const runId = created.body.run_id;
  record("assignment starts and pauses on discount qualification",
         created.body.assignment.assignment.status === "waiting",
         { run_id: runId, status: created.body.assignment.assignment.status });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.addCookies([{
    name: "auth_token", value: "browser-acceptance-token",
    domain: "127.0.0.1", path: "/",
  }]);
  const page = await context.newPage();
  const openAssignment = async () => {
    await page.goto(`${UI}/assignments`);
    const row = page.getByRole("button").filter({ hasText: objective }).first();
    await row.waitFor({ state: "visible", timeout: 20000 });
    await row.click();
    const detail = page.getByTestId("assignment-detail");
    await detail.waitFor({ state: "visible", timeout: 20000 });
    return detail;
  };

  let detail = await openAssignment();
  await detail.getByText(/Which qualification applies/i).waitFor({
    state: "visible", timeout: 20000 });
  const beforeRestart = await screenshot(page, "01-qualification-before-restart");

  // Leave, restart the real backend process, then resume from the browser.
  await page.goto(`${UI}/assignments`);
  await stopServer();
  server = await startServer(false);
  const newPid = server.pid;
  record("real backend process restarted", oldPid !== newPid,
         { old_pid: oldPid, new_pid: newPid });
  const restartedState = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  record("restarted backend serves source identity",
         restartedState.version === "v1",
         restartedState);
  detail = await openAssignment();
  await detail.getByText(/Which qualification applies/i).waitFor({
    state: "visible", timeout: 20000 });
  record("obligation survives backend restart", true,
         { run_id: runId });

  // Change the connected source bytes and invalidate the read branch.
  const changed = await getJson(`${API}/_acceptance/connected/source`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ content: SOURCE_V2, version: "v2" }),
  });
  record("connected source changed", changed.status === 200, changed.body);
  const invalidated = await getJson(
    `${API}/api/assignments/${runId}/invalidate/read`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ reason: "connected price list changed" }),
    });
  record("changed source invalidates read branch", invalidated.status === 200,
         { status: invalidated.status, run_id: runId });

  detail = await openAssignment();
  await detail.getByText(/qualification applies|authorized source version changed/i)
    .first().waitFor({ state: "visible", timeout: 20000 });
  // The source change creates a reassessment obligation; the prior scope
  // question may still be visible. Answer every text obligation before the
  // corrected calculation can proceed.
  for (let index = 0; index < 5; index += 1) {
    const inputs = detail.getByLabel("Gap answer");
    if (await inputs.count() === 0) break;
    await inputs.first().fill("unlicensed");
    await detail.getByLabel(/Resolve gap:/).first().click();
    await page.waitForTimeout(600);
  }
  await detail.getByText(/Approval required/).first().waitFor({
    state: "visible", timeout: 20000 });
  const corrected = await screenshot(page, "02-corrected-quote-approval");
  record("corrected continuation reaches estimate approval", true,
         { screenshot: corrected });
  const rawRun = (await getJson(
    `${API}/_acceptance/connected/run/${runId}`)).body.assignment;
  const readStep = rawRun.steps.find((step) => step.step_id === "read");
  const calcStep = rawRun.steps.find((step) => step.step_id === "calculate");
  const readReceipt = readStep.result.data.read_receipt;
  record("production WorkDrive receipt identifies v2",
         readReceipt.version === "v2"
         && readReceipt.fields.sha256
         && readReceipt.coverage === "complete",
         { version: readReceipt.version,
           sha256: readReceipt.fields.sha256,
           coverage: readReceipt.coverage });
  const currentRows = calcStep.result.rows || [];
  record("corrected calculation rows use v2 source identity",
         currentRows.length > 0
         && currentRows.every((row) => row.source_ref?.version === "v2"
           && row.source_ref?.sha256),
         { row_count: currentRows.length,
           versions: [...new Set(currentRows.map(
             (row) => row.source_ref?.version))] });
  const priorReads = (readStep.prior_results || []).map(
    (item) => (item.result || item).data?.read_receipt).filter(Boolean);
  const priorRows = (calcStep.prior_results || []).flatMap(
    (item) => (item.result || item).rows || []);
  record("v1 remains only in historical result",
         priorReads.length > 0
         && priorReads.every((receipt) => receipt.version === "v1")
         && readReceipt.version === "v2"
         && priorRows.every((row) => row.source_ref?.version === "v1"),
         { prior_read_versions: priorReads.map(
             (receipt) => receipt.version),
           current_read_version: readReceipt.version,
           prior_row_count: priorRows.length,
           prior_row_versions: [...new Set(priorRows.map(
             (row) => row.source_ref?.version))] });

  // Approve the estimate, verify the readback, then approve the draft.
  await detail.getByRole("button", { name: /Approve this payload/ }).first()
    .click();
  await detail.getByText(/376.75/).first().waitFor({
    state: "visible", timeout: 20000 });
  const estimateState = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  record("estimate readback uses corrected total",
         estimateState.estimates.some((item) => item.total === "376.75"),
         estimateState.estimates);
  await detail.getByRole("button", { name: /Approve this payload/ }).first()
    .click();
  await detail.getByText("completed", { exact: true }).waitFor({
    state: "visible", timeout: 25000 });
  const finalState = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  const draft = finalState.drafts[0] || {};
  record("Outlook draft uses verified corrected total",
         String(draft.body || "").includes("376.75"), draft);
  record("no send occurred", finalState.drafts.length === 1 &&
         !String(draft.body || "").toLowerCase().includes("sent"), draft);
  await screenshot(page, "03-completed-draft");

  await page.reload();
  detail = await openAssignment();
  await detail.getByText("completed", { exact: true }).waitFor({
    state: "visible", timeout: 20000 });
  record("completed assignment reopens after reload", true, { run_id: runId });

  // Control: a repeated resume after completion must not create a second
  // external effect.
  const duplicateBefore = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  const firstResume = await getJson(
    `${API}/api/assignments/${runId}/resume`, { method: "POST" });
  const secondResume = await getJson(
    `${API}/api/assignments/${runId}/resume`, { method: "POST" });
  const duplicateAfter = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  record("duplicate resume after completion is a no-op",
         firstResume.status === 200 && secondResume.status === 200
         && duplicateAfter.estimates.length === duplicateBefore.estimates.length
         && duplicateAfter.drafts.length === duplicateBefore.drafts.length,
         { status: secondResume.body.assignment?.status,
           estimates: duplicateAfter.estimates.length,
           drafts: duplicateAfter.drafts.length });

  // Control: cancellation is terminal. Resuming or answering a gap after
  // cancellation must neither revive the run nor create an effect.
  const cancelEffectsBefore = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  const cancelRun = await startConnectedAssignment(health, "cancel");
  const cancelGap = await waitForOpenGap(cancelRun.runId, "discount_scope");
  const cancelled = await getJson(
    `${API}/api/assignments/${cancelRun.runId}/cancel`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ reason: "cancellation control" }),
    });
  const resumedCancelled = await getJson(
    `${API}/api/assignments/${cancelRun.runId}/resume`, { method: "POST" });
  const revived = await resolveGap(cancelRun.runId, cancelGap, "unlicensed");
  const cancelEffectsAfter = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  record("cancellation is terminal and creates no effect",
         cancelled.status === 200
         && cancelled.body.assignment.status === "cancelled"
         && resumedCancelled.body.assignment?.status === "cancelled"
         && revived.status === 409
         && cancelEffectsAfter.estimates.length
            === cancelEffectsBefore.estimates.length
         && cancelEffectsAfter.drafts.length === cancelEffectsBefore.drafts.length,
         { cancelled_status: cancelled.body.assignment.status,
           resume_status: resumedCancelled.body.assignment?.status,
           gap_status: revived.status,
           estimates: cancelEffectsAfter.estimates.length,
           drafts: cancelEffectsAfter.drafts.length });

  // Control: the provider lands the estimate but the response is lost. The
  // step must be uncertain (never "failed"), and reconciliation must settle
  // the ORIGINAL effect without another create.
  const uncertainRun = await startConnectedAssignment(health, "uncertain");
  const uncertainGap = await waitForOpenGap(uncertainRun.runId, "discount_scope");
  await resolveGap(uncertainRun.runId, uncertainGap, "unlicensed");
  await waitForPreparedApproval(uncertainRun.runId, "estimate");
  const pendingBefore = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  const pendingResumeOne = await getJson(
    `${API}/api/assignments/${uncertainRun.runId}/resume`, { method: "POST" });
  const pendingResumeTwo = await getJson(
    `${API}/api/assignments/${uncertainRun.runId}/resume`, { method: "POST" });
  const pendingAfter = await approvalState(uncertainRun.runId, "estimate");
  const pendingEffects = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  record("duplicate resume while approval is pending is a no-op",
         pendingResumeOne.status === 200 && pendingResumeTwo.status === 200
         && pendingAfter.step?.status === "awaiting_approval"
         && pendingEffects.estimates.length === pendingBefore.estimates.length
         && pendingEffects.calls === pendingBefore.calls,
         { step_status: pendingAfter.step?.status,
           estimates: pendingEffects.estimates.length,
           calls: pendingEffects.calls });
  const faultBefore = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  const fault = await getJson(`${API}/_acceptance/connected/fault`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ estimate_fail_after_apply: 1 }),
  });
  const approvedLost = await getJson(
    `${API}/api/assignments/${uncertainRun.runId}/approve/estimate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ note: "uncertainty control" }),
    });
  const afterLost = await approvalState(uncertainRun.runId, "estimate");
  const faultAfter = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  record("lost provider response is uncertain, not failed",
         fault.status === 200 && approvedLost.status === 200
         && afterLost.step?.status === "uncertain"
         && afterLost.operations.some((operation) => (
           operation.step_id === "estimate" && operation.status === "uncertain"
           && operation.needs_reconciliation))
         && faultAfter.estimates.length === faultBefore.estimates.length + 1
         && faultAfter.fail_estimate_after_apply === 0,
         { fault: fault.body,
           approved: approvedLost.status,
           step_status: afterLost.step?.status,
           estimate_delta:
             faultAfter.estimates.length - faultBefore.estimates.length,
           needs_reconciliation: afterLost.operations
             .filter((operation) => operation.step_id === "estimate")
             .map((operation) => operation.needs_reconciliation) });

  const landed = faultAfter.estimates[faultAfter.estimates.length - 1];
  const reconciled = await getJson(
    `${API}/api/assignments/${uncertainRun.runId}/reconcile/estimate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        verdict: "applied",
        evidence: `controlled provider readback shows ${landed.estimate_id} `
          + `(${landed.reference_number}) persisted once`,
        evidence_ref: `${API}/_acceptance/connected/state`,
      }),
    });
  const afterReconcile = await approvalState(
    uncertainRun.runId, "estimate");
  const reconciledEffects = (await getJson(
    `${API}/_acceptance/connected/state`)).body;
  record("reconciliation settles the original effect without a duplicate",
         reconciled.status === 200
         && afterReconcile.step?.status === "applied"
         && reconciledEffects.estimates.length === faultAfter.estimates.length
         && reconciledEffects.calls === faultAfter.calls,
         { reconciled: reconciled.status,
           step_status: afterReconcile.step?.status,
           estimates: reconciledEffects.estimates.length,
           calls: reconciledEffects.calls,
           landed: landed.estimate_id });

  // Leave no pending work from the controls.
  await getJson(`${API}/api/assignments/${uncertainRun.runId}/cancel`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ reason: "uncertainty control complete" }),
  });

  await browser.close();
  fs.writeFileSync(path.join(OUT, "checks.json"),
                   JSON.stringify(checks, null, 2));
  const failed = checks.filter((item) => !item.ok);
  log(`RESULT ${checks.length - failed.length}/${checks.length} checks`);
  if (failed.length) process.exitCode = 1;
}

main().catch(async (error) => {
  log("ERROR", error && error.stack ? error.stack : String(error));
  try { await screenshot(await (await chromium.launch()).newPage(),
                         "99-failure"); } catch { /* noop */ }
  await stopServer();
  process.exit(1);
}).finally(async () => {
  await stopServer();
});
