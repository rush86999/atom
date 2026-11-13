#!/usr/bin/env node
/**
 * WA-075 — signed-in settings acceptance.
 *
 * Proves the Settings tabs a signed-in operator actually touches, on the
 * isolated whole-app world (never the live dev database, never a real
 * credential, never an external model provider):
 *
 *   Account      profile read-back + password rotation saved, reloaded and
 *                restored; 2FA surface probed (and optionally exercised)
 *   AI           provider routing policy saved, reloaded and restored
 *   Sessions     a disposable secondary session is signed in and session
 *                management is attempted through the tab
 *   Routing      real /api/chat/routing-stats payload loads, renders exactly,
 *                and Refresh fetches again (empty telemetry stays empty)
 *   Local Models a disposable provider is registered, survives reload, and is
 *                deleted; the provider is never contacted
 *
 * Reuses `scripts/acceptance/browser_core_surface.mjs`'s world contract via
 * `lib/core_surface_session.mjs` (same env vars, same scratch login, same
 * Chrome/Playwright import, same frontend-wait retry).
 *
 * Every check is recorded explicitly with one of four statuses:
 *
 *   pass     proven at the boundary the user touches
 *   fail     the product did something the check says it must not do
 *   missing  the capability is absent (reported with the exact evidence);
 *            this does NOT silently pass and it does NOT count as a regression
 *   skipped  precondition not met, with the reason recorded
 *
 * Exit codes: 0 all checks pass, 1 at least one fail, 2 fatal (world/auth
 * unreachable or identity unverified), 3 no failures but at least one missing
 * capability, 4 no failures but a required check was skipped (incomplete).
 *
 * Evidence is allowlisted, not dumped: only the four non-auth API bodies the
 * checks actually assert are persisted (redacted), plus status/method/path.
 * Raw `/api/auth/*` bodies, tokens, passwords and 2FA secrets never reach the
 * evidence file; a final scan refuses to write if any registered secret value
 * is present.
 *
 * Usage:
 *   node scripts/acceptance/browser_settings_acceptance.mjs \
 *     --out docs/acceptance/evidence/wa075_settings/signed-in-settings.json
 *
 * Optional flags:
 *   --no-screenshots          smaller evidence bundle
 *   --exercise-2fa            enable/reload/disable round trip when reachable
 *   --skip-account-password   read-only Account coverage (run is incomplete:
 *                             exit 4, never a silent pass)
 *   --timeout-ms <ms>         per-action wait (default 45000)
 *
 * Env (same contract as browser_core_surface, plus the identity pin):
 *   ATOM_FRONTEND_URL   default http://127.0.0.1:3001 (loopback only)
 *   ATOM_BACKEND_URL    default http://127.0.0.1:8105 (loopback only)
 *   ATOM_SCOPE_EMAIL    default admin@example.com
 *   ATOM_SCOPE_PASSWORD required; the scratch world's admin password
 *   ATOM_WA075_WORLD    required; the scratch world directory. The backend's
 *                       /health identity must report <WORLD>/atom.db before
 *                       any setting is changed.
 *   ATOM_PLAYWRIGHT_MODULE optional explicit Playwright ESM path
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import {
  collectErrors,
  loginToken,
  waitForFrontend,
} from "./lib/core_surface_session.mjs";
import {
  freshTotpStepDelayMs,
  normalizePolicy,
  policyMode,
  routingStatsFrom,
  samePolicy,
  toNumber,
  totpCode,
} from "./lib/settings_contract.mjs";
import {
  ownCurrentSession,
  revocableRows,
  selectDisposableSession,
} from "./lib/session_selection.mjs";

const FRONTEND = (process.env.ATOM_FRONTEND_URL || "http://127.0.0.1:3001").replace(/\/$/, "");
const BACKEND = (process.env.ATOM_BACKEND_URL || "http://127.0.0.1:8105").replace(/\/$/, "");
const EMAIL = process.env.ATOM_SCOPE_EMAIL || "admin@example.com";
const PASSWORD = process.env.ATOM_SCOPE_PASSWORD;
const ROLE = process.env.ATOM_SCOPE_ROLE || "admin";
const WORLD = (process.env.ATOM_WA075_WORLD || "").trim();
//: Optional existing browser binary. The installed Chrome is x64 here and
//: runs under Rosetta on arm64 (Chromium warns this is unsupported); the
//: environment's arm64 Playwright headless shell is used only when a run pins
//: it. Nothing is ever downloaded or installed.
const CHROME_EXECUTABLE = (process.env.ATOM_CHROME_EXECUTABLE || "").trim();
const PLAYWRIGHT_MODULE = process.env.ATOM_PLAYWRIGHT_MODULE
  || new URL("../../frontend-nextjs/node_modules/playwright/index.mjs", import.meta.url).href;

/* ------------------------------------------------------------------ */
/* Scratch-origin pinning and secret hygiene                          */
/* ------------------------------------------------------------------ */

//: Only these hostnames may ever serve the acceptance stack. A capture from a
//: non-loopback origin is not the scratch world, whatever the env says.
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);
//: Known long-lived dev/service ports. Accepting one would let a stale or live
//: stack masquerade as the scratch world.
const NON_SCRATCH_PORTS = new Set([3000, 3002, 8000, 8001, 8080]);

//: Values registered here must never appear in the persisted evidence. Tokens,
//: the scratch password and a 2FA secret are added when they are minted.
const SECRET_VALUES = new Set();
function registerSecret(value) {
  if (typeof value === "string" && value.length >= 4) SECRET_VALUES.add(value);
}
registerSecret(PASSWORD);

const SENSITIVE_KEY = /^(?:access_?token|refresh_?token|token|id_?token|secret|totp_?secret|password|passwd|current_?password|new_?password|confirm_?password|api_?key|authorization|cookie|set-cookie|backup_?codes?|recovery_?codes?|code|otp|credential|credentials)$/i;
const DROPPED_KEYS = new Set([
  "token", "access_token", "refresh_token", "secret", "totp_secret",
  "password", "current_password", "new_password", "confirm_password",
  "api_key", "authorization", "cookie", "set-cookie", "backup_codes",
  "recovery_codes", "code", "otp", "credential", "credentials",
  "setup_body_sample", "setup_secret", "response_body", "body_raw",
]);

function normalizeOrigin(label, raw) {
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new Error(`${label} URL is not absolute: ${raw}`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`${label} URL must be http(s): ${raw}`);
  }
  if (url.username || url.password) {
    throw new Error(`${label} URL embeds credentials; refusing to use it`);
  }
  if (!LOOPBACK_HOSTS.has(url.hostname)) {
    throw new Error(
      `${label} URL ${url.origin} is not loopback; WA-075 only ever runs `
      + "against the scratch 127.0.0.1 stack");
  }
  const port = Number(url.port || (url.protocol === "https:" ? 443 : 80));
  if (NON_SCRATCH_PORTS.has(port)) {
    throw new Error(
      `${label} URL ${url.origin} uses known non-scratch port ${port}; `
      + "point it at the isolated acceptance stack (e.g. 8105/3001)");
  }
  return { origin: url.origin, port, hostname: url.hostname };
}

const FRONTEND_ORIGIN_INFO = normalizeOrigin("frontend", FRONTEND);
const BACKEND_ORIGIN_INFO = normalizeOrigin("backend", BACKEND);
const FRONTEND_ORIGIN = FRONTEND_ORIGIN_INFO.origin;
const BACKEND_ORIGIN = BACKEND_ORIGIN_INFO.origin;
if (FRONTEND_ORIGIN === BACKEND_ORIGIN) {
  throw new Error("frontend and backend must be distinct scratch origins");
}

function redactJson(value, depth = 0) {
  if (depth > 12) return "[depth-limit]";
  if (Array.isArray(value)) return value.map((v) => redactJson(v, depth + 1));
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, val] of Object.entries(value)) {
      if (SENSITIVE_KEY.test(key) || DROPPED_KEYS.has(key.toLowerCase())) continue;
      out[key] = redactJson(val, depth + 1);
    }
    return out;
  }
  return value;
}

function sanitizeString(text) {
  let out = String(text);
  for (const secret of SECRET_VALUES) {
    if (secret && out.includes(secret)) out = out.split(secret).join("[redacted]");
  }
  return out.slice(0, 4000);
}

function sanitizeEvidence(value, depth = 0) {
  if (depth > 20) return "[depth-limit]";
  if (Array.isArray(value)) return value.map((v) => sanitizeEvidence(v, depth + 1));
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, val] of Object.entries(value)) {
      if (DROPPED_KEYS.has(key.toLowerCase()) || SENSITIVE_KEY.test(key)) continue;
      out[key] = sanitizeEvidence(val, depth + 1);
    }
    return out;
  }
  if (typeof value === "string") return sanitizeString(value);
  return value;
}

let chromium;
try {
  ({ chromium } = await import(PLAYWRIGHT_MODULE));
} catch (err) {
  console.error(
    `Playwright is not available at ${PLAYWRIGHT_MODULE}.\n`
    + "This harness reuses the workspace's installed frontend-nextjs/node_modules "
    + "and installs nothing; point ATOM_PLAYWRIGHT_MODULE at an existing "
    + `Playwright ESM entry if the frontend lives elsewhere.\n${String(err.message || err)}`);
  process.exit(2);
}

const argv = process.argv.slice(2);
function argValue(name, fallback = null) {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : fallback;
}
const OUT = argValue("--out");
const TIMEOUT = Number(argValue("--timeout-ms", "45000"));
const NO_SCREENSHOTS = argv.includes("--no-screenshots");
const EXERCISE_2FA = argv.includes("--exercise-2fa");
const SKIP_PASSWORD = argv.includes("--skip-account-password");
const RUN_ID = `wa075-${new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14)}-${crypto.randomBytes(3).toString("hex")}`;
//: Wait a little past the TOTP step boundary before spending the next code.
//: The backend burns one step per enable/disable/verify-action; the harness
//: waits the clock out rather than bypassing that guard.
const TOTP_STEP_MARGIN_MS = 250;
const DISPOSABLE_PROVIDER_NAME = `${RUN_ID} provider`;
// RFC 2606 reserved TLD: guaranteed non-resolvable, so a stray Discover/Test
// could never reach a real service. Discover and Test are never clicked.
const DISPOSABLE_PROVIDER_URL = "http://wa075-disposable.invalid/v1";

const checks = [];
const evidence = {};
const net = { entries: [], bodies: [], external: [] };

function record({ id, area, description, status, reason = null, data = {} }) {
  const entry = { id, area, description, status, reason, evidence: data };
  checks.push(entry);
  const suffix = reason ? ` :: ${reason}` : "";
  console.log(`[${status.toUpperCase()}] ${id} — ${description}${suffix}`);
  return entry;
}

async function runCheck({ id, area, description }, fn) {
  try {
    const outcome = await fn();
    if (!outcome || !outcome.status) throw new Error("check produced no outcome");
    return record({ id, area, description, ...outcome });
  } catch (err) {
    return record({
      id, area, description, status: "fail",
      reason: String((err && err.message) || err).slice(0, 500),
    });
  }
}

/* ------------------------------------------------------------------ */
/* HTTP / network helpers                                             */
/* ------------------------------------------------------------------ */

async function api(method, pathname, { token, body } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BACKEND}${pathname}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch { /* non-JSON */ }
  return { status: res.status, json, text: text.slice(0, 600) };
}

//: Only these non-auth endpoints may contribute a persisted response body.
//: `/api/auth/*` is deliberately absent: those bodies carry session tokens,
//: password-change acknowledgements and (on a reachable setup route) a 2FA
//: secret. Their method/path/status is enough for the checks.
const BODY_EVIDENCE_ALLOWLIST = new Set([
  "/api/chat/routing-stats",
  "/api/ai/provider-policy",
  "/api/ai/providers",
  "/api/local-models",
]);

