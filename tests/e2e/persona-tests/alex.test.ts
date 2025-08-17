import { test, expect } from '@playwright/test';
import { getPersona } from '../core/personas';
import { TestConfig } from '../core/test-config';

const alex = getPersona('alex');
let config: TestConfig;

test.beforeEach(async ({ page }) => {
  config = new TestConfig();
  await page.goto(config.baseUrl);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
});

test.describe('Alex Chen - Growth Professional Journey', () => {
  test('Alex completes onboarding flow', async ({ page }) => {
    await page.goto(`${config.baseUrl}/signup`);

    // Registration
    await page.fill('[data-testid="email-input"]', alex.email);
    await page.fill('[data-testid="name-input"]', alex.name);
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="submit-register"]');
+
    // Onboarding
    await page.click('[data-testid="persona-growth"]');
    await page.fill('[data-testid="job-title"]', 'Product Manager');
+    await page.click('[data-testid="complete-onboarding"]');

    // Verify dashboard
    await expect(page).toHaveURL(`${config.baseUrl}/dashboard`);
    await expect(page.locator('h1')).toContainText('Welcome, Alex!');
  });

  test('Alex creates automation workflow', async ({ page }) => {
    await page.goto(`${config.baseUrl}`);
    await page.fill('[data-testid="email-input"]', alex.email);
    await page.fill('[data-testid="password-input"]`, 'TestPass123!');
    await page.click('[data-testid="login-button"]');
    await page.waitForURL(`${config.baseUrl}/dashboard`);

    // Navigate to workflows
    await page.click('[data-testid="nav-workflows"]');
    await page.click('[data-testid="create-workflow"]');

    // Create workflow
    await page.fill('[data-testid="workflow-name"]', 'Daily standup automation');
    await page.selectOption('[data-testid="trigger-type"]', 'schedule');
    await page.click('[data-testid="save-workflow"]');

    // Verify success
    await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
  });

  test('Alex views productivity dashboard', async ({ page }) => {
    await page.goto(`${config.baseUrl}/login`);
    await page.fill('[data-testid="email-input"]', alex.email);
    await page.fill('[data-testid="password-input"]`, 'TestPass123!');
    await page.click('[data-testid="login-button"]');
    await page.waitForURL(`${config.baseUrl}/dashboard`);

    // Check productivity metrics
    await expect(page.locator('[data-testid="productivity-score"]')).toBeVisible();
    await expect(page.locator('[data-testid="weekly-insights"]')).toBeVisible();

    // Test AI suggestions
    await page.click('[data-testid="get-ai-insights"]');
    await expect(page.locator('[data-testid="ai-suggestions"]')).toBeVisible();
  });
});
