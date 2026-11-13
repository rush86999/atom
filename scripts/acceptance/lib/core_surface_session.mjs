/**
 * Shared signed-in browser primitives for the core-surface acceptance scripts.
 *
 * Extracted verbatim from `scripts/acceptance/browser_core_surface.mjs` so the
 * WA-075 settings acceptance can reuse the same world contract instead of
 * inventing a second one:
 *
 *   - the isolated world is addressed by `ATOM_FRONTEND_URL` /
 *     `ATOM_BACKEND_URL` (defaults 127.0.0.1:3001 / :8105);
 *   - the sign-in credential is the scratch world's admin password, never a
 *     live credential;
 *   - the browser is the installed Google Chrome via Playwright, imported from
 *     the workspace's own `frontend-nextjs/node_modules` (no install).
 *
 * Behaviour is unchanged for the original caller: same login endpoint, same
 * cookie/localStorage contract, same error collection, same frontend-wait
 * retry loop.
 */

/**
 * Mint a backend bearer from the scratch world's login route.
 *
 * The world is expected to run with a known scratch `ADMIN_PASSWORD` (see
 * `scripts/acceptance/scratch_admin_password.py`). The password is never
 * printed, logged or written to evidence.
 */
export async function loginToken({ backend, email, password }) {
  if (!password) {
    throw new Error("set ATOM_SCOPE_PASSWORD for the isolated world");
  }
  const res = await fetch(`${backend}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: email, password }),
  });
  if (!res.ok) {
    throw new Error(`login failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  const token = data.access_token || data.token;
  if (!token) throw new Error("login returned no token");
  return token;
}

/** Wait until the (possibly restarting) Next dev server answers /login. */
export async function waitForFrontend(frontend, attempts = 40, delayMs = 1000) {
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(`${frontend}/login`);
      if (res.ok) return true;
    } catch {
      /* dev server restarting */
    }
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return false;
}

/**
 * Collect page errors, console errors and >=500 responses.
 *
 * Only statuses/URLs are retained; response bodies, headers and credentials
 * are never captured here.
 */
export function collectErrors(page) {
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