function attachNetwork(page, label) {
  page.on("request", (req) => {
    const u = new URL(req.url());
    if (u.protocol !== "http:" && u.protocol !== "https:") return;
    if (u.origin !== FRONTEND_ORIGIN && u.origin !== BACKEND_ORIGIN) {
      if (net.external.length < 200) {
        net.external.push({
          label, origin: u.origin, host: u.host,
          path: u.pathname, method: req.method(),
          resource_type: req.resourceType(),
          frame_path: (() => { try { return new URL(req.frame().url()).pathname; } catch { return null; } })(),
          is_api: u.pathname.startsWith("/api/"),
        });
      }
    }
  });
  page.on("response", async (res) => {
    const u = new URL(res.url());
    if (!u.pathname.startsWith("/api/")) return;
    if (net.entries.length >= 600) return;
    const entry = {
      label, method: res.request().method(), origin: u.origin,
      path: u.pathname, status: res.status(),
    };
    net.entries.push(entry);
    if (BODY_EVIDENCE_ALLOWLIST.has(u.pathname)) {
      try {
        const body = await res.text();
        let parsed = null;
        try { parsed = JSON.parse(body); } catch { /* non-JSON */ }
        net.bodies.push({
          ...entry,
          // Non-JSON bodies are not evidence and are never persisted.
          body: parsed === null ? "[non-JSON body omitted]" : JSON.stringify(redactJson(parsed)),
        });
      } catch { /* body unavailable */ }
    }
  });
}

function responsesFor(pathname, method = null) {
  return net.entries.filter((e) => e.path === pathname && (!method || e.method === method));
}

/**
 * Read the most recent captured JSON body for a path. Bodies are appended in
 * arrival order, so callers that need "the payload this render used" pass
 * `since` = net.bodies.length before the triggering action.
 */
function lastCapturedJson(pathname, since = 0) {
  for (let i = net.bodies.length - 1; i >= since; i--) {
    if (net.bodies[i].path === pathname) {
      try { return { status: net.bodies[i].status, json: JSON.parse(net.bodies[i].body) }; }
      catch { return { status: net.bodies[i].status, json: null, raw: net.bodies[i].body }; }
    }
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Browser helpers                                                    */
/* ------------------------------------------------------------------ */

async function seedContext(context, token) {
  await context.addCookies([
    { name: "auth_token", value: token, url: FRONTEND, sameSite: "Lax" },
  ]);
  await context.addInitScript(({ t, e }) => {
    try {
      localStorage.setItem("auth_token", t);
      localStorage.setItem("token", t);
      localStorage.setItem("user_email", e);
    } catch { /* ignore */ }
  }, { t: token, e: EMAIL });
  return context;
}

async function newSeededPage(browser, token) {
  const context = await seedContext(
    await browser.newContext({ viewport: { width: 1440, height: 1000 } }), token);
  const page = await context.newPage();
  attachNetwork(page, "primary");
  return { context, page };
}

async function tryLogin(password) {
  const res = await api("POST", "/api/auth/login", {
    body: { username: EMAIL, password },
  });
  const token = res.json ? (res.json.access_token || res.json.token) : null;
  registerSecret(token);
  return {
    ok: res.status === 200 && Boolean(token),
    status: res.status,
    token,
  };
}

async function gotoRoute(page, route, { heading = null, settleMs = 600 } = {}) {
  let response = null;
  let lastErr = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      response = await page.goto(`${FRONTEND}${route}`, {
        waitUntil: "domcontentloaded", timeout: TIMEOUT,
      });
      lastErr = null;
      break;
    } catch (err) {
      lastErr = err;
      await waitForFrontend(FRONTEND);
      await page.waitForTimeout(1500);
    }
  }
  if (lastErr && !response) throw lastErr;
  if (heading) {
    await page.getByRole("heading", { name: heading, exact: false }).first()
      .waitFor({ state: "visible", timeout: 20000 });
  }
  await page.waitForLoadState("networkidle", { timeout: 12000 }).catch(() => {});
  await page.waitForTimeout(settleMs);
  await dismissOnboardingDialog(page, route);
  return {
    status: response ? response.status() : null,
    finalPath: new URL(page.url()).pathname,
  };
}

/**
 * A fresh scratch admin has not completed onboarding, so the global
 * OnboardingWizard mounts a modal about 3 s after the first authenticated
 * page and covers every control. An operator dismisses it; the harness does
 * the same and records which control worked. This is a UI state of the
 * product under test, not something to hide with localStorage.
 *
 * The modal is found by its overlay text rather than `getByRole("dialog")`
 * alone: the Radix content mounts/unmounts while its parent overlay stays.
 */
async function dismissOnboardingDialog(page, label) {
  const flagSet = () => page.evaluate(() => {
    try { return Boolean(sessionStorage.getItem("atom.onboarding.dismissed")); }
    catch { return null; }
  }).catch(() => null);
  if (await flagSet()) {
    return { appeared: false, dismissed: false, already_dismissed: true };
  }

  const overlay = page.locator("div.fixed.inset-0.z-50")
    .filter({ hasText: "Welcome to Atom" }).first();
  await overlay.waitFor({ state: "visible", timeout: 8000 }).catch(() => {});
  if (!(await overlay.isVisible().catch(() => false))) {
    return { appeared: false, dismissed: false };
  }

  const attempts = [];
  let method = null;
  for (const attempt of ["skip_button", "escape", "close_icon", "overlay_click"]) {
    if (attempt === "skip_button") {
      const skip = overlay.getByRole("button")
        .filter({ hasText: /skip|later|not now|dismiss|close/i }).first();
      if (!(await skip.count().catch(() => 0))) { attempts.push("skip_button:absent"); continue; }
      await skip.click({ force: true }).catch(() => {});
      method = "skip_button";
    } else if (attempt === "escape") {
      await page.keyboard.press("Escape").catch(() => {});
      method = "escape";
    } else if (attempt === "close_icon") {
      const buttons = overlay.locator("button");
      const count = await buttons.count().catch(() => 0);
      let clicked = false;
      for (let i = 0; i < count; i++) {
        const button = buttons.nth(i);
        const text = (await button.innerText().catch(() => "")).trim();
        if (!text) {
          await button.click({ force: true }).catch(() => {});
          clicked = true;
          break;
        }
      }
      if (!clicked) { attempts.push("close_icon:absent"); continue; }
      method = "close_icon";
    } else {
      const box = await overlay.boundingBox().catch(() => null);
      if (!box) { attempts.push("overlay_click:no_box"); continue; }
      await page.mouse.click(box.x + 4, box.y + 4).catch(() => {});
      method = "overlay_click";
    }
    await page.waitForTimeout(900);
    if (await flagSet()) break;
    if (!(await overlay.isVisible().catch(() => false))) break;
    attempts.push(`${attempt}:still_visible`);
  }

  const gone = !(await overlay.isVisible().catch(() => false));
  const flag = await flagSet();
  const dismissed = Boolean(gone || flag);
  const record = {
    appeared: true, dismissed, method, route: label,
    attempts, session_flag_set: Boolean(flag),
  };
  evidence.onboarding_dismissals = evidence.onboarding_dismissals || [];
  evidence.onboarding_dismissals.push(record);
  if (!dismissed) {
    throw new Error(
      `the onboarding dialog ("Welcome to Atom") could not be dismissed on ${label}; `
      + "its overlay blocks every settings control");
  }
  return record;
}

async function bodyText(page) {
  return (await page.locator("body").innerText().catch(() => "")).slice(0, 4000);
}

async function shot(page, name) {
  if (NO_SCREENSHOTS || !OUT) return;
  const dir = path.join(path.dirname(OUT), "screenshots");
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true })
    .catch(() => {});
}

async function clickAndWait(page, matcher, action) {
  // Own the rejection: if the click itself throws (or the page re-renders),
  // an abandoned waitForResponse would surface later as an unhandled
  // rejection and kill the whole run instead of failing one check.
  const wait = page.waitForResponse(matcher, { timeout: TIMEOUT })
    .catch((err) => ({ __wait_error: err }));
  await action();
  const res = await wait;
  if (!res || res.__wait_error) {
    throw new Error(
      `no matching response within ${TIMEOUT}ms: ${res && res.__wait_error
        ? String(res.__wait_error.message || res.__wait_error).split("\n")[0]
        : "none"}`);
  }
  let json = null;
  try { json = await res.json(); } catch { /* non-JSON */ }
  return {
    status: res.status(),
    method: res.request().method(),
    url: res.url(),
    json,
  };
}

/** Numeric/text value of a Routing dashboard metric card. */
async function metricText(page, label) {
  const cards = page.locator("div").filter({ hasText: label })
    .filter({ has: page.locator(".text-2xl") });
  const count = await cards.count();
  if (count === 0) throw new Error(`routing metric card not found: ${label}`);
  const card = cards.nth(count - 1);
  const value = (await card.locator(".text-2xl").first().innerText()).trim();
  if (!value) throw new Error(`routing metric card is empty: ${label}`);
  return value;
}

/* ------------------------------------------------------------------ */
/* 0. Scratch identity — verified BEFORE any mutation                 */
/* ------------------------------------------------------------------ */

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function canonicalPath(p) {
  const resolved = path.resolve(p);
  try { return fs.realpathSync(resolved); } catch { /* not present yet */ }
  try { return path.join(fs.realpathSync(path.dirname(resolved)), path.basename(resolved)); }
  catch { return resolved; }
}

/**
 * The names must match the scratch stack, not merely answer 200. A stale
 * server, a live dev stack or a second checkout on the same machine would
 * otherwise accept every later write.
 */
async function verifyScratchIdentity() {
  const problems = [];
  const pinned = {
    frontend_origin: FRONTEND_ORIGIN,
    backend_origin: BACKEND_ORIGIN,
    frontend_port: FRONTEND_ORIGIN_INFO.port,
    backend_port: BACKEND_ORIGIN_INFO.port,
    loopback_only: true,
    non_scratch_ports_refused: [...NON_SCRATCH_PORTS],
  };
  if (!WORLD) {
    problems.push(
      "ATOM_WA075_WORLD is not set; the driver refuses to change any setting "
      + "without knowing which scratch world the backend must report");
  } else if (!path.isAbsolute(WORLD)) {
    problems.push(`ATOM_WA075_WORLD must be absolute, got ${WORLD}`);
  }
  const expectedDatabase = WORLD ? path.join(WORLD, "atom.db") : null;
  const expectedBackendDir = path.join(REPO_ROOT, "backend");

  let health = null;
  try {
    const res = await fetch(`${BACKEND}/health`, { signal: AbortSignal.timeout(20000) });
    const text = await res.text();
    try { health = { http: res.status, json: JSON.parse(text) }; }
    catch { health = { http: res.status, json: null, non_json: text.slice(0, 120) }; }
  } catch (err) {
    problems.push(`GET ${BACKEND}/health failed: ${String(err.message || err).slice(0, 200)}`);
  }

  const identity = health && health.json ? (health.json.identity || null) : null;
  if (health && health.http !== 200) {
    problems.push(`GET /health -> ${health.http}; the scratch backend is not healthy`);
  }
  if (!identity) {
    problems.push("GET /health returned no identity block; cannot attribute the backend");
  } else {
    const reportedDb = identity.database ? canonicalPath(String(identity.database)) : null;
    const dbMatches = Boolean(expectedDatabase)
      && reportedDb === canonicalPath(expectedDatabase);
    const portMatches = String(identity.port) === String(BACKEND_ORIGIN_INFO.port);
    const cwdMatches = identity.cwd
      ? canonicalPath(String(identity.cwd)) === canonicalPath(expectedBackendDir)
      : false;
    if (!dbMatches) {
      problems.push(
        `backend database ${identity.database || "<none>"} is not the scratch world `
        + `${expectedDatabase || "<unset ATOM_WA075_WORLD>"}`);
    }
    if (!portMatches) {
      problems.push(`backend identity port ${identity.port} != pinned ${BACKEND_ORIGIN_INFO.port}`);
    }
    if (!cwdMatches) {
      problems.push(
        `backend cwd ${identity.cwd || "<none>"} is not ${expectedBackendDir}; `
        + "a second checkout or a stale process is answering");
    }
    pinned.backend_identity = {
      pid: identity.pid ?? null,
      port: identity.port ?? null,
      cwd: identity.cwd ?? null,
      database: identity.database ?? null,
      source_id: identity.source_id ?? null,
      instance_id: identity.instance_id ?? null,
      database_matches_world: dbMatches,
      port_matches: portMatches,
      cwd_matches: cwdMatches,
    };
  }

  let frontend = null;
  try {
    const res = await fetch(`${FRONTEND}/api/health`, { signal: AbortSignal.timeout(20000) });
    const text = await res.text();
    try { frontend = { http: res.status, json: JSON.parse(text) }; }
    catch { frontend = { http: res.status, json: null }; }
  } catch (err) {
    problems.push(`GET ${FRONTEND}/api/health failed: ${String(err.message || err).slice(0, 200)}`);
  }
  const serviceOk = Boolean(frontend && frontend.json
    && frontend.json.service === "atom-frontend"
    && ["healthy", "ok"].includes(frontend.json.status));
  if (!serviceOk) {
    problems.push(
      `GET /api/health did not identify an atom-frontend scratch server: `
      + `${frontend ? JSON.stringify(frontend.json || frontend.http) : "unreachable"}`);
  }
  pinned.frontend_identity = {
    http: frontend ? frontend.http : null,
    service: frontend && frontend.json ? frontend.json.service ?? null : null,
    status: frontend && frontend.json ? frontend.json.status ?? null : null,
    service_matches: serviceOk,
  };

  return { ok: problems.length === 0, problems, evidence: pinned };
}

