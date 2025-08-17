import { test, expect, _electron as electron } from '@playwright/test';

test.describe('Maria - Desktop Financial Optimizer', () => {
  let electronApp: any;
  let window: any;

  test.beforeAll(async () => {
    electronApp = await electron.launch({
      args: ['./desktop-app'],
      cwd: './atomic-desktop'
    });
    window = await electronApp.firstWindow();
  });

  test.afterAll(async () => {
    await electronApp.close();
  });

  test('Maria completes desktop financial onboarding', async () => {
    await window.click('[data-testid="persona-maria-financial"]');
    await window.fill('[data-testid="profile-name"]', 'Maria Rodriguez');
    await window.selectOption('[data-testid="financial-goals"]', 'budget_optimization');
    await window.fill('[data-testid="monthly-income"]', '8500');
    await window.click('[data-testid="complete-financial-setup"]');

    await window.waitForSelector('[data-testid="maria-dashboard-desktop"]');
  });

  test('Maria configures desktop financial dashboard', async () => {
    await window.click('[data-testid="configure-dashboard"]');

    // Add budget widget
    await window.click('[data-testid="add-widget']');
    await window.click('[data-testid="widget-budget']');
    await window.fill('[data-testid="widget-name']', 'Monthly Budget Tracker');
    await window.selectOption('[data-testid="budget-period"]', 'monthly');
    await window.click('[data-testid="save-widget"]');

    await window.waitForSelector('[data-testid="budget-widget-active"]');
  });

  test('Maria connects financial accounts', async () => {
    await window.click('[data-testid="accounts-center"]');
    await window.click('[data-testid="add-account-plaid"]');

    // Mock Plaid connection
    await window.click('[data-testid="connect-chase"]');
    await window.fill('[data-testid="mock-credentials"]', 'maria@email.com');
    await window.click('[data-testid="sync-accounts"]');

    await window.waitForSelector('[data-testid="accounts-synced-desktop"]');
  });

  test('Maria sets up spending alerts', async () => {
    await window.click('[data-testid="alerts-center"]');
    await window.click('[data-testid="create-spending-alert"]');

    await window.fill('[data-testid="alert-threshold"]', '1000');
    await window.selectOption('[data-testid="alert-category"]', 'dining');
    await window.selectOption('[data-testid="alert-type"]', 'realtime');

    // Set notification preferences
    await window.check('[data-testid="desktop-notification"]');
    await window.check('[data-testid="email-notification"]');

    await window.click('[data-testid="save-alert"]');
    await window.waitForSelector('[data-testid="alert-configured-desktop"]');
  });

  test('Maria creates financial goals', async () => {
    await window.click('[data-testid="goals-center"]');
    await window.click('[data-testid="new-goal"]');

    await window.fill('[data-testid="goal-name"]', 'Emergency Fund');
    await window.fill('[data-testid="goal-amount"]', '10000');
    await window.selectOption('[data-testid="goal-timeline']', '12_months');

    // Configure auto-save
    await window.check('[data-testid="auto-save-monthly"]');
    await window.fill('[data-testid="auto-save-amount"]', '500');

    await window.click('[data-testid="create-goal"]');
    await window.waitForSelector('[data-testid="goal-tracker-desktop"]');
  });

  test('Maria uses financial insights features', async () => {
    await window.click('[data-testid="insights-center"]');

    // View spending patterns
    await window.click('[data-testid="spending-insights"]');
    const insights = await window.textContent('[data-testid="monthly-spending"]');
+    expect(insights).toContain('$');
++
++    // Get personalized recommendations
++    await window.click('[data-testid="ai-recommendations"]');
++    await window.waitForSelector('[data-testid="savings-suggestions"]');
++
++    const suggestions = await window.textContent('[data-testid="savings-suggestions"]');
++    expect(suggestions).toContain('saving');
++  });
++
++  test('Maria manages bill payment workflows', async () => {
++    await window.click('[data-testid="bill-management"]');
++    await window.click('[data-testid="add-bill']');
++
++    await window.fill('[data-testid="bill-name"]', 'Rent');
++    await window.fill('[data-testid
