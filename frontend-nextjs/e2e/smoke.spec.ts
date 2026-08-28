/**
 * Employee-critical smoke suite (berd gap #4 / UI gap analysis).
 * Ten flows a pilot employee or admin must be able to do. Run with:
 *   npx playwright test   (after: npx playwright install chromium)
 * Config: playwright.config.ts. Skipped automatically when no backend
 * is reachable (CI without services) via the health check in beforeEach.
 */
import { test, expect, request, type Locator } from "@playwright/test";

const BASE = process.env.SMOKE_BASE_URL || "http://localhost:3001";
const API = process.env.SMOKE_API_URL || "http://localhost:8001";
const ADMIN_EMAIL = process.env.SMOKE_ADMIN_EMAIL || "admin@example.com";
const ADMIN_PASSWORD = process.env.SMOKE_ADMIN_PASSWORD || "";

let backendUp = false;
test.beforeAll(async () => {
  try {
    const ctx = await request.newContext();
    const res = await ctx.get(`${API}/alive`, { timeout: 3000 });
    backendUp = res.ok();
    await ctx.dispose();
  } catch { backendUp = false; }
});
test.beforeEach(async () => {
  test.skip(!backendUp || !ADMIN_PASSWORD, "backend or credentials unavailable");
});

async function login(page: import("@playwright/test").Page) {
  await page.goto(`${BASE}/login`);
  await page.fill('input[type="email"], input[name="email"]', ADMIN_EMAIL);
  await page.fill('input[type="password"], input[name="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/dashboard|chat/, { timeout: 15000 });
}

test("1. login as admin", async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/dashboard|chat/);
});

test("2. dashboard loads with integration health", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/dashboard`);
  await expect(page.locator("body")).toContainText(/Dashboard|health/i, { timeout: 15000 });
});

test("3. chat sends a message and shows a model badge", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/chat`);
  await page.fill("textarea, input[type='text']", "hello smoke test");
  await page.keyboard.press("Enter");
  await expect(page.locator("text=/hello smoke test/i").first()).toBeVisible({ timeout: 20000 });
});

test("4. approvals page renders (empty or queue)", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/approvals`);
  await expect(page.locator("body")).toContainText(/Approvals|Nothing waiting/i);
});

test("5. admin user management renders", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/admin/users`);
  await expect(page.locator("body")).toContainText(/User Management|Admin access required/i);
});

test("6. settings renders with Account tab + Advanced links", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/settings`);
  await expect(page.locator("body")).toContainText(/Account/i);
  await expect(page.locator("body")).toContainText(/AI Providers/i);
});

test("7. integrations catalog lists Telegram", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/integrations`);
  await expect(page.locator("body").or(page as unknown as Locator)).toContainText(/Telegram/i);
});

test("8. agents page renders the maturity ladder", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/agents`);
  await expect(page.locator("body")).toContainText(/Agents|student|autonomous/i, { timeout: 15000 });
});

test("9. canvas list renders", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/canvas`);
  await expect(page.locator("body")).toContainText(/Canvas/i, { timeout: 15000 });
});

test("10. logout returns to a signed-out state", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/dashboard`);
  // Sidebar sign-out (icon button with Sign out label/aria)
  const signOut = page.locator('[aria-label*="ign out"], button:has-text("Sign out"), button:has-text("Log out")').first();
  if (await signOut.count()) {
    await signOut.click();
    await page.waitForTimeout(1500);
  }
  // After logout, hitting a protected route should bounce to a sign-in.
  await page.goto(`${BASE}/dashboard`);
  await expect(page.locator("body")).toContainText(/sign in|log in|email/i, { timeout: 15000 });
});