/* ------------------------------------------------------------------ */
/* 1. Signed-in session                                               */
/* ------------------------------------------------------------------ */

async function checkSignedIn(token) {
  return runCheck({
    id: "session.signed_in_token",
    area: "session",
    description: "the scratch admin signs in through the real backend login route",
  }, async () => {
    const me = await api("GET", "/api/auth/me", { token });
    if (me.status !== 200 || !me.json) {
      return { status: "fail", reason: `GET /api/auth/me -> ${me.status}`, data: { status: me.status } };
    }
    const meEmail = me.json.email || (me.json.user && me.json.user.email) || null;
    if (meEmail !== EMAIL) {
      return {
        status: "fail",
        reason: `authenticated as ${meEmail} but expected ${EMAIL}`,
        data: { email: meEmail },
      };
    }
    return {
      status: "pass",
      data: {
        email: meEmail,
        role: me.json.role || (me.json.user && me.json.user.role) || null,
        expected_role: ROLE,
        token_minted_via: "POST /api/auth/login",
        password_recorded: false,
      },
    };
  });
}

/* ------------------------------------------------------------------ */
/* 2. AI — provider routing policy (reversible control)               */
/* ------------------------------------------------------------------ */

async function policyViaApi(token) {
  const res = await api("GET", "/api/ai/provider-policy", { token });
  return res;
}

/**
 * A body the public PUT accepts for a restored policy. Raw `unset` is not a
 * writable mode (`validate_provider_policy` accepts automatic|selected); the
 * equivalent `automatic` body is used and the difference is recorded.
 */
function policyRestoreBody(policy) {
  return {
    mode: policyMode(policy),
    allowed_providers: [...(policy.allowed_providers || [])],
    preferred: policy.preferred || null,
  };
}

async function readUiPolicy(page) {
  const automaticChecked = await page
    .locator('label.policy-option', { hasText: "Automatic among enabled providers" })
    .locator("input").isChecked().catch(() => false);
  const selectedChecked = await page
    .locator('label.policy-option', { hasText: "Only selected providers" })
    .locator("input").isChecked().catch(() => false);
  const preferredProvider = await page.locator("#policy-preferred-provider")
    .inputValue().catch(() => "");
  const preferredModel = await page.locator("#policy-preferred-model")
    .inputValue().catch(() => "");
  const allowed = [];
  const boxes = page.locator("label.policy-provider-option");
  const count = await boxes.count();
  for (let i = 0; i < count; i++) {
    const box = boxes.nth(i);
    if (await box.locator("input").isChecked().catch(() => false)) {
      const label = (await box.innerText()).split("\n")[0].trim();
      allowed.push(providerIdForLabel(label));
    }
  }
  return {
    mode: selectedChecked ? "selected" : automaticChecked ? "automatic" : null,
    allowed_provider_ids: allowed,
    preferred_provider: preferredProvider || null,
    preferred_model: preferredModel || null,
  };
}

/**
 * Map the provider display name the page renders back to the backend id,
 * using the `/api/ai/providers` payload the page itself received. Falls back
 * to a normalized slug so an unmapped label is visible in evidence instead of
 * silently matching nothing.
 */
function providerIdForLabel(label) {
  const captured = lastCapturedJson("/api/ai/providers");
  const payload = captured && captured.json
    ? (captured.json.data?.providers ? captured.json.data : captured.json)
    : null;
  const rows = (payload && payload.providers) || [];
  const base = String(label).replace(/\s*\(.*\)\s*$/, "").trim().toLowerCase();
  for (const row of rows) {
    const info = row.provider || row;
    const name = String(info.name || "").trim().toLowerCase();
    if (name && name === base && info.id) return info.id;
  }
  if (base === "ollama") return "ollama";
  return base.replace(/[^a-z0-9]+/g, "_");
}

async function setUiPolicy(page, policy) {
  if (policy.mode === "selected") {
    await page.locator('label.policy-option', { hasText: "Only selected providers" })
      .locator("input").check();
    if ((policy.allowed_providers || []).length > 0) {
      // The provider grid is conditionally rendered after the radio flips.
      await page.locator("label.policy-provider-option").first()
        .waitFor({ state: "visible", timeout: 8000 }).catch(() => {});
    }
  } else {
    await page.locator('label.policy-option', { hasText: "Automatic among enabled providers" })
      .locator("input").check();
  }
  // Checkboxes only exist for providers the page can represent (configured
  // providers + ollama). Anything else cannot be expressed through the UI.
  const boxes = page.locator("label.policy-provider-option");
  const total = await boxes.count();
  const wanted = new Set(policy.allowed_providers || []);
  const seen = new Set();
  for (let i = 0; i < total; i++) {
    const box = boxes.nth(i);
    const label = (await box.innerText()).split("\n")[0].trim();
    const providerId = providerIdForLabel(label);
    seen.add(providerId);
    const shouldCheck = wanted.has(providerId);
    const checked = await box.locator("input").isChecked().catch(() => false);
    if (shouldCheck !== checked) await box.locator("input").setChecked(shouldCheck, { force: true });
  }
  const preferred = policy.preferred;
  await page.locator("#policy-preferred-provider")
    .selectOption(preferred ? preferred.provider : "").catch(() => {});
  if (preferred) {
    await page.locator("#policy-preferred-model").fill(preferred.model || "");
  }
  return { rendered_provider_ids: [...seen] };
}

async function aiChecks({ page, token }) {
  const baselineRes = await policyViaApi(token);
  evidence.ai = {
    baseline_http: baselineRes.status,
    baseline: baselineRes.json ? normalizePolicy(baselineRes.json.data?.policy || baselineRes.json.policy) : null,
  };
  if (baselineRes.status !== 200 || !evidence.ai.baseline) {
    return runCheck({
      id: "ai.page_loads", area: "ai",
      description: "AI Provider Settings loads the installation policy from the backend",
    }, async () => ({
      status: "fail",
      reason: `GET /api/ai/provider-policy -> ${baselineRes.status}`,
      data: { http: baselineRes.status },
    }));
  }
  const baseline = evidence.ai.baseline;
  const managedByEnv = Boolean(
    (baselineRes.json.data?.policy || baselineRes.json.policy || {}).managed_by_env);

  await runCheck({
    id: "ai.page_loads", area: "ai",
    description: "AI Provider Settings renders and requests the real provider status + policy",
  }, async () => {
    const since = net.bodies.length;
    const providerBefore = responsesFor("/api/ai/providers").length;
    const policyBefore = responsesFor("/api/ai/provider-policy").length;
    const nav = await gotoRoute(page, "/settings/ai", { heading: "AI Provider Settings" });
    await page.getByText("Where Atom may send requests").first()
      .waitFor({ state: "visible", timeout: 15000 }).catch(() => {});
    const text = await bodyText(page);
    const statusReq = responsesFor("/api/ai/providers").length - providerBefore;
    const policyReq = responsesFor("/api/ai/provider-policy").length - policyBefore;
    await shot(page, "02_ai");
    const blocked = /Failed to load provider policy|Failed to load provider status/i.test(text);
    return {
      status: nav.status === 200 && statusReq > 0 && policyReq > 0 && !blocked ? "pass" : "fail",
      reason: blocked ? "page reported a provider/policy load failure" : null,
      data: {
        http: nav.status, final_path: nav.finalPath,
        provider_status_requests: statusReq, policy_requests: policyReq,
        policy_rendered: lastCapturedJson("/api/ai/provider-policy", since) !== null,
        text_sample: text.slice(0, 300),
      },
    };
  });

  await runCheck({
    id: "ai.policy_loads", area: "ai",
    description: "the saved policy shown in the UI is the policy the backend returned",
  }, async () => {
    const ui = await readUiPolicy(page);
    const apiPolicy = (await policyViaApi(token)).json;
    const effective = apiPolicy ? normalizePolicy(apiPolicy.data?.policy || apiPolicy.policy) : null;
    const modeMatches = ui.mode === policyMode(effective);
    const allowedMatches = effective.effective_mode !== "selected"
      || JSON.stringify([...ui.allowed_provider_ids].sort())
        === JSON.stringify([...effective.allowed_providers].sort());
    const managedBadge = (await bodyText(page)).includes("Managed by this installation");
    return {
      status: modeMatches && allowedMatches && managedByEnv === managedBadge ? "pass" : "fail",
      reason: !modeMatches ? `UI mode ${ui.mode} != API mode ${policyMode(effective)} `
        + `(raw ${effective.mode})`
        : (!allowedMatches ? "UI allowed set != API allowed set" : null),
      data: {
        ui, effective, effective_mode: policyMode(effective),
        managed_by_env: managedByEnv, managed_badge_shown: managedBadge,
      },
    };
  });

  if (managedByEnv) {
    await runCheck({
      id: "ai.policy_saved", area: "ai",
      description: "a reversible provider-policy preference can be saved and reloaded",
    }, async () => ({
      status: "missing",
      reason: "ATOM_LLM_PROVIDER_POLICY is set for this installation; the UI is "
        + "read-only and a save is rejected (PUT 409). No policy was changed.",
      data: { managed_by_env: true, ui_controls_disabled: true },
    }));
    record({
      id: "ai.policy_restored", area: "ai", status: "skipped",
      description: "restore the baseline policy (nothing was changed)",
      reason: "no save was attempted", data: { baseline },
    });
    return;
  }

  // The policy tab can only represent providers it renders (configured keys +
  // ollama). A fresh scratch world has neither, so the representable change is
  // the mode itself. `unset` (the legacy default) behaves as `automatic`, so
  // the reversible change is still the mode. "Only selected providers" with an
  // empty set is a real, reversible policy (it makes routes unavailable), and
  // the baseline is restored immediately afterwards.
  const target = policyMode(baseline) === "selected"
    ? { mode: "automatic", allowed_providers: [], preferred: null }
    : { mode: "selected", allowed_providers: [], preferred: null };

  await runCheck({
    id: "ai.policy_saved", area: "ai",
    description: "save a reversible provider-policy preference through the page",
  }, async () => {
    const uiControls = await setUiPolicy(page, target);
    const since = net.bodies.length;
    const res = await clickAndWait(page,
      (r) => r.url().includes("/api/ai/provider-policy") && r.request().method() === "PUT",
      () => page.getByRole("button", { name: "Save Routing Policy" }).click());
    const saved = res.json ? (res.json.data?.policy || res.json.policy) : null;
    const text = await bodyText(page);
    const toast = /Routing policy saved/i.test(text);
    const ok = res.status === 200 && samePolicy(saved, target);
    return {
      status: ok ? "pass" : "fail",
      reason: ok ? null : `PUT -> ${res.status}; effective=${JSON.stringify(normalizePolicy(saved))}`,
      data: {
        target, http: res.status, effective: normalizePolicy(saved),
        revision_before: baselineRes.json.data?.policy?.revision
          || baselineRes.json.policy?.revision || null,
        revision_after: saved ? saved.revision : null,
        toast_shown: toast, ui_controls: uiControls,
        response_bodies_since_save: net.bodies.length - since,
      },
    };
  });

  await runCheck({
    id: "ai.policy_persisted_reload", area: "ai",
    description: "the saved preference survives a full page reload and is what the backend serves",
  }, async () => {
    const nav = await gotoRoute(page, "/settings/ai", { heading: "AI Provider Settings" });
    const ui = await readUiPolicy(page);
    const apiPolicy = (await policyViaApi(token)).json;
    const effective = apiPolicy ? normalizePolicy(apiPolicy.data?.policy || apiPolicy.policy) : null;
    const persisted = samePolicy(effective, target);
    const uiMode = ui.mode === policyMode(target);
    const uiAllowed = policyMode(target) !== "selected"
      || JSON.stringify([...ui.allowed_provider_ids].sort())
        === JSON.stringify([...target.allowed_providers].sort());
    return {
      status: nav.status === 200 && persisted && uiMode && uiAllowed ? "pass" : "fail",
      reason: !persisted ? "backend policy is not the saved target after reload"
        : (!uiMode ? `UI mode ${ui.mode} != saved ${target.mode}`
          : (!uiAllowed ? "UI allowed set != saved target" : null)),
      data: { http: nav.status, ui, effective, target },
    };
  });

  await runCheck({
    id: "ai.policy_restored", area: "ai",
    description: "the baseline policy is restored and verified after another reload",
  }, async () => {
    // The UI can only represent providers it renders. If the baseline names
    // an unrendered provider, restore through the same public PUT the page
    // uses and say so, rather than silently leaving a changed policy.
    const uiRestore = await setUiPolicy(page, baseline);
    let res = await clickAndWait(page,
      (r) => r.url().includes("/api/ai/provider-policy") && r.request().method() === "PUT",
      () => page.getByRole("button", { name: "Save Routing Policy" }).click()).catch(() => null);
    let method = "ui";
    let effectiveAfter = res && res.json ? (res.json.data?.policy || res.json.policy) : null;
    if (!res || res.status !== 200 || !samePolicy(effectiveAfter, baseline)) {
      method = "public_put_endpoint_cleanup";
      const put = await api("PUT", "/api/ai/provider-policy", {
        token, body: policyRestoreBody(baseline),
      });
      effectiveAfter = put.json ? (put.json.data?.policy || put.json.policy) : null;
      res = { status: put.status, json: put.json };
    }
    const nav = await gotoRoute(page, "/settings/ai", { heading: "AI Provider Settings" });
    const ui = await readUiPolicy(page);
    const apiPolicy = (await policyViaApi(token)).json;
    const effective = apiPolicy ? normalizePolicy(apiPolicy.data?.policy || apiPolicy.policy) : null;
    const behaviorEquivalent = samePolicy(effective, baseline);
    const ok = behaviorEquivalent && ui.mode === policyMode(baseline);
    const exactRawMode = Boolean(effective && effective.mode === baseline.mode);
    return {
      status: ok ? "pass" : "fail",
      reason: ok ? null : `restore not effective: ${JSON.stringify(effective)}`,
      data: {
        method, http: res ? res.status : null, effective,
        ui, baseline, rendered: uiRestore,
        baseline_raw_mode: baseline.mode,
        restored_raw_mode: effective ? effective.mode : null,
        behavior_equivalent: behaviorEquivalent,
        exact_raw_mode_restored: exactRawMode,
        ui_restore_possible: method === "ui",
        note: [
          method === "ui" ? null
            : "baseline names a provider the tab cannot render; restored through the same public PUT the page uses",
          baseline.mode === "unset" && exactRawMode ? null
            : (baseline.mode === "unset"
              ? "baseline was the legacy `unset` default; the UI/API can only write `automatic`, "
                + "which allows the same providers and is verified here as behavior-equivalent"
              : null),
        ].filter(Boolean).join("; ") || null,
      },
    };
  });

  // Safety net: whatever the checks reported, the installation policy is
  // behaviorally the baseline when this function returns. A scratch world is
  // disposable, but a changed policy would silently invalidate every later run.
  const finalPolicy = await policyViaApi(token);
  const finalEffective = finalPolicy.json
    ? (finalPolicy.json.data?.policy || finalPolicy.json.policy) : null;
  if (!samePolicy(finalEffective, baseline)) {
    const put = await api("PUT", "/api/ai/provider-policy", {
      token, body: policyRestoreBody(baseline),
    });
    evidence.ai_cleanup = {
      restored: put.status === 200, http: put.status,
      baseline_mode: baseline.mode,
      reason: "policy differed from the captured baseline after the checks",
    };
  } else {
    evidence.ai_cleanup = {
      restored: true, http: finalPolicy.status,
      baseline_mode: baseline.mode,
      exact_raw_mode: Boolean(finalEffective && finalEffective.mode === baseline.mode),
    };
  }
}

