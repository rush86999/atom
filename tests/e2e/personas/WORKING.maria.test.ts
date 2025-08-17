import { test, expect, Page } from '@playwright/test';

test.describe('Maria Rodriguez - Working Financial Optimizer Test Suite', () => {
  let page: Page;

  test.beforeEach(async ({ page: newPage }) => {
    page = newPage;
    await page.goto('http://localhost:3000');
  });

  test('Maria completes financial onboarding', async () => {
    await page.goto('http://localhost:3000/signup');

    await page.fill('[data-testid="email-input"]', 'maria.test@example.com');
    await page.fill('[data-testid="name-input"]', 'Maria Rodriguez');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="submit-register"]');

    await page.click('[data-testid="persona-maria"]');
    await page.fill('[data-testid="monthly-income"]', '7500');
    await page.fill('[data-testid="budget-goal"]', 'Save for emergency fund');
    await page.click('[data-testid="complete-onboarding"]');

    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('[data-testid="budget-overview"]')).toBeVisible();
  });

  test('Maria connects financial account', async () => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[data-testid="email-input"]', 'maria.test@example.com');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');

    await page.waitForURL(/dashboard/);

    await page.click('[data-testid="nav-integrations"]');
    await page.click('[data-testid="connect-bank"]');
    await page.click('[data-testid="mock-plaid-connect"]');

    await expect(page.locator('[data-testid="accounts-synced"]')).toContainText('Account connected');
  });

  test('Maria sets up spending tracking', async () => {
    await page.goto('http://localhost:3000/budget');
    await page.click('[data-testid="create-budget"]');

    await page.fill('[data-testid="budget-name"]', 'Monthly Essentials');
    await page.fill('[data-testid="budget-amount"]', '4000');
    await page.selectOption('[data-testid="budget-category"]', 'essentials');
    await page.click('[data-testid="create-budget"]');

    await expect(page.locator('[data-testid="budget-created"]')).toContainText('Budget created');
  });

  test('Maria creates emergency fund goal', async () => {
    await page.goto('http://localhost:3000/goals');
    await page.click('[data-testid="new-goal"]');

    await page.fill('[data-testid="goal-name"]', 'Emergency Fund');
    await page.fill('[data-testid="goal-amount"]', '15000');
    await page.selectOption('[data-testid="goal-timeline']', '12');
    await page.click('[data-testid="create-goal"]');

    await expect(page.locator('[data-testid="goal-tracker"]')).toContainText('$15,000 goal');
  });

  test('Maria tracks monthly expenses', async () => {
    await page.goto('http://localhost:3000/expenses');

    await page.click('[data-testid="add-expense"]');
    await page.fill('[data-testid="expense-description"]', 'Grocery shopping');
    await page.fill('[data-testid="expense-amount"]', '125.50');
    await page.selectOption('[data-testid="expense-category"]', 'groceries');
    await page.click('[data-testid="save-expense"]');

    await expect(page.locator('[data-testid="expense-list"]')).toContainText('Grocery shopping');
  });

  test('Maria sets up bill payment reminders', async () => {
    await page.goto('http://localhost:3000/alerts');
    await page.click('[data-testid="create-alert"]');

    await page.fill('[data-testid="alert-name"]', 'Credit Card Due');
    await page.fill('[data-testid="alert-amount"]', '500');
    await page.fill('[data-testid="alert-date"]', '15');
    await page.click('[data-testid="save-alert"]');

    await expect(page.locator('[data-testid="alert-configured"]')).toBeVisible();
  });
});
