import { test, expect } from '@playwright/test';

const personas = {
  alex: {
    email: 'alex@test.com',
    name: 'Alex Chen',
    password: 'Test123!',
    jobTitle: 'Product Manager'
  },
  maria: {
    email: 'maria@test.com',
    name: 'Maria Rodriguez',
    password: 'Test123!',
    income: '7500'
  },
  ben: {
    email: 'ben@test.com',
    name: 'Ben Carter',
    password: 'Test123!',
    businessName: 'TechStartup'
  }
};

test.describe('Atom Personas - Core User Journey Tests', () => {

  test.beforeEach(async ({ page }) => {
    // Mock all external APIs for reliable testing
    await page.route('**/api/**', (route) => {
      route.fulfill({ status: 200, body: JSON.stringify({ success: true }) });
    });
  });

  Object.entries(personas).forEach(([personaName, persona]) => {

    test(`Complete ${personaName.toUpperCase()} Journey - Signup to Dashboard`, async ({ page }) => {
      console.log(`Testing complete signup and onboarding for ${persona.name}`);

      // Step 1: Navigate to signup
      await page.goto('http://localhost:3000/signup');

      // Step 2: Fill registration form
      await page.fill('[data-testid="email-input"]', persona.email);
      await page.fill('[data-testid="name-input"]', persona.name);
      await page.fill('[data-testid="password-input"]', persona.password);
      await page.fill('[data-testid="confirm-password-input"]', persona.password);

      // Step 3: Select persona type
      await page.click(`[data-testid="persona-${personaName}"]`);

      // Step 4: Complete persona-specific onboarding
      if (personaName === 'alex') {
        await page.fill('[data-testid="job-title"]', persona.jobTitle);
        await page.fill('[data-testid="company-size"]', 'medium');
      } else if (personaName === 'maria') {
        await page.fill('[data-testid="monthly-income"]', persona.income);
        await page.selectOption('[data-testid="primary-goal"]', 'save-for-emergency');
      } else if (personaName === 'ben') {
        await page.fill('[data-testid="business-name"]', persona.businessName);
        await page.selectOption('[data-testid="business-type"]', 'saas');
      }

      // Step 5: Complete registration
      await page.click('[data-testid="complete-signup"]');

      // Step 6: Verify successful onboarding
      await expect(page).toHaveURL(/dashboard/);
      await expect(page.locator('[data-testid="welcome-message"]')).toContainText(`Welcome, ${persona.name}!`);

      // Step 7: Navigate to core feature
      await page.click('[data-testid="nav-workflows"]');
      await page.click('[data-testid="create-first-workflow"]');

      // Step 8: Verify workflow creation available
      await expect(page.locator('[data-testid="workflow-creator"]')).toBeVisible();
    });

    test(`Complete ${personaName.toUpperCase()} Journey - Login and Core Feature`, async ({ page }) => {
      console.log(`Testing login and core features for ${persona.name}`);

      // Step 1: Login
      await page.goto('http://localhost:3000/login');
      await page.fill('[data-testid="email-input"]', persona.email);
      await page.fill('[data-testid="password-input"]', persona.password);
      await page.click('[data-testid="login-button"]');

      // Step 2: Wait for dashboard
      await page.waitForURL(/dashboard/);

      // Step 3: Navigate to persona-specific section
      if (personaName === 'alex') {
        await page.click('[data-testid="productivity-section"]');
        await page.click('[data-testid="create-productivity-workflow"]');
        await page.fill('[data-testid="workflow-name"]', 'Daily Standup Automation');
        await page.click('[data-testid="save-workflow"]');
        await expect(page.locator('[data-testid="workflow-saved"]')).toContainText('Productivity workflow created');

      } else if (personaName === 'maria') {
        await page.click('[data-testid="budget-section"]');
        await page.click('[data-testid="create-budget-tracker"]');
        await page.fill('[data-testid="budget-name"]', 'Monthly Budget');
        await page.fill('[data-testid="budget-amount"]', '3000');
        await page.click('[data-test