/* ------------------------------------------------------------------ */
/* 3. Routing — real metrics load + refresh                           */
/* ------------------------------------------------------------------ */

async function routingChecks({ page }) {
  let firstPayload = null;
  await runCheck({
    id: "routing.metrics_loaded_from_backend", area: "routing",
    description: "Routing loads its numbers from /api/chat/routing-stats (no baked-in data)",
  }, async () => {
    const wait = page.waitForResponse(
      (r) => r.url().includes("/api/chat/routing-stats") && r.request().method() === "GET",
      { timeout: TIMEOUT });
    const nav = await gotoRoute(page, "/settings/routing", { heading: "Routing & Telemetry" });
    const res = await wait;
    let json = null;
    try { json = await res.json(); } catch { /* handled below */ }
    firstPayload = routingStatsFrom(json);
    const shapeOk = Boolean(json)
      && typeof json.enabled === "boolean" && typeof json.stats === "object";
    const denied = res.status() === 403;
    return {
      status: res.status() === 200 && shapeOk ? "pass"
        : (denied && ROLE !== "admin" ? "skipped" : "fail"),
      reason: res.status() === 200 ? null
        : denied && ROLE !== "admin"
          ? "routing telemetry is workspace_admin+ by design; this run is not admin"
          : `routing-stats -> ${res.status()}`,
      data: {
        http: res.status(), origin: new URL(res.url()).origin,
        http_via: new URL(res.url()).origin === FRONTEND_ORIGIN ? "next_proxy" : "backend_cors",
        payload: firstPayload, final_path: nav.finalPath,
      },
    };
  });

  await runCheck({
    id: "routing.page_loads", area: "routing",
    description: "the Routing dashboard renders its four metric cards",
  }, async () => {
    const text = await bodyText(page);
    const labels = ["Feedback Samples", "Models Tracked", "ML Predictor Status", "EMA Telemetry"];
    const missing = labels.filter((l) => !text.includes(l));
    const denied = /Supervisor access required|Admin role required/i.test(text);
    return {
      status: missing.length === 0 && !denied ? "pass"
        : (denied && ROLE !== "admin" ? "skipped" : "fail"),
      reason: denied
        ? (ROLE !== "admin" ? "role band denied the dashboard by design" : "admin run was denied")
        : (missing.length ? `missing cards: ${missing}` : null),
      data: { labels_found: labels.length - missing.length, denied },
    };
  });

  await runCheck({
    id: "routing.rendered_matches_payload", area: "routing",
    description: "every rendered metric equals the payload the browser actually received",
  }, async () => {
    if (!firstPayload) throw new Error("no routing payload was captured");
    const renderedSamples = toNumber(await metricText(page, "Feedback Samples"));
    const renderedModels = toNumber(await metricText(page, "Models Tracked"));
    const renderedPredictor = await metricText(page, "ML Predictor Status");
    const renderedEma = await metricText(page, "EMA Telemetry");
    const expectedModels = Object.keys(firstPayload.model_success_rates).length
      || Object.keys(firstPayload.ema_scores).length;
    const expectedPredictor = firstPayload.enabled ? "Active" : "Off";
    const expectedEma = firstPayload.ema_enabled ? "Blended"
      : (firstPayload.enabled ? "Collected" : "Off");
    const ok = renderedSamples === firstPayload.feedback_samples
      && renderedModels === expectedModels
      && renderedPredictor === expectedPredictor
      && renderedEma === expectedEma;
    return {
      status: ok ? "pass" : "fail",
      reason: ok ? null : "rendered numbers disagree with the received payload",
      data: {
        rendered: {
          feedback_samples: renderedSamples, models_tracked: renderedModels,
          predictor: renderedPredictor, ema: renderedEma,
        },
        expected: {
          feedback_samples: firstPayload.feedback_samples, models_tracked: expectedModels,
          predictor: expectedPredictor, ema: expectedEma,
        },
        payload: firstPayload,
      },
    };
  });

  await runCheck({
    id: "routing.refresh_refetches", area: "routing",
    description: "Refresh issues a second real request and the render follows the new payload",
  }, async () => {
    const before = responsesFor("/api/chat/routing-stats", "GET").length;
    const wait = page.waitForResponse(
      (r) => r.url().includes("/api/chat/routing-stats") && r.request().method() === "GET",
      { timeout: TIMEOUT });
    await page.getByRole("button", { name: "Refresh" }).click();
    const res = await wait;
    let json = null;
    try { json = await res.json(); } catch { /* handled below */ }
    const second = routingStatsFrom(json);
    const renderedSamples = toNumber(await metricText(page, "Feedback Samples"));
    const renderedModels = toNumber(await metricText(page, "Models Tracked"));
    const expectedModels = Object.keys(second.model_success_rates).length
      || Object.keys(second.ema_scores).length;
    const after = responsesFor("/api/chat/routing-stats", "GET").length;
    const ok = res.status() === 200 && after > before
      && renderedSamples === second.feedback_samples && renderedModels === expectedModels;
    return {
      status: ok ? "pass" : "fail",
      reason: ok ? null : "refresh did not refetch or render the new payload",
      data: { http: res.status(), requests_before: before, requests_after: after, payload: second },
    };
  });

  await runCheck({
    id: "routing.honest_telemetry_state", area: "routing",
    description: "the 'Learning Router is off' banner agrees with the real telemetry flags",
  }, async () => {
    if (!firstPayload) throw new Error("no routing payload was captured");
    const text = await bodyText(page);
    const banner = /Learning Router is off/.test(text);
    const shouldBanner = !firstPayload.enabled && !firstPayload.ema_enabled;
    return {
      status: banner === shouldBanner ? "pass" : "fail",
      reason: banner === shouldBanner ? null
        : `banner=${banner} but enabled=${firstPayload.enabled} ema_enabled=${firstPayload.ema_enabled}`,
      data: {
        banner_shown: banner, expected_banner: shouldBanner,
        learning_router_enabled: firstPayload.enabled,
        ema_enabled: firstPayload.ema_enabled,
        feedback_samples: firstPayload.feedback_samples,
        telemetry_empty: firstPayload.feedback_samples === 0
          && Object.keys(firstPayload.model_success_rates).length === 0,
        stats_error: firstPayload.stats_error,
        note: "empty telemetry is reported as empty; the harness never seeds or invents samples",
      },
    };
  });
}

/* ------------------------------------------------------------------ */
/* 4. Local models — disposable register / reload / delete            */
/* ------------------------------------------------------------------ */

async function localModelList(token) {
  const res = await api("GET", "/api/local-models", { token });
  return { status: res.status, list: Array.isArray(res.json) ? res.json : null };
}

