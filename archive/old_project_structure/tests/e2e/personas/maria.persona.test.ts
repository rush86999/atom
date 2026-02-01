import { test, expect, Page } from '@playwright/test';

test.describe('Maria Rodriguez - Financial Optimizer Test Suite', () => {
  let page: Page;

  test.beforeEach(async ({ page: newPage }) => {
    page = newPage;
    // Assuming Maria is already registered or we use a fresh session
    // For E2E, usually we might seed data or login.
    // Following Alex's pattern, we'll assume the app is running.
    await page.goto('http://localhost:3000');
  });

  test('Maria completes financial onboarding', async () => {
    await page.goto('http://localhost:3000/signup');
    await page.fill('[data-testid="email-input"]', 'maria.finance@example.com');
    await page.fill('[data-testid="name-input"]', 'Maria Rodriguez');
    await page.fill('[data-testid="password-input"]', 'SecurePass123!');
    await page.click('[data-testid="submit-register"]');

    await page.click('[data-testid="persona-maria"]');
    await page.fill('[data-testid="financial-goals"]', 'Save for house, Optimize spending');
    await page.click('[data-testid="complete-onboarding"]');

    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('h1')).toContainText(/Welcome, Maria!/);
  });

  test('Maria connects bank accounts', async () => {
    await page.goto('http://localhost:3000/finance/settings');
    await page.click('[data-testid="connect-bank"]');

    // Mock Plaid or similar integration flow
    await page.click('[data-testid="bank-mock-provider"]');
    await page.click('[data-testid="confirm-connection"]');

    await expect(page.locator('[data-testid="connection-success"]')).toBeVisible();
    await expect(page.locator('[data-testid="account-list"]')).toContainText('Checking Account');
  });

  test('Maria sets up budget tracking', async () => {
    await page.goto('http://localhost:3000/finance/budget');
    await page.click('[data-testid="create-budget"]');

    await page.fill('[data-testid="budget-name"]', 'Monthly Groceries');
    await page.fill('[data-testid="budget-amount"]', '500');
    await page.selectOption('[data-testid="category-select"]', 'groceries');
    await page.click('[data-testid="save-budget"]');

    await expect(page.locator('[data-testid="budget-card-groceries"]')).toBeVisible();
    await expect(page.locator('[data-testid="budget-amount-display"]')).toContainText('$500');
  });

  test('Maria analyzes expenses with AI', async () => {
    await page.goto('http://localhost:3000/finance/insights');
    await page.click('[data-testid="analyze-spending"]');

    // Wait for AI analysis
    await expect(page.locator('[data-testid="ai-analysis-loading"]')).toBeVisible();
    await expect(page.locator('[data-testid="ai-analysis-result"]')).toBeVisible({ timeout: 10000 });

    await expect(page.locator('[data-testid="spending-breakdown"]')).toBeVisible();
    await expect(page.locator('[data-testid="savings-opportunity"]')).toBeVisible();
  });

  test('Maria sets up spending alerts', async () => {
    await page.goto('http://localhost:3000/finance/alerts');
    await page.click('[data-testid="new-alert"]');

    await page.selectOption('[data-testid="alert-trigger"]', 'over_budget');
    await page.fill('[data-testid="threshold-amount"]', '50'); // 50% or $50
    await page.click('[data-testid="save-alert"]');

    await expect(page.locator('[data-testid="active-alerts-list"]')).toContainText('Over Budget Alert');
  });

  test('Maria creates a savings goal', async () => {
    await page.goto('http://localhost:3000/finance/goals');
    await page.click('[data-testid="create-goal"]');

    await page.fill('[data-testid="goal-name"]', 'Emergency Fund');
    await page.fill('[data-testid="target-amount"]', '10000');
    await page.fill('[data-testid="target-date"]', '2024-12-31');
    await page.click('[data-testid="create-goal-btn"]');

    await expect(page.locator('[data-testid="goal-card-emergency-fund"]')).toBeVisible();
  });

  test('Maria schedules bill payment reminders', async () => {
    await page.goto('http://localhost:3000/finance/bills');
    await page.click('[data-testid="add-bill"]');

    await page.fill('[data-testid="bill-name"]', 'Electricity');
    await page.fill('[data-testid="bill-amount"]', '120');
    await page.fill('[data-testid="due-date"]', '2023-11-15');
    await page.tick('[data-testid="set-reminder"]');
    await page.click('[data-testid="save-bill"]');

    await expect(page.locator('[data-testid="bill-list"]')).toContainText('Electricity');
    await expect(page.locator('[data-testid="reminder-badge"]')).toBeVisible();
  });

  test('Maria exports financial report', async () => {
    await page.goto('http://localhost:3000/finance/reports');
    await page.click('[data-testid="generate-report"]');
    await page.click('[data-testid="download-pdf"]');

    // verifying download triggers is tricky, usually we check if the button works or notification appears
    await expect(page.locator('[data-testid="download-success"]')).toBeVisible();
  });
});
