const { test, expect } = require('@playwright/test');

test.describe('Atom E2E Core User Journey Tests', () => {

  test('User can successfully navigate signup flow', async ({ page }) => {
    // Mock API responses for reliable testing
    await page.route('**/api/**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true })
      });
    });

    // Test Alex - Growth Professional
    await test.step('Alex completes signup journey', async () => {
      await page.goto('http://localhost:3000/signup');

      await page.fill('[data-testid="email-input"]', 'alex@test.com');
      await page.fill('[data-testid="name-input"]', 'Alex Chen');
      await page.fill('[data-testid="password-input"]', 'Test123!');
      await page.click('[data-testid="submit-register"]');

      await page.click('[data-testid="persona-alex"]');
      await page.fill('[data-testid="job-title"]', 'Product Manager');
      await page.click('[data-testid="complete-onboarding"]');

      await expect(page).toHaveURL(/dashboard/);
      await expect(page.locator('body')).toContainText('Welcome!');
    });

    // Test Alex login and core feature
    await test.step('Alex creates productivity workflow', async () => {
      await page.goto('http://localhost:3000/login');
      await page.fill('[data-testid="email-input"]', 'alex@test.com');
      await page.fill('[data-testid="password-input"]', 'Test123!');
      await page.click('[data-testid="login-button"]');

      await page.click('[data-testid="nav-workflows"]');
      await page.fill('[data-testid="workflow-name"]', 'Daily Tasks');
      await page.click('[data-testid="save-workflow"]');

      await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
    });

    // Test Maria - Financial Optimizer
    await test.step('Maria completes signup journey', async () => {
      await page.goto('http://localhost:3000/signup');

      await page.fill('[data-testid="email-input"]', 'maria@test.com');
      await page.fill('[data-testid="name-input"]', 'Maria Rodriguez');
      await page.fill('[data-testid="password-input"]', 'Test123!');
      await page.click('[data-testid="submit-register"]');

      await page.click('[data-testid="persona-maria"]');
      await page.fill('[data-testid="monthly-income"]', '8000');
      await page.click('[data-testid="complete-onboarding"]');

      await expect(page).toHaveURL(/dashboard/);
    });

    // Test Maria creates budget tracker
    await test.step('Maria creates budget workflow', async () => {
      await page.goto('http://localhost:3000/login');
      await page.fill('[data-testid="email-input"]', 'maria@test.com');
      await page.fill('[data-testid="password-input"]', 'Test123!');
      await page.click('[data-testid="login-button"]');

      await page.click('[data-testid="nav-budgets"]');
      await page.fill('[data-testid="budget-name"]', 'Monthly Expenses');
      await page.click('[data-testid="save-budget"]');

      await expect(page.locator('[data-testid="budget-created"]')).toBeVisible();
    });

    // Test Ben - Solopreneur
    await test.step('Ben completes signup journey', async () => {
      await page.goto('http://localhost:3000/signup');

      await page.fill('[data-testid="email-input"]', 'ben@test.com');
      await page.fill('[data-testid="name-input"]', 'Ben Carter');
      await page.fill('[data-testid="password-input"]', 'Test123!');
      await page.click('[data-testid="submit-register"]');

      await page.click('[data-testid="persona-ben"]');
      await page.fill('[data-testid="business-name"]', 'TechStartup');
      await page.click('[data-testid="complete-onboarding"]');

      await expect(page).toHaveURL(/dashboard/);
    });

    // Test Ben creates business workflow
    await test.step('Ben creates business automation', async () => {
      await page.goto('http://localhost:3000/login');
      await page.fill('[data-testid="email-input"]', 'ben@test.com');
      await page.fill('[data-testid="password-input"]', 'Test123!');
      await page.click('[data-testid="login-button"]');

      await page.click('[data-testid="nav-automation"]');
      await page.fill