async function localModelsChecks({ page, token }) {
  const baseline = await localModelList(token);
  if (baseline.status !== 200 || !baseline.list) {
    return runCheck({
      id: "local_models.page_loads", area: "local_models",
      description: "Local Models loads the registered provider list",
    }, async () => ({
      status: "fail",
      reason: `GET /api/local-models -> ${baseline.status}`,
      data: { http: baseline.status },
    }));
  }
  const baselineIds = baseline.list.map((p) => p.id).sort();
  let createdId = null;

  try {
    await runCheck({
      id: "local_models.page_loads", area: "local_models",
      description: "Local Models renders the same provider set the backend serves",
    }, async () => {
      const nav = await gotoRoute(page, "/settings/local-models", { heading: "Local Models" });
      const text = await bodyText(page);
      const missing = baseline.list
        .map((p) => p.name)
        .filter((name) => !text.includes(name));
      const emptyState = /No local providers registered yet/.test(text);
      const ok = nav.status === 200 && missing.length === 0
        && (baseline.list.length === 0 ? emptyState : true);
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null : (missing.length ? `providers missing from UI: ${missing}` : "empty state contradicts backend list"),
        data: {
          http: nav.status, baseline_count: baseline.list.length,
          missing_from_ui: missing, empty_state_shown: emptyState,
        },
      };
    });

    await runCheck({
      id: "local_models.register_saved", area: "local_models",
      description: "a disposable provider is registered through the Add Provider form",
    }, async () => {
      await page.getByRole("button", { name: "Add Provider" }).click();
      await page.getByPlaceholder("Name (e.g. 'My Ollama')").fill(DISPOSABLE_PROVIDER_NAME);
      await page.getByPlaceholder("Base URL (e.g. http://localhost:11434/v1)")
        .fill(DISPOSABLE_PROVIDER_URL);
      const res = await clickAndWait(page,
        (r) => r.url().includes("/api/local-models") && r.request().method() === "POST",
        () => page.getByRole("button", { name: "Register" }).click());
      createdId = res.json ? res.json.id : null;
      await page.getByText(DISPOSABLE_PROVIDER_NAME, { exact: true })
        .first().waitFor({ state: "visible", timeout: 20000 }).catch(() => {});
      const visible = await page.getByText(DISPOSABLE_PROVIDER_NAME, { exact: true }).count();
      const after = await localModelList(token);
      const created = after.list ? after.list.find((p) => p.name === DISPOSABLE_PROVIDER_NAME) : null;
      const ok = (res.status === 200 || res.status === 201)
        && Boolean(res.json && res.json.registered === true)
        && visible >= 1 && Boolean(created)
        && created.base_url === DISPOSABLE_PROVIDER_URL.replace(/\/$/, "")
        && created.provider_type === "ollama";
      if (!createdId && created) createdId = created.id;
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null : `POST -> ${res.status}; visible=${visible}; listed=${Boolean(created)}`,
        data: {
          http: res.status, response_id: res.json ? res.json.id : null,
          provider: created ? {
            id: created.id, name: created.name, provider_type: created.provider_type,
            base_url: created.base_url,
          } : null,
          ui_visible: visible, baseline_count: baseline.list.length,
          after_count: after.list ? after.list.length : null,
        },
      };
    });

    await runCheck({
      id: "local_models.persisted_after_reload", area: "local_models",
      description: "the disposable provider survives a full page reload and is still served",
    }, async () => {
      const nav = await gotoRoute(page, "/settings/local-models", { heading: "Local Models" });
      const visible = await page.getByText(DISPOSABLE_PROVIDER_NAME, { exact: true }).count();
      const after = await localModelList(token);
      const rows = after.list
        ? after.list.filter((p) => p.name === DISPOSABLE_PROVIDER_NAME) : [];
      const ok = nav.status === 200 && visible === 1 && rows.length === 1
        && (after.list || []).length === baseline.list.length + 1;
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null : `visible=${visible}; backend rows=${rows.length}`,
        data: {
          http: nav.status, ui_visible: visible,
          backend_rows: rows.map((p) => ({ id: p.id, provider_type: p.provider_type, base_url: p.base_url })),
          after_count: after.list ? after.list.length : null,
        },
      };
    });

    await runCheck({
      id: "local_models.delete_removed", area: "local_models",
      description: "Delete removes the disposable provider from the page and the backend",
    }, async () => {
      // Nearest ancestor card that owns both the exact provider name and a
      // Delete button. A broad `div` filter matches every wrapper, so the
      // XPath axis keeps the click unambiguous.
      const card = page.getByText(DISPOSABLE_PROVIDER_NAME, { exact: true }).first()
        .locator("xpath=ancestor::div[.//button[contains(normalize-space(.), 'Delete')]][1]");
      const count = await card.count();
      if (count !== 1) {
        throw new Error(`expected exactly one disposable provider card, found ${count}`);
      }
      const res = await clickAndWait(page,
        (r) => r.url().includes("/api/local-models/") && r.request().method() === "DELETE",
        () => card.getByRole("button", { name: /Delete/ }).click());
      await page.waitForTimeout(800);
      const visible = await page.getByText(DISPOSABLE_PROVIDER_NAME, { exact: true }).count();
      const reloadNav = await gotoRoute(page, "/settings/local-models", { heading: "Local Models" });
      const visibleAfterReload = await page.getByText(DISPOSABLE_PROVIDER_NAME, { exact: true }).count();
      const after = await localModelList(token);
      const idsAfter = after.list ? after.list.map((p) => p.id).sort() : null;
      const ok = res.status === 200 && visible === 0 && visibleAfterReload === 0
        && idsAfter !== null && JSON.stringify(idsAfter) === JSON.stringify(baselineIds);
      if (ok) createdId = null;
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null : `DELETE -> ${res.status}; visible=${visible}; after_reload=${visibleAfterReload}`,
        data: {
          http: res.status, ui_visible_after_delete: visible,
          ui_visible_after_reload: visibleAfterReload, reload_http: reloadNav.status,
          provider_set_matches_baseline: idsAfter !== null
            && JSON.stringify(idsAfter) === JSON.stringify(baselineIds),
        },
      };
    });

    await runCheck({
      id: "local_models.no_provider_contact", area: "local_models",
      description: "the disposable provider was never contacted (no Discover/Test, no egress)",
    }, async () => {
      const host = new URL(DISPOSABLE_PROVIDER_URL).host;
      const hostHits = net.external.filter((e) => e.host === host);
      const externalApi = net.external.filter((e) => e.is_api);
      const nonLoopback = externalApi.filter(
        (e) => !/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(e.origin));
      const ok = hostHits.length === 0 && nonLoopback.length === 0;
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null : "an unexpected provider/external request was observed",
        data: {
          provider_host: host,
          provider_host_requests: hostHits.length,
          external_api_requests: externalApi.slice(0, 10),
          non_loopback_requests: nonLoopback.slice(0, 10),
          all_external_requests: net.external.slice(0, 20),
        },
      };
    });
  } finally {
    // Bounded cleanup: never leave the disposable row in the world.
    if (createdId) {
      const cleanup = await api("DELETE", `/api/local-models/${createdId}`, { token });
      evidence.local_models_cleanup = {
        attempted: true, provider_id: createdId, http: cleanup.status,
      };
    } else {
      evidence.local_models_cleanup = {
        attempted: false,
        reason: "no disposable provider id was created, or the page already deleted it",
      };
    }
  }
}

/* ------------------------------------------------------------------ */
/* 5. Sessions — disposable secondary session                         */
/* ------------------------------------------------------------------ */

async function formLogin(page) {
  await page.goto(`${FRONTEND}/login`, { waitUntil: "domcontentloaded", timeout: TIMEOUT });
  await page.getByTestId("login-email-input").fill(EMAIL);
  await page.getByTestId("login-password-input").fill(PASSWORD);
  const started = Date.now();
  await page.getByTestId("login-submit-button").click();
  let landed = false;
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(500);
    const p = new URL(page.url()).pathname;
    if (!p.startsWith("/login")) { landed = true; break; }
    if (Date.now() - started > TIMEOUT) break;
  }
  const text = await bodyText(page);
  const token = await page.evaluate(() => {
    try { return localStorage.getItem("auth_token"); } catch { return null; }
  });
  registerSecret(token);
  return { landed, finalPath: new URL(page.url()).pathname, token, textSample: text.slice(0, 500) };
}

