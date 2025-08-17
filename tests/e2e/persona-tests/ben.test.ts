import { test, expect } from '@playwright/test';
import { getPersona } from '../core/personas';
import { TestConfig } from '../core/test-config';

const ben = getPersona('ben');
let config: TestConfig;

test.beforeEach(async ({ page }) => {
  config = new TestConfig();
  await page.goto(config.baseUrl);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
});

test.describe('Ben Williams - Startup Founder Journey', () => {
  test('Ben signs up as startup founder', async ({ page }) => {
    await page.goto(`${config.baseUrl}/signup`);
+
+    await page.fill('[data-testid="email-input"]', ben.email);
+    await page.fill('[data-testid="name-input"]', ben.name);
+    await page.fill('[data-testid="password-input"]', 'TestPass123!');
+    await page.click('[data-testid="submit-register"]');
+
+    await page.click('[data-testid="persona-founder"]');
+    await page.fill('[data-testid="company-name"]', 'InnovateTech');
+    await page.click('[data-testid="complete-onboarding"]');
+
+    await expect(page).toHaveURL(`${config.baseUrl}/dashboard`);
+    await expect(page.locator('h1')).toContainText('Welcome, Ben!');
+  });
+
+  test('Ben sets up team collaboration tools', async ({ page }) => {
+    await page.goto(`${config.baseUrl}/login`);
+    await page.fill('[data-testid="email-input"]', ben.email);
+    await page.fill('[data-testid="password-input"]', 'TestPass123!');
+    await page.click('[data-testid="login-button"]');
+    await page.waitForURL(`${config.baseUrl}/dashboard`);
+
+    await page.click('[data-testid="nav-integrations"]');
+    await page.click('[data-testid="integrate-linkedin"]');
+    await page.click('[data-testid="integrate-asana"]');
+
+    await expect(page.locator('[data-testid="integration-status"]')).toContainText('Connected');
+  });
+
+  test('Ben creates investor relationship workflow', async ({ page }) => {
+    await page.goto(`${config.baseUrl}/login`);
+    await page.fill('[data-testid="email-input"]', ben.email);
+    await page.fill('[data-testid="password-input"]', 'TestPass123!');
+    await page.click('[data-testid="login-button"]');
+    await page.waitForURL(`${config.baseUrl}/dashboard`);
+
+    await page.click('[data-testid="nav-workflows"]');
+    await page.click('[data-testid="create-investor-workflow"]');
+
+    await page.fill('[data-testid="workflow-name"]', 'Weekly investor update');
+    await page.selectOption('[data-testid="trigger-schedule"]', 'weekly');
+    await page.click('[data-testid="save-workflow"]');
+
+    await expect(page.locator('[data-testid="workflow-active"]')).toBeVisible();
+  });
+
+  test('Ben views startup dashboard analytics', async ({ page }) => {
+    await page.goto(`${config.baseUrl}/login`);
+    await page.fill('[data-testid="email-input"]', ben.email);
+    await page.fill('[data-testid="password-input"]', 'TestPass123!');
+    await page.click('[data-testid="login-button"]');
+    await page.waitForURL(`${config.baseUrl}/dashboard`);
+
+    await expect(page.locator('[data-testid="mrr-metric"]')).toBeVisible();
+    await expect(page.locator('[data-testid="team-productivity']')).toBeVisible();
+    await expect(page.locator('[data-testid="investor-pipeline"]')).toBeVisible();
+  });
+});
