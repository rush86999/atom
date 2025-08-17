import { test, expect } from '@playwright/test';
import { getPersona } from '../core/personas';
import { TestConfig } from '../core/test-config';

const maria = getPersona('maria');
let config: TestConfig;

test.beforeEach(async ({ page }) => {
  config = new TestConfig();
  await page.goto(config.baseUrl);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
});

test.describe('Maria Garcia - Work-Life Balance Journey', () => {
  test('Maria completes onboarding for busy parent', async ({ page }) => {
    await page.goto(`${config.baseUrl}/signup`);

    await page.fill('[data-testid="email-input"]', maria.email);
    await page.fill('[data-testid="name-input"]', maria.name);
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="submit-register"]');

    await page.click('[data-testid="persona-parent"]');
    await page.fill('[data-testid="family-size"]', '4');
    await page.click('[data-testid="complete-onboarding"]');

    await expect(page).toHaveURL(`${config.baseUrl}/dashboard`);
    await expect(page.locator('h1')).toContainText('Welcome, Maria!');
  });

  test('Maria sets up family calendar integration', async ({ page }) => {
    await page.goto(`${config.baseUrl}`);
    await page.fill('[data-testid="email-input"]', maria.email);
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');
+    await page.waitForURL(`${config.baseUrl}/dashboard`);

    await page.click('[data-testid="nav-integrations"]');
    await page.click('[data-testid="integrate-google-calendar"]');

    await expect(page.locator('[data-testid="calendar-synced"]')).toBeVisible();
  });

  test('Maria creates work-life balance workflow', async ({ page }) => {
    await page.goto(`${config.baseUrl}/login`);
    await page.fill('[data-testid="email-input"]', maria.email);
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');
+    await page.waitForURL(`${config.baseUrl}/dashboard`);

    await page.click('[data-testid="nav-workflows"]');
    await page.click('[data-testid="create-balance-workflow"]');

    await page.fill('[data-testid="workflow-prompt"]', 'Notify me 30 minutes before school pickup');
    await page.click('[data-testid="create-workflow-ai"]');

    await expect(page.locator('[data-testid="workflow-created"]')).toBeVisible();
  });

  test('Maria views family dashboard', async ({ page }) => {
    await page.goto(`${config.baseUrl}/login`);
    await page.fill('[data-testid="email-input"]', maria.email);
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');
+    await page.waitForURL(`${config.baseUrl}/dashboard`);

    await expect(page.locator('[data-testid="family-calendar"]')).toBeVisible();
    await expect(page.locator('[data-testid="work-life-balance-score"]')).toBeVisible();
  });
});