async function sessionsChecks({ browser, page, token }) {
  let secondary = null;
  let secondaryLogin = null;
  const registryBefore = await api("GET", "/api/users/sessions", { token });
  const idsBefore = Array.isArray(registryBefore.json)
    ? registryBefore.json.map((row) => row.id) : [];
  try {
    await runCheck({
      id: "sessions.disposable_secondary_session", area: "sessions",
      description: "a disposable secondary browser signs in through the real login form",
    }, async () => {
      secondary = await browser.newContext({
        viewport: { width: 1280, height: 900 },
        userAgent: "AtomWA075DisposableSession/1.0 (acceptance)",
      });
      const p2 = await secondary.newPage();
      attachNetwork(p2, "secondary");
      const secondaryCaptured = collectErrors(p2);
      secondaryLogin = await formLogin(p2);
      evidence.secondary_page_errors = {
        page_errors: secondaryCaptured.pageErrors.slice(0, 10),
        console_errors: secondaryCaptured.consoleErrors.slice(0, 10),
        bad_responses: secondaryCaptured.badResponses.slice(0, 10),
      };
      evidence.sessions = {
        secondary_final_path: secondaryLogin.finalPath,
        secondary_web_session: secondaryLogin.landed,
        secondary_has_backend_token: Boolean(secondaryLogin.token),
        login_error_text: secondaryLogin.landed ? null : secondaryLogin.textSample,
      };
      await shot(p2, "05_sessions_secondary_login");
      const ok = secondaryLogin.landed && Boolean(secondaryLogin.token);
      return {
        status: ok ? "pass" : "missing",
        reason: ok ? null
          : `real form login did not establish a session (final path ${secondaryLogin.finalPath}): `
            + (secondaryLogin.textSample.split("\n").slice(0, 4).join(" ")),
        data: evidence.sessions,
      };
    });

    // A session-management view must be able to see BOTH live sign-ins: the
    // token-seeded primary (browser_core_surface convention) and the
    // disposable secondary that just signed in through the form.
    const primaryNav = await gotoRoute(page, "/settings/sessions", { heading: "Active Sessions" });
    const primaryText = await bodyText(page);
    const secondaryPage = secondary ? secondary.pages()[0] : null;
    const secondaryNav = secondaryPage
      ? await gotoRoute(secondaryPage, "/settings/sessions", { heading: "Active Sessions" })
      : null;
    const secondaryText = secondaryPage ? await bodyText(secondaryPage) : "";
    const primarySessionGets = net.entries
      .filter((e) => e.label === "primary" && e.path === "/api/auth/sessions" && e.method === "GET");
    const secondarySessionGets = net.entries
      .filter((e) => e.label === "secondary" && e.path === "/api/auth/sessions" && e.method === "GET");
    const registry = await api("GET", "/api/users/sessions", { token });
    const registryRows = Array.isArray(registry.json) ? registry.json : null;
    evidence.sessions = {
      ...(evidence.sessions || {}),
      primary_page: { http: primaryNav.status, text_sample: primaryText.slice(0, 400) },
      secondary_page: secondaryNav
        ? { http: secondaryNav.status, text_sample: secondaryText.slice(0, 400) }
        : null,
      frontend_sessions_http_primary: primarySessionGets.length
        ? primarySessionGets[primarySessionGets.length - 1].status : null,
      frontend_sessions_http_secondary: secondarySessionGets.length
        ? secondarySessionGets[secondarySessionGets.length - 1].status : null,
      backend_registry_http: registry.status,
      backend_registry_rows: registryRows ? registryRows.length : null,
      backend_registry_ids: registryRows ? registryRows.map((r) => r.id) : null,
    };

    await runCheck({
      id: "sessions.page_loads", area: "sessions",
      description: "the Active Sessions tab renders its shell (data failure is reported separately)",
    }, async () => {
      const text = primaryText + "\n" + secondaryText;
      const shell = /Active Sessions/.test(text) && /Your Devices/.test(text);
      const statuses = [primaryNav.status, secondaryNav ? secondaryNav.status : null]
        .filter((s) => s !== null);
      const dataError = /Failed to fetch sessions|Failed to load session information/.test(text);
      const ok = shell && statuses.every((s) => s === 200);
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null : `shell=${shell}; http=${statuses.join(",")}`,
        data: {
          primary_http: primaryNav.status,
          secondary_http: secondaryNav ? secondaryNav.status : null,
          shell_rendered: shell,
          session_data_error_shown: dataError,
          text_sample: text.slice(0, 400),
        },
      };
    });

    await runCheck({
      id: "sessions.list_reflects_live_sessions", area: "sessions",
      description: "the tab lists both live sign-ins and can identify the current device",
    }, async () => {
      const http = evidence.sessions.frontend_sessions_http_secondary
        ?? evidence.sessions.frontend_sessions_http_primary;
      const rows = evidence.sessions.backend_registry_rows;
      const reasons = [];
      if (!secondaryLogin || !secondaryLogin.landed) {
        reasons.push("the disposable secondary never established a web session");
      }
      if (http !== 200) reasons.push(`GET /api/auth/sessions -> ${http}`);
      if (rows === null) reasons.push(`GET /api/users/sessions -> ${evidence.sessions.backend_registry_http}`);
      else if (rows < 2) {
        reasons.push(
          `backend session registry has ${rows} active row(s) while two browsers are signed in; `
          + "no production code writes UserSession rows and the Next API route queries Postgres directly");
      }
      if (reasons.length === 0) {
        const text = `${primaryText}\n${secondaryText}`;
        const devices = (text.match(/Revoke|Current Device/g) || []).length;
        if (!/Current Device/.test(text)) reasons.push("no current-device badge rendered");
        if (devices === 0) reasons.push("no session rows rendered");
      }
      return {
        status: reasons.length === 0 ? "pass" : "missing",
        reason: reasons.length ? reasons.join("; ") : null,
        data: {
          frontend_sessions_http_secondary: http,
          backend_registry_http: evidence.sessions.backend_registry_http,
          backend_registry_rows: rows,
          two_live_sign_ins: Boolean(secondaryLogin && secondaryLogin.landed),
          capability_gap: reasons.length > 0,
        },
      };
    });

    await runCheck({
      id: "sessions.revoke_disposable", area: "sessions",
      description: "Revoke signs the disposable secondary out while the primary session stays",
    }, async () => {
      const rows = evidence.sessions.backend_registry_rows;
      const http = evidence.sessions.frontend_sessions_http_secondary;
      if (http !== 200 || rows === null || rows < 2) {
        return {
          status: "skipped",
          reason: "the tab cannot list sessions in this build; there is no row to revoke "
            + "(see sessions.list_reflects_live_sessions)",
          data: { rows, http },
        };
      }
      if (!secondaryLogin || !secondaryLogin.token) {
        return {
          status: "skipped",
          reason: "the disposable secondary has no authenticated bearer to identify its own row",
          data: { secondary_web_session: Boolean(secondaryLogin && secondaryLogin.landed) },
        };
      }

      // Identify the disposable row from the secondary's OWN authenticated
      // list. The bootstrap bearer that mints the API token is registered as a
      // session too, so the primary page legitimately shows two non-current
      // rows; "the only revocable row" or "the first Revoke button" is not the
      // disposable session.
      //
      // Reload the primary list immediately before acting so the rendered
      // order and the order used to pick the control come from the same
      // inventory. The page's heartbeat only touches its current row, which is
      // excluded from `revocableRows`, so non-current order stays stable.
      const primaryNav = await gotoRoute(page, "/settings/sessions", {
        heading: "Active Sessions",
      });
      const primaryToken = await page.evaluate(() => {
        try { return localStorage.getItem("auth_token"); } catch { return null; }
      });
      registerSecret(primaryToken);
      const primaryBearer = primaryToken || token;
      const secondaryRowsResponse = await api("GET", "/api/users/sessions", {
        token: secondaryLogin.token,
      });
      const primaryRowsResponse = await api("GET", "/api/users/sessions", {
        token: primaryBearer,
      });
      const secondaryRows = Array.isArray(secondaryRowsResponse.json)
        ? secondaryRowsResponse.json : null;
      const primaryRows = Array.isArray(primaryRowsResponse.json)
        ? primaryRowsResponse.json : null;
      const selection = selectDisposableSession({ secondaryRows, primaryRows });
      if (!selection.ok) {
        return {
          status: "missing",
          reason: selection.reason,
          data: {
            secondary_registry_http: secondaryRowsResponse.status,
            primary_registry_http: primaryRowsResponse.status,
            secondary_rows: secondaryRows ? secondaryRows.length : null,
            primary_rows: primaryRows ? primaryRows.length : null,
            primary_page_http: primaryNav.status,
          },
        };
      }
      if (selection.row.revocable === false) {
        return {
          status: "missing",
          reason: "the secondary's own current row reports that it is not revocable",
          data: {
            target_session_id: selection.id,
            target_control_index: selection.controlIndex,
          },
        };
      }

      const revokeButtons = page.getByRole("button", { name: "Revoke" });
      const controlCount = await revokeButtons.count();
      const expectedControls = revocableRows(primaryRows).length;
      if (controlCount !== expectedControls) {
        return {
          status: "fail",
          reason: `the primary page rendered ${controlCount} Revoke control(s) for `
            + `${expectedControls} non-current row(s)`,
          data: {
            controls: controlCount,
            non_current_rows: expectedControls,
            target_control_index: selection.controlIndex,
          },
        };
      }

      // The page confirms before revoking; accept that native dialog as the
      // operator would, then wait for the DELETE the control issues.
      const acceptConfirm = (dialog) => dialog.accept().catch(() => {});
      page.on("dialog", acceptConfirm);
      let res;
      try {
        res = await clickAndWait(page,
          (r) => r.url().includes("/api/auth/sessions") && r.request().method() === "DELETE",
          () => revokeButtons.nth(selection.controlIndex).click());
      } finally {
        page.off("dialog", acceptConfirm);
      }
      await page.waitForTimeout(1000);
      const after = await api("GET", "/api/users/sessions", { token: primaryBearer });
      const afterRows = Array.isArray(after.json) ? after.json : null;
      const secondaryMe = await api("GET", "/api/auth/me", {
        token: secondaryLogin.token,
      });
      const primaryMe = await api("GET", "/api/auth/me", { token: primaryBearer });
      const primaryCurrent = ownCurrentSession(primaryRows);
      const targetGone = Boolean(afterRows)
        && !afterRows.some((row) => row.id === selection.id);
      const primaryStillListed = Boolean(afterRows)
        && (!primaryCurrent || afterRows.some((row) => row.id === primaryCurrent.id));
      const ok = res.status === 200
        && afterRows !== null
        && afterRows.length === primaryRows.length - 1
        && targetGone
        && secondaryMe.status === 401
        && primaryMe.status === 200
        && primaryStillListed;
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null
          : `DELETE -> ${res.status}; rows ${primaryRows.length} -> `
            + `${afterRows ? afterRows.length : null}; target removed ${targetGone}; `
            + `secondary /me ${secondaryMe.status}; primary /me ${primaryMe.status}; `
            + `primary row present ${primaryStillListed}`,
        data: {
          http: res.status,
          rows_before: primaryRows.length,
          rows_after: afterRows ? afterRows.length : null,
          target_session_id: selection.id,
          target_control_index: selection.controlIndex,
          non_current_rows: expectedControls,
          target_row_removed: targetGone,
          secondary_me_after_revoke: secondaryMe.status,
          primary_me_after_revoke: primaryMe.status,
          primary_row_present_after: primaryStillListed,
          primary_page_http: primaryNav.status,
        },
      };
    });
  } finally {
    if (secondary) await secondary.close().catch(() => {});
    // Bounded cleanup: any session row that appeared during this run (and was
    // not deliberately revoked by the check) is revoked through the same
    // public route the product uses. Rows that existed before are untouched.
    const after = await api("GET", "/api/users/sessions", { token });
    const leftover = Array.isArray(after.json)
      ? after.json.filter((row) => !idsBefore.includes(row.id) && !row.is_current)
      : [];
    const revoked = [];
    for (const row of leftover) {
      const del = await api("DELETE", `/api/users/sessions/${row.id}`, { token });
      revoked.push({ id: row.id, http: del.status });
    }
    evidence.sessions_cleanup = {
      registry_before: idsBefore.length,
      registry_after: Array.isArray(after.json) ? after.json.length : null,
      revoked,
    };
  }
}

/* ------------------------------------------------------------------ */
/* 6. Account — profile + reversible password rotation                */
/* ------------------------------------------------------------------ */

async function ensureOriginalPassword(rotatedRef, log) {
  const candidates = [PASSWORD, rotatedRef.value].filter(Boolean);
  let active = null;
  for (const candidate of candidates) {
    const attempt = await tryLogin(candidate);
    if (attempt.ok) { active = { password: candidate, token: attempt.token }; break; }
  }
  if (!active) {
    log.status = "failed";
    log.reason = "neither the original nor the rotated password signs in; recover the "
      + "scratch admin with scripts/acceptance/scratch_admin_password.py (0600 password file)";
    return log;
  }
  if (active.password === PASSWORD) {
    log.status = "already_original";
    return { ...log, verified: true };
  }
  const res = await api("POST", "/api/auth/change-password", {
    token: active.token,
    body: { current_password: active.password, new_password: PASSWORD },
  });
  if (res.status !== 200) {
    log.status = "failed";
    log.reason = `restore POST -> ${res.status}`;
    return log;
  }
  const verified = await tryLogin(PASSWORD);
  return { ...log, status: verified.ok ? "restored" : "failed", verified: verified.ok };
}

/**
 * Interpret a 2FA setup response without keeping its body.
 *
 * The live payload is not small: the secret, its otpauth:// provisioning URL
 * and the operation receipt put it far past any fixed sample budget. Truncating
 * the text before JSON.parse() therefore turned a valid HTTP 200 into "no
 * secret", and the check then blamed a routing gap that no longer existed. The
 * whole body is parsed here, in memory; only these derived facts leave this
 * function, so no part of the body (least of all the secret) can be persisted.
 * The caller registers `secret` for redaction and never records it.
 */
function interpretTwoFactorSetup({ status, text, contentType = null }) {
  const raw = typeof text === "string" ? text : "";
  let body = null;
  let parseError = null;
  try {
    body = JSON.parse(raw);
  } catch (err) {
    parseError = String((err && err.message) || err).slice(0, 120);
  }
  const json = body && typeof body === "object" && !Array.isArray(body) ? body : null;
  const secret = json && typeof json.secret === "string" && json.secret.length > 0
    ? json.secret : null;
  const detail = json ? json.detail : undefined;
  return {
    http: status,
    content_type: contentType || null,
    body_bytes: Buffer.byteLength(raw, "utf8"),
    json_parsed: Boolean(json),
    parse_error: parseError,
    secret,
    secret_returned: Boolean(secret),
    error_detail_present: detail !== undefined && detail !== null,
    body_persisted: false,
  };
}

/**
 * Describe only what the captured response proves. The previous wording
 * asserted a specific Next rewrite gap ("the tab's 2FA setup call is not
 * routed ... NextAuth catch-all"); that claim became a false explanation once
 * the routes existed, so status and parse outcome are reported instead.
 */
function describeTwoFactorSetup(setup) {
  const type = setup.content_type ? `, content-type ${setup.content_type}` : "";
  if (setup.http === -1) {
    return "POST /api/auth/2fa/setup could not be reached through the frontend "
      + "origin; the status read still works, but setup was never exercised";
  }
  if (setup.http === 200 && setup.secret_returned) return null;
  if (setup.http === 200 && !setup.json_parsed) {
    return "POST /api/auth/2fa/setup answered HTTP 200 with a "
      + `${setup.body_bytes}-byte body that is not JSON${type}`
      + (setup.parse_error ? ` (${setup.parse_error})` : "")
      + "; a 200 alone does not prove routing, and this is not the backend's "
      + "setup payload. The body was parsed in memory only and not persisted.";
  }
  if (setup.http === 200) {
    return "POST /api/auth/2fa/setup answered HTTP 200 with a "
      + `${setup.body_bytes}-byte JSON body${type} that carried no secret, so the `
      + "endpoint declined to mint an enrollment (2FA may already be enabled)";
  }
  return `POST /api/auth/2fa/setup -> HTTP ${setup.http} with a `
    + `${setup.body_bytes}-byte ${setup.json_parsed ? "JSON" : "non-JSON"} body${type}; `
    + "the endpoint refused the request"
    + (setup.error_detail_present ? " and returned an error detail (not persisted)" : "");
}

/** Response header lookup that tolerates the catch-fallback response stub. */
function responseHeader(res, name) {
  try {
    const headers = typeof res.headers === "function" ? res.headers() : null;
    const value = headers ? headers[name] : null;
    return typeof value === "string" ? value.slice(0, 120) : null;
  } catch {
    return null;
  }
}

