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
const { execSync, spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
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

function portFree(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: "127.0.0.1", port });
    const finish = (free) => {
      socket.destroy();
      resolve(free);
    };
    socket.setTimeout(800);
    socket.once("connect", () => finish(false));
    socket.once("timeout", () => finish(true));
    socket.once("error", () => finish(true));
  });
}

async function startServer(reset) {
  if (!(await portFree(PORT))) {
    throw new Error(
      `port ${PORT} is already occupied; refusing to reuse an unknown server`);
  }
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
  const state = await waitFor(async () => {
    const response = await getJson(
      `${API}/_acceptance/state`).catch(() => null);
    return response && response.status === 200 && response.body.ok
      ? response.body : null;
  }, 45000);
  if (state.pid !== child.pid
      || state.world !== WORLD
      || state.database !== path.join(WORLD, "atom.db")) {
    child.kill("SIGTERM");
    throw new Error(
      `port ${PORT} is served by pid ${state.pid} in world ${state.world}; `
      + `the spawned process is ${child.pid} in ${WORLD}`);
  }
  child.__acceptanceState = state;
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

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const expectedHead = execSync("git rev-parse HEAD", { cwd: ROOT })
    .toString().trim();
  const expectedDirty = execSync("git status --porcelain", { cwd: ROOT })
    .toString().trim().length > 0;
  if (process.env.BRENNAN_REQUIRE_CLEAN !== "0" && expectedDirty) {
    throw new Error(
      "browser gate requires a frozen clean source; commit the candidate "
      + "before running (or set BRENNAN_REQUIRE_CLEAN=0 for development)");
  }
  server = await startServer(true);
  const oldPid = server.pid;
  const health = (await getJson(`${API}/api/health`)).body;
  const initialState = health;
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
  const answerTextGaps = async (detail) => {
    for (let index = 0; index < 5; index += 1) {
      const inputs = detail.getByLabel("Gap answer");
      if (await inputs.count() === 0) break;
      await inputs.first().fill("unlicensed");
      await detail.getByLabel(/Resolve gap:/).first().click();
      await page.waitForTimeout(600);
    }
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
  const restartedHealth = (await getJson(`${API}/api/health`)).body;
  const oldIdentity = initialState.identity || {};
  const newIdentity = restartedHealth.identity || {};
  const expectedSourceId = expectedDirty
    ? null : expectedHead.slice(0, 12);
  const sourceMatches = expectedDirty
    ? newIdentity.dirty === true
      && String(newIdentity.source_id).startsWith(
        `${expectedHead.slice(0, 12)}-dirty.`)
    : newIdentity.dirty === false
      && newIdentity.source_id === expectedSourceId;
  const codeIdentityOk =
    newIdentity.revision === expectedHead
    && sourceMatches
    && newIdentity.source_id === oldIdentity.source_id
    && newIdentity.instance_id !== oldIdentity.instance_id
    && restartedHealth.pid === newPid
    && initialState.pid === oldPid
    && restartedHealth.process_start
    && restartedHealth.process_start !== initialState.process_start
    && restartedHealth.world === WORLD
    && restartedHealth.database === path.join(WORLD, "atom.db")
    && restartedHealth.repo_root === ROOT
    && restartedHealth.backend_root === path.join(ROOT, "backend");
  record("restarted backend serves the declared code identity",
         codeIdentityOk,
         { expected_head: expectedHead,
           expected_dirty: expectedDirty,
           old_pid: oldPid, new_pid: newPid,
           old_instance: oldIdentity.instance_id,
           new_instance: newIdentity.instance_id,
           old_source_id: oldIdentity.source_id,
           new_source_id: newIdentity.source_id,
           dirty: newIdentity.dirty,
           world: restartedHealth.world,
           database: restartedHealth.database,
           repo_root: restartedHealth.repo_root,
           backend_root: restartedHealth.backend_root });
  record("health and connected routes identify the same instance",
         restartedHealth.pid === restartedState.pid
         && restartedHealth.identity?.instance_id
            === restartedState.identity?.instance_id,
         { health_pid: restartedHealth.pid,
           connected_pid: restartedState.pid,
           health_instance: restartedHealth.identity?.instance_id,
           connected_instance: restartedState.identity?.instance_id });
  record("connected provider still serves the pre-change source",
         restartedState.version === "v1",
         { version: restartedState.version });
  detail = await openAssignment();
  await detail.getByText(/Which qualification applies/i).waitFor({
    state: "visible", timeout: 20000 });
  record("obligation survives backend restart", true,
         { run_id: runId });
  await answerTextGaps(detail);
  await detail.getByText(/Approval required/).first().waitFor({
    state: "visible", timeout: 20000 });
  const v1Raw = (await getJson(
    `${API}/_acceptance/connected/run/${runId}`)).body.assignment;
  const v1Calc = v1Raw.steps.find((step) => step.step_id === "calculate");
  const v1Rows = v1Calc.result.rows || [];
  record("v1 calculation completes before correction",
         v1Calc.status === "applied"
         && v1Calc.result.value === "362.50"
         && v1Rows.length > 0
         && v1Rows.every((row) => row.source_ref?.version === "v1"),
         { value: v1Calc.result.value,
           versions: [...new Set(v1Rows.map(
             (row) => row.source_ref?.version))] });
  const v1Screenshot = await screenshot(page, "02-v1-completed-calculation");
  record("v1 calculation captured before correction", true,
         { screenshot: v1Screenshot });

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
  await answerTextGaps(detail);
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
  const priorRows = (calcStep.prior_results || []).flatMap(
    (item) => (item.result && item.result.rows) || item.rows || []);
  record("v1 remains only in historical result",
         priorRows.length > 0
         && priorRows.every((row) => row.source_ref?.version === "v1"),
         { prior_row_count: priorRows.length,
           versions: [...new Set(priorRows.map(
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
