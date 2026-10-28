#!/usr/bin/env node
/**
 * Core-release browser breadth check.
 *
 * Uses the isolated whole-app world only:
 *   frontend http://127.0.0.1:3001
 *   backend  http://127.0.0.1:8105
 *
 * It proves the one surface configuration is what the browser actually sees:
 * the core sidebar renders, every core route loads without a page error, and
 * every deferred route renders the explicit scope page on direct access.
 *
 * Usage:
 *   node scripts/acceptance/browser_core_surface.mjs \
 *     --out docs/acceptance/evidence/.../browser-core-surface.json
 */
import { chromium } from "../../frontend-nextjs/node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";

const FRONTEND = process.env.ATOM_FRONTEND_URL || "http://127.0.0.1:3001";
const BACKEND = process.env.ATOM_BACKEND_URL || "http://127.0.0.1:8105";
const EMAIL = process.env.ATOM_SCOPE_EMAIL || "admin@example.com";
const PASSWORD = process.env.ATOM_SCOPE_PASSWORD;
const ROLE = process.env.ATOM_SCOPE_ROLE || "admin";

const CORE_ROUTES = [
  "/dashboard",
  "/chat",
  "/documents",
  "/canvas",
  "/agents",
  "/goal-runs",
  "/execution-history",
  "/settings",
  "/settings/ai",
  "/settings/account",
  "/settings/sessions",
  "/settings/routing",
  "/settings/local-models",
];

const DEFERRED_ROUTES = [
  "/search",
  "/tasks",
  "/boards",
  "/automations",
  "/workflows/builder",
  "/workflows/schedule",
  "/marketplace",
  "/dashboards/projects",
  "/communication",
  "/sales",
  "/marketing",
  "/finance",
  "/analytics",
  "/calendar",
  "/health",
  "/voice",
  "/admin/users",
  "/admin/settings",
  "/audit-trail",
  "/dev-studio",
  "/integrations",
  "/team-chat",
  "/system-status",
];

const args = process.argv.slice(2);
const outIdx = args.indexOf("--out");
const outPath = outIdx >= 0 ? args[outIdx + 1] : null;

async function loginToken() {
  if (!PASSWORD) throw new Error("set ATOM_SCOPE_PASSWORD for the isolated world");
  const res = await fetch(`${BACKEND}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: EMAIL, password: PASSWORD }),
  });
  if (!res.ok) throw new Error(`login failed: ${res.status} ${await res.text()}`);
  const data = await res.json();
  const token = data.access_token || data.token;
  if (!token) throw new Error("login returned no token");
  return token;
}

function collect(page) {
  const pageErrors = [];
  const consoleErrors = [];
  const badResponses = [];
  page.on("pageerror", (err) => pageErrors.push(String(err).slice(0, 300)));
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 300));
  });
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/_next/") || url.includes("hot-update")) return;
    if (res.status() >= 500) badResponses.push(`${res.status()} ${url}`);
  });
  return { pageErrors, consoleErrors, badResponses };
}

async function waitForFrontend() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`${FRONTEND}/login`);
      if (res.ok) return true;
    } catch { /* dev server restarting */ }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

async function visit(page, route, timeout = 45000) {
  const started = Date.now();
  let rec = null;
  let lastErr = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      rec = await page.goto(`${FRONTEND}${route}`, {
        waitUntil: "domcontentloaded",
        timeout,
      });
      lastErr = null;
      break;
    } catch (err) {
      lastErr = err;
      // Next dev restarts itself near its memory threshold. Wait for the
      // server to come back and retry the same route.
      await waitForFrontend();
      await page.waitForTimeout(1500);
    }
  }
  if (lastErr && !rec) throw lastErr;
  // Wait for the surface check to resolve (profile fetch) before reading the
  // body; otherwise a fast deferred page can be sampled mid-load.
  for (let i = 0; i < 20; i++) {
    const state = await page.evaluate(() => window.__atomSurface).catch(() => null);
    if (state && state.loading === false) break;
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(300);
  const text = await page.locator("body").innerText().catch(() => "");
  return {
    route,
    finalUrl: new URL(page.url()).pathname,
    status: rec ? rec.status() : null,
    ms: Date.now() - started,
    textSample: text.slice(0, 400),
    notInRelease: /not part of this release/i.test(text),
  };
}

(async () => {
  const token = await loginToken();
  const browser = await chromium.launch({ headless: true, channel: "chrome" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  await context.addCookies([
    { name: "auth_token", value: token, url: FRONTEND, sameSite: "Lax" },
  ]);
  await context.addInitScript((t) => {
    try {
      localStorage.setItem("auth_token", t);
      localStorage.setItem("token", t);
      localStorage.setItem("user_email", "admin@example.com");
    } catch { /* ignore */ }
  }, token);
  const page = await context.newPage();
  const captured = collect(page);

  const profileRes = await page.request.get(`${BACKEND}/api/product/profile`);
  const profile = await profileRes.json();

  const core = [];
  for (const route of CORE_ROUTES) {
    core.push(await visit(page, route));
  }

  const navLabels = await page
    .locator("nav[aria-label='Main Navigation'] a")
    .allInnerTexts()
    .catch(() => []);

  const deferred = [];
  for (const route of DEFERRED_ROUTES) {
    deferred.push(await visit(page, route, 30000));
  }

  const result = {
    generatedAt: new Date().toISOString(),
    frontend: FRONTEND,
    backend: BACKEND,
    profile: {
      profile: profile.profile,
      enabled: profile.enabled_capabilities,
      deferred: profile.deferred_capabilities,
    },
    role: ROLE,
    navLabels,
    core,
    deferred,
    errors: captured,
  };

  const failures = [];
  for (const r of core) {
    if (r.notInRelease) failures.push(`${r.route}: core route showed the scope page`);
    if (r.status !== 200) failures.push(`${r.route}: HTTP ${r.status}`);
  }
  for (const r of deferred) {
    if (!r.notInRelease) failures.push(`${r.route}: deferred route rendered`);
  }
  for (const label of ["Chat", "Data", "Workspace", "Agents", "Activity", "Settings"]) {
    if (!navLabels.includes(label)) failures.push(`sidebar missing ${label}`);
  }
  if (ROLE === "member" && navLabels.some((l) => l.startsWith("Approvals"))) {
    failures.push("member sidebar exposes Approvals");
  }
  if (ROLE === "member") {
    const approvals = await visit(page, "/approvals", 30000);
    if (!/Supervisor access required/i.test(approvals.textSample)) {
      failures.push("/approvals: member did not get a clean denied state");
    }
  }
  for (const label of ["Automations", "Marketplace", "Tasks", "Kanban", "Integrations"]) {
    if (navLabels.includes(label)) failures.push(`sidebar still exposes ${label}`);
  }
  result.roleChecks = {
    role: ROLE,
    approvalsHidden: !navLabels.some((l) => l.startsWith("Approvals")),
  };
  result.failures = failures;
  result.ok = failures.length === 0;

  if (outPath) {
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
  }
  console.log(JSON.stringify({
    ok: result.ok,
    profile: result.profile.profile,
    navLabels,
    core: core.map((r) => `${r.route} ${r.status} ${r.notInRelease ? "SCOPE" : "ok"}`),
    deferred: deferred.map((r) => `${r.route} ${r.status} ${r.notInRelease ? "scope" : "RENDERED"}`),
    failures,
    pageErrors: captured.pageErrors.slice(0, 5),
    badResponses: captured.badResponses.slice(0, 10),
  }, null, 2));

  await browser.close();
  process.exit(result.ok ? 0 : 1);
})().catch((err) => {
  console.error(err);
  process.exit(2);
});