async function accountChecks({ browser, page, token }) {
  const rotatedRef = { value: null };
  const recovery = { attempted: false, status: "not_needed", password_value_recorded: false };
  let accountNav = null;
  let accountsHttp = null;
  let text = "";

  try {
    await runCheck({
      id: "account.page_loads", area: "account",
      description: "Account Settings loads the signed-in user's profile",
    }, async () => {
      const wait = page.waitForResponse(
        (r) => r.url().includes("/api/auth/accounts") && r.request().method() === "GET",
        { timeout: TIMEOUT }).catch(() => null);
      accountNav = await gotoRoute(page, "/settings/account", { heading: "Account Settings" });
      const res = await wait;
      accountsHttp = res ? res.status() : null;
      text = await bodyText(page);
      await shot(page, "01_account");
      const showsEmail = text.includes(EMAIL);
      const loadError = /Failed to load account information|Failed to load account/i.test(text);
      const ok = accountNav.status === 200 && showsEmail && !loadError
        && (accountsHttp === null || accountsHttp === 200);
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null : `http=${accountNav.status} accounts_http=${accountsHttp} email_shown=${showsEmail} load_error=${loadError}`,
        data: {
          http: accountNav.status, accounts_http: accountsHttp,
          email_shown: showsEmail, load_error_shown: loadError,
          sections_found: ["Profile Information", "Change Password", "Two-Factor Authentication", "Linked Accounts"]
            .filter((s) => text.includes(s)),
          text_sample: text.slice(0, 300),
        },
      };
    });

    await runCheck({
      id: "account.profile_readback", area: "account",
      description: "the profile fields rendered are the backend's own /api/auth/me values",
    }, async () => {
      const me = await api("GET", "/api/auth/me", { token });
      if (me.status !== 200 || !me.json) {
        return { status: "fail", reason: `GET /api/auth/me -> ${me.status}`, data: { http: me.status } };
      }
      const meEmail = me.json.email || (me.json.user && me.json.user.email);
      const linked = /Email\/Password/.test(text);
      return {
        status: meEmail === EMAIL && linked ? "pass" : "fail",
        reason: meEmail === EMAIL ? null : `backend email ${meEmail} != ${EMAIL}`,
        data: {
          backend_email: meEmail, ui_email: EMAIL,
          linked_credentials_row: linked, accounts_http: accountsHttp,
          accounts_route: "Next API route /api/auth/accounts -> backend /api/auth/me",
        },
      };
    });

    await runCheck({
      id: "account.two_factor_surface", area: "account",
      description: "the 2FA card reports the real status; the enable/disable controls are reachable",
    }, async () => {
      const statusRes = await page.request.get(`${FRONTEND}/api/auth/2fa/status`, {
        headers: { Authorization: `Bearer ${token}` },
      }).catch((err) => ({
        status: () => -1, text: async () => String(err), headers: () => ({}),
      }));
      let statusBody = null;
      try { statusBody = await statusRes.json(); } catch { /* non-JSON */ }
      // Probe the setup endpoint the tab calls. This only creates (or recovers)
      // a pending enrollment secret when it actually works; it does not enable
      // 2FA. The whole body is read and parsed in memory — the otpauth:// URL
      // and verification receipt do not fit in any small sample — and only
      // derived facts are recorded: no part of the body (least of all a
      // secret) is persisted.
      const setupRes = await page.request.post(`${FRONTEND}/api/auth/2fa/setup`, {
        headers: { Authorization: `Bearer ${token}` },
      }).catch((err) => ({
        status: () => -1, text: async () => String(err), headers: () => ({}),
      }));
      const setup = interpretTwoFactorSetup({
        status: setupRes.status(),
        text: await setupRes.text().catch(() => ""),
        contentType: responseHeader(setupRes, "content-type"),
      });
      // Register for redaction only; the value never reaches the evidence.
      registerSecret(setup.secret);
      evidence.account_two_factor = {
        status_http: statusRes.status(),
        enabled: statusBody ? Boolean(statusBody.enabled) : null,
        setup_http: setup.http,
        setup_content_type: setup.content_type,
        setup_body_bytes: setup.body_bytes,
        setup_json_parsed: setup.json_parsed,
        setup_parse_error: setup.parse_error,
        setup_secret_returned: setup.secret_returned,
        setup_error_detail_present: setup.error_detail_present,
        setup_body_persisted: false,
        toggle_exercised: false,
      };
      if (!setup.secret_returned) {
        return {
          status: "missing",
          reason: describeTwoFactorSetup(setup),
          data: evidence.account_two_factor,
        };
      }
      return {
        status: "pass",
        reason: null,
        data: {
          ...evidence.account_two_factor,
          note: "setup is reachable; the enable/disable round trip runs only with --exercise-2fa",
        },
      };
    });

    if (EXERCISE_2FA && evidence.account_two_factor.setup_secret_returned) {
      await runCheck({
        id: "account.two_factor_reversible", area: "account",
        description: "2FA can be enabled, survives reload, and is disabled again",
      }, async () => {
        const start = await page.request.post(`${FRONTEND}/api/auth/2fa/setup`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const setup = await start.json();
        const secret = setup.secret;
        registerSecret(secret);
        const enableAtMs = Date.now();
        const enable = await page.request.post(`${FRONTEND}/api/auth/2fa/enable`, {
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          data: { code: totpCode(secret, enableAtMs) },
        });
        // The backend records the accepted step at enable. Anchor on the
        // response, not the request, so a request that crossed a boundary
        // cannot make the next wait land in the step enable just spent.
        const enableCompletedAtMs = Date.now();
        const enabledBody = await enable.json().catch(() => null);
        await gotoRoute(page, "/settings/account", { heading: "Account Settings" });
        const enabledText = await bodyText(page);
        const shownEnabled = /secured with two-factor authentication/i.test(enabledText);
        // A reused step is refused (409) even though the code is still valid.
        // Wait into a later step, then compute the current code as usual.
        const disableWaitMs = freshTotpStepDelayMs(enableCompletedAtMs, {
          marginMs: TOTP_STEP_MARGIN_MS,
        });
        if (disableWaitMs > 0) await page.waitForTimeout(disableWaitMs);
        const disableAtMs = Date.now();
        const disable = await page.request.post(`${FRONTEND}/api/auth/2fa/disable`, {
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          data: { code: totpCode(secret, disableAtMs) },
        });
        const disableCompletedAtMs = Date.now();
        await gotoRoute(page, "/settings/account", { heading: "Account Settings" });
        const disabledText = await bodyText(page);
        const shownDisabled = /Add an extra layer of security/i.test(disabledText);
        // Never leave the scratch admin locked behind an unwritten secret.
        const statusAfter = await api("GET", "/api/auth/2fa/status", { token });
        let recovery = null;
        let cleanupWaitMs = 0;
        if (statusAfter.json && statusAfter.json.enabled === true) {
          // Cleanup may run after a failed disable. Wait past every step this
          // check has spent (enable and the disable attempt) before retrying.
          cleanupWaitMs = freshTotpStepDelayMs(
            Math.max(enableCompletedAtMs, disableCompletedAtMs),
            { marginMs: TOTP_STEP_MARGIN_MS });
          if (cleanupWaitMs > 0) await page.waitForTimeout(cleanupWaitMs);
          const cleanupAtMs = Date.now();
          const direct = await api("POST", "/api/auth/2fa/disable", {
            token, body: { code: totpCode(secret, cleanupAtMs) },
          });
          recovery = { http: direct.status, route: "backend_direct" };
        }
        const stillEnabled = statusAfter.json ? statusAfter.json.enabled === true : null;
        const recovered = !stillEnabled || (recovery && recovery.http === 200);
        const ok = enable.status() === 200 && shownEnabled
          && disable.status() === 200 && shownDisabled && recovered;
        return {
          status: ok ? "pass" : "fail",
          reason: ok ? null
            : `enable=${enable.status()} shown=${shownEnabled} disable=${disable.status()} `
              + `shown_disabled=${shownDisabled} recovered=${recovered}. `
              + (recovered ? "" : "2FA may still be enabled; disable it through "
                + "/api/auth/2fa/disable with a current code before reusing the world."),
          data: {
            enable_http: enable.status(), enabled_state_shown: shownEnabled,
            disable_http: disable.status(), disabled_state_shown: shownDisabled,
            backup_codes_returned: Boolean(enabledBody && (enabledBody.data?.backup_codes || enabledBody.backup_codes)),
            enabled_after_check: stillEnabled,
            recovery,
            totp_step_waits_ms: { disable: disableWaitMs, cleanup: cleanupWaitMs },
            secret_recorded: false,
          },
        };
      });
    }

    if (SKIP_PASSWORD) {
      for (const [id, description] of [
        ["account.password_change_saved",
          "a password change is accepted, saves durably, and forces re-authentication"],
        ["account.password_reload",
          "the new password signs in and the Account tab loads again after reload"],
        ["account.password_restored",
          "the original password is restored through the tab and verified again"],
      ]) {
        record({
          id, area: "account", description, status: "skipped",
          reason: "--skip-account-password was passed; Account coverage stayed read-only",
          data: { operator_choice: true },
        });
      }
      return;
    }

    await runCheck({
      id: "account.password_change_saved", area: "account",
      description: "a password change is accepted, saves durably, and forces re-authentication",
    }, async () => {
      // The rotated password is minted at runtime and never appears as a
      // literal in this source: no fixed prefix, no credential-shaped string.
      // The value is registered below so the evidence scan still refuses to
      // persist it.
      rotatedRef.value = crypto.randomBytes(10).toString("hex");
      registerSecret(rotatedRef.value);
      await page.locator("#currentPassword").fill(PASSWORD);
      await page.locator("#newPassword").fill(rotatedRef.value);
      await page.locator("#confirmPassword").fill(rotatedRef.value);
      const res = await clickAndWait(page,
        (r) => r.url().includes("/api/auth/change-password") && r.request().method() === "POST",
        () => page.getByRole("button", { name: "Update Password" }).click());
      let signedOut = false;
      for (let i = 0; i < 30; i++) {
        await page.waitForTimeout(500);
        if (/^\/(login|auth\/signin|signin)/.test(new URL(page.url()).pathname)) { signedOut = true; break; }
      }
      // Prove the durable effect at the credentials boundary: old rejected,
      // new accepted. Password values are never recorded. A 429 is NOT a
      // rejection - it means the rate limiter interfered, and the check must
      // say so instead of passing.
      const oldTry = await tryLogin(PASSWORD);
      const newTry = await tryLogin(rotatedRef.value);
      rotatedRef.token = newTry.token;
      const oldRejected = [400, 401, 403].includes(oldTry.status);
      const ok = res.status === 200 && res.json && res.json.requires_reauthentication === true
        && oldRejected && newTry.ok;
      return {
        status: ok ? "pass" : "fail",
        reason: ok ? null
          : `POST -> ${res.status}; old login -> ${oldTry.status} (rejected=${oldRejected}); new login -> ${newTry.status}`,
        data: {
          http: res.status,
          requires_reauthentication: res.json ? res.json.requires_reauthentication : null,
          revoked_sessions: res.json ? res.json.revoked_sessions ?? null : null,
          ui_signed_out: signedOut,
          old_login_status: oldTry.status,
          old_password_rejected: oldRejected,
          new_login_status: newTry.status,
          new_password_accepted: newTry.ok,
          password_value_recorded: false,
        },
      };
    });

    await runCheck({
      id: "account.password_reload", area: "account",
      description: "the new password signs in and the Account tab loads again after reload",
    }, async () => {
      if (!rotatedRef.value) throw new Error("no rotated password to verify");
      if (!rotatedRef.token) {
        const login = await tryLogin(rotatedRef.value);
        if (!login.ok) {
          return { status: "fail", reason: `new password login -> ${login.status}`, data: {} };
        }
        rotatedRef.token = login.token;
      }
      const fresh = await newSeededPage(browser, rotatedRef.token);
      try {
        const nav = await gotoRoute(fresh.page, "/settings/account", { heading: "Account Settings" });
        const t = await bodyText(fresh.page);
        const me = await api("GET", "/api/auth/me", { token: rotatedRef.token });
        const ok = nav.status === 200 && t.includes(EMAIL) && me.status === 200;
        return {
          status: ok ? "pass" : "fail",
          reason: ok ? null : `http=${nav.status} email_shown=${t.includes(EMAIL)} me=${me.status}`,
          data: { http: nav.status, email_shown: t.includes(EMAIL), me_http: me.status },
        };
      } finally {
        await fresh.context.close().catch(() => {});
      }
    });

    await runCheck({
      id: "account.password_restored", area: "account",
      description: "the original password is restored through the tab and verified again",
    }, async () => {
      if (!rotatedRef.value) throw new Error("no rotated password to restore");
      if (!rotatedRef.token) {
        const login = await tryLogin(rotatedRef.value);
        if (!login.ok) {
          return { status: "fail", reason: `new password login -> ${login.status}`, data: {} };
        }
        rotatedRef.token = login.token;
      }
      const fresh = await newSeededPage(browser, rotatedRef.token);
      try {
        const nav = await gotoRoute(fresh.page, "/settings/account", { heading: "Account Settings" });
        await fresh.page.locator("#currentPassword").fill(rotatedRef.value);
        await fresh.page.locator("#newPassword").fill(PASSWORD);
        await fresh.page.locator("#confirmPassword").fill(PASSWORD);
        const res = await clickAndWait(fresh.page,
          (r) => r.url().includes("/api/auth/change-password") && r.request().method() === "POST",
          () => fresh.page.getByRole("button", { name: "Update Password" }).click());
        const original = await tryLogin(PASSWORD);
        const rotated = await tryLogin(rotatedRef.value);
        const rotatedRejected = [400, 401, 403].includes(rotated.status);
        const verify = await newSeededPage(browser, original.token || token);
        try {
          const reload = await gotoRoute(verify.page, "/settings/account", { heading: "Account Settings" });
          const t = await bodyText(verify.page);
          const ok = nav.status === 200 && res.status === 200 && original.ok
            && rotatedRejected && reload.status === 200 && t.includes(EMAIL);
          return {
            status: ok ? "pass" : "fail",
            reason: ok ? null
              : `POST -> ${res.status}; original login -> ${original.status}; rotated login -> ${rotated.status} (rejected=${rotatedRejected})`,
            data: {
              http: res.status, original_password_accepted: original.ok,
              rotated_login_status: rotated.status,
              rotated_password_rejected: rotatedRejected,
              reload_http: reload.status, email_shown_after_restore: t.includes(EMAIL),
              password_value_recorded: false,
            },
          };
        } finally {
          await verify.context.close().catch(() => {});
        }
      } finally {
        await fresh.context.close().catch(() => {});
      }
    });
  } finally {
    recovery.attempted = true;
    evidence.account_password_recovery = await ensureOriginalPassword(rotatedRef, recovery);
    if (evidence.account_password_recovery.status === "failed") {
      record({
        id: "account.password_cleanup", area: "account", status: "fail",
        description: "leave the scratch world's original password in place",
        reason: evidence.account_password_recovery.reason,
        data: evidence.account_password_recovery,
      });
    }
  }
}

