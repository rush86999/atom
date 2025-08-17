import { test, expect, Page } from '@playwright/test';

test.describe('Ben Carter - Working Solopreneur Test Suite', () => {
  let page: Page;

  test.beforeEach(async ({ page: newPage }) => {
    page = newPage;
    await page.goto('http://localhost:3000');
  });

  test('Ben completes startup onboarding', async () => {
    await page.goto('http://localhost:3000/signup');

    await page.fill('[data-testid="email-input"]', 'ben.test@example.com');
    await page.fill('[data-testid="name-input"]', 'Ben Carter');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="submit-register"]');

    await page.click('[data-testid="persona-ben"]');
    await page.fill('[data-testid="business-name"]', 'InnovateTech');
    await page.selectOption('[data-testid="business-type"]', 'SaaS');
    await page.click('[data-testid="complete-onboarding"]');

    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('[data-testid="startup-dashboard"]')).toBeVisible();
  });

  test('Ben creates competitor analysis', async () => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[data-testid="email-input"]', 'ben.test@example.com');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');

    await page.waitForURL(/dashboard/);
    await page.click('[data-testid="nav-research"]');
    await page.click('[data-testid="competitor-analysis"]');

    await page.fill('[data-testid="analysis-prompt"]', 'Analyze Shopify competitors');
    await page.click('[data-testid="start-analysis"]');

    await page.waitForSelector('[data-testid="analysis-results"]');
    await expect(page.locator('[data-testid="competitors-list"]')).toBeVisible();
  });

  test('Ben schedules social media content', async () => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[data-testid="email-input"]', 'ben.test@example.com');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');

    await page.waitForURL(/dashboard/);
    await page.click('[data-testid="nav-social"]');
    await page.click('[data-testid="schedule-content"]');

    await page.fill('[data-testid="content-prompt"]', 'Create LinkedIn posts about our new feature');
    await page.selectOption('[data-testid="platform-select"]', 'linkedin');
    await page.click('[data-testid="generate-content"]');

    await expect(page.locator('[data-testid="content-scheduled"]')).toBeVisible();
  });

  test('Ben creates customer support workflow', async () => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[data-testid="email-input"]', 'ben.test@example.com');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');

    await page.waitForURL(/dashboard/);
    await page.click('[data-testid="nav-workflows"]');
    await page.click('[data-testid="create-workflow"]');

    await page.fill('[data-testid="workflow-name"]', 'Support Request Handler');
    await page.selectOption('[data-testid="trigger-type"]', 'email');
    await page.fill('[data-testid="trigger-condition"]', 'Support');
    await page.click('[data-testid="save-workflow"]');

    await expect(page.locator('[data-testid="workflow-active"]')).toBeVisible();
  });

  test('Ben manages investor relationships', async () => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[data-testid="email-input"]', 'ben.test@example.com');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');

    await page.waitForURL(/dashboard/);
    await page.click('[data-testid="nav-investors"]');
    await page.click('[data-testid="add-investor-contact"]');

    await page.fill('[data-testid="investor-name"]', 'Tech Ventures Inc');
    await page.fill('[data-testid="investor-email"]', 'investor@techventures.com');
    await page.selectOption('[data-testid="investor-stage"]', 'seed');
    await page.click('[data-testid="add