/* ------------------------------------------------------------------ */
/* Main                                                               */
/* ------------------------------------------------------------------ */

(async () => {
  if (!PASSWORD) {
    console.error("set ATOM_SCOPE_PASSWORD for the isolated world (never a live credential)");
    process.exit(2);
  }

  // Identity before mutations. No setting is read, saved or restored until the
  // answering backend reports the exact scratch world database and port, and
  // the frontend identifies itself as the scratch Next app.
  const identity = await verifyScratchIdentity();
  record({
    id: "run.scratch_identity",
    area: "run",
    description: "the answering stack is the pinned scratch frontend/backend for ATOM_WA075_WORLD",
    status: identity.ok ? "pass" : "fail",
    reason: identity.ok ? null : identity.problems.join("; "),
    data: identity.evidence,
  });
  if (!identity.ok) {
    console.error(JSON.stringify({
      fatal: "scratch identity not verified; nothing was changed",
      problems: identity.problems,
      evidence: identity.evidence,
    }, null, 2));
    process.exit(2);
  }

  if (!(await waitForFrontend(FRONTEND, 10, 1000))) {
    console.error(`frontend is not serving ${FRONTEND}; start the isolated world first`);
    process.exit(2);
  }

  let token;
  try {
    token = await loginToken({ backend: BACKEND, email: EMAIL, password: PASSWORD });
  } catch (err) {
    console.error(`backend login failed: ${String(err.message || err).slice(0, 300)}`);
    process.exit(2);
  }
  registerSecret(token);

  const browser = await chromium.launch(CHROME_EXECUTABLE
    ? { headless: true, executablePath: CHROME_EXECUTABLE }
    : { headless: true, channel: "chrome" });
  const browserLaunch = {
    mode: CHROME_EXECUTABLE ? "pinned_executable" : "installed_chrome_channel",
    executable: CHROME_EXECUTABLE || null,
    version: browser.version(),
  };

  // Prefer the ordinary sign-in form (that is the boundary WA-075 claims).
  // Fall back to the browser_core_surface token contract only when the real
  // web session cannot be established, and record which one was used.
  let primary = null;
  let signIn = null;
  const formContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const formPage = await formContext.newPage();
  attachNetwork(formPage, "primary");
  const formLoginResult = await formLogin(formPage).catch((err) => ({
    landed: false,
    finalPath: "/login",
    token: null,
    textSample: `login form error: ${String(err.message || err).slice(0, 300)}`,
  }));
  if (formLoginResult.landed && formLoginResult.token) {
    primary = { context: formContext, page: formPage };
    signIn = {
      mechanism: "real login form (data-testid login-*) -> NextAuth web session "
        + "+ backend bearer",
      web_session: true,
      final_path: formLoginResult.finalPath,
      password_recorded: false,
    };
  } else {
    await formContext.close().catch(() => {});
    primary = await newSeededPage(browser, token);
    signIn = {
      mechanism: "browser_core_surface token seed (auth_token cookie/localStorage)",
      web_session: false,
      reason: "the real login form did not establish a session",
      login_text_sample: formLoginResult.textSample.slice(0, 400),
      password_recorded: false,
    };
  }
  const page = primary.page;
  const captured = collectErrors(page);
  const startedAt = new Date().toISOString();
  let fatalError = null;

  try {
    try {
      await checkSignedIn(token);
      await aiChecks({ page, token });
      await routingChecks({ page });
      await localModelsChecks({ page, token });
      await sessionsChecks({ browser, page, token });
      // Account runs last: changing the password revokes every token, so every
      // earlier check must already have run on the intact session.
      await accountChecks({ browser, page, token });
    } catch (err) {
      // A fatal mid-run error must still produce evidence: the checks that
      // already ran are the record of what the product did before it broke.
      fatalError = String((err && err.message) || err).slice(0, 800);
      record({
        id: "run.fatal", area: "run", status: "fail",
        description: "the run completed every check without a fatal error",
        reason: fatalError,
      });
    }
  } finally {
    await primary.context.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  // Run-scope guard: every /api/ request must have gone to the scratch
  // frontend or the scratch backend. A live/dev origin here would invalidate
  // the whole capture even if individual checks passed.
  const foreignApi = net.external.filter((e) => e.is_api);
  record({
    id: "run.no_foreign_api_origin",
    area: "run",
    description: "no /api/ request left the scratch frontend/backend origins",
    status: foreignApi.length === 0 ? "pass" : "fail",
    reason: foreignApi.length === 0 ? null
      : `${foreignApi.length} /api/ request(s) went to a non-scratch origin`,
    data: {
      allowed_origins: [FRONTEND_ORIGIN, BACKEND_ORIGIN],
      foreign_api_requests: foreignApi.slice(0, 20),
    },
  });

  const failures = checks.filter((c) => c.status === "fail");
  const missing = checks.filter((c) => c.status === "missing");
  const skipped = checks.filter((c) => c.status === "skipped");
  const passes = checks.filter((c) => c.status === "pass");
  const missingCapabilities = [...new Set(missing.map((c) => c.area))];
  // Every WA-075 check is required for the tab to be "closed". A skip is an
  // incomplete capture, not a pass: it must exit nonzero and say so.
  const incomplete = skipped.length > 0;
  const status = failures.length ? "fail"
    : (missing.length ? "missing" : (incomplete ? "incomplete" : "pass"));
  const exitCode = failures.length ? 1
    : (missing.length ? 3 : (incomplete ? 4 : 0));

  const result = {
    schema: "atom-wa075-signed-in-settings-1",
    generated_at: startedAt,
    finished_at: new Date().toISOString(),
    run_id: RUN_ID,
    frontend: FRONTEND,
    backend: BACKEND,
    role: ROLE,
    scratch_identity: identity.evidence,
    browser_launch: browserLaunch,
    sign_in: {
      email: EMAIL,
      primary: signIn,
      api_assertions: "POST /api/auth/login bearer (never written to evidence)",
      disposable_secondary: "real login form in a separate browser context",
      password_recorded: false,
    },
    disposable: {
      provider_name: DISPOSABLE_PROVIDER_NAME,
      provider_url: DISPOSABLE_PROVIDER_URL,
      provider_contact_allowed: false,
    },
    checks,
    fatal_error: fatalError,
    summary: {
      ok: status === "pass",
      status,
      completeness: status === "pass" ? "complete" : "incomplete",
      incomplete: incomplete,
      pass: passes.length,
      fail: failures.length,
      missing: missing.length,
      skipped: skipped.length,
      missing_capability_areas: missingCapabilities,
      failed_ids: failures.map((c) => c.id),
      missing_ids: missing.map((c) => c.id),
      skipped_ids: skipped.map((c) => c.id),
      required_skipped_ids: skipped.map((c) => c.id),
      incomplete_reason: incomplete
        ? "a required check was skipped; WA-075 is not complete" : null,
    },
    evidence_policy: {
      body_allowlist: [...BODY_EVIDENCE_ALLOWLIST],
      auth_response_bodies_persisted: false,
      redacted_fields: [...DROPPED_KEYS].sort(),
      secret_values_scan: "refuses to write if any registered secret appears",
    },
    network: {
      api_requests: net.entries.length,
      external_requests: net.external,
      captured_bodies: net.bodies.map((b) => ({
        method: b.method, path: b.path, status: b.status,
        body: b.body.length > 1200 ? `${b.body.slice(0, 1200)}…` : b.body,
      })),
    },
    page_errors: captured.pageErrors.slice(0, 20),
    console_errors: captured.consoleErrors.slice(0, 20),
    bad_responses: captured.badResponses.map((r) => r.replace(/[?#].*$/, "")).slice(0, 20),
    evidence,
    non_claims: [
      "no live database, live credential or external model provider was used",
      "no chat/completion, provider probe, Discover or Test call was made",
      "empty routing telemetry is reported as empty, never seeded",
      "the Sessions result reflects this build; a missing row is reported, not patched",
    ],
  };

  // Persist only allowlisted, redacted evidence. A registered secret value in
  // the serialized document aborts the write instead of leaking it.
  const safeResult = sanitizeEvidence(result);
  const serialized = `${JSON.stringify(safeResult, null, 2)}\n`;
  const leaked = [...SECRET_VALUES].filter((secret) => serialized.includes(secret));
  if (leaked.length > 0) {
    console.error(
      `refusing to write evidence: ${leaked.length} registered secret value(s) `
      + "would have been persisted");
    process.exit(2);
  }
  if (OUT) {
    fs.mkdirSync(path.dirname(OUT), { recursive: true });
    fs.writeFileSync(OUT, serialized);
  }
  console.log(JSON.stringify({
    ok: safeResult.summary.ok,
    status: safeResult.summary.status,
    summary: safeResult.summary,
    checks: checks.map((c) => `${c.status} ${c.id}`),
    missing_capabilities: missing.map((c) => ({ id: c.id, reason: c.reason })),
    failures: failures.map((c) => ({ id: c.id, reason: c.reason })),
    network: { api_requests: net.entries.length, external: net.external.length },
    out: OUT,
  }, null, 2));

  if (fatalError) process.exit(2);
  process.exit(exitCode);
})().catch((err) => {
  console.error(err);
  process.exit(2);
});
