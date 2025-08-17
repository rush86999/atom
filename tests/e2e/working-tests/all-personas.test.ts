import { test, expect } from '@playwright/test';

const personas = {
  alex: {
    email: 'alex.core@example.com',
    name: 'Alex Chen',
    password: 'TestPass123!',
    persona: 'growth-professional'
  },
  maria: {
    email: 'maria.financial@example.com',
    name: 'Maria Rodriguez',
    password: 'TestPass123!',
    persona: 'financial-optimizer'
  },
  ben: {
    email: 'ben.business@example.com',
    name: 'Ben Carter',
    password: 'TestPass123!',
    persona: 'solopreneur'
  }
};

const mockAPI = {
  simulate: async (endpoint) => {
    return new Promise((resolve) => {
      setTimeout(resolve, 100, { success: true });
    });
  }
};

test.describe('Atom E2E - All Personas Complete Journey', () => {

  test.beforeEach(async ({ page }) => {
    // Mock services for reliable testing
    await page.route('**/api/**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: 'test-response' })
      });
    });
  });

  Object.entries(personas).forEach(([personaName, persona]) => {

    test(`Complete ${personaName.toUpperCase()} - Signup & Onboarding`, async ({ page }) => {
      console.log(`Testing ${persona.name} (${persona.persona})...`);

      // 1. Navigate to signup
      await page.goto('http://localhost:3000/signup');

      // 2. Fill registration form
      await page.fill('[data-testid="email-input"]', persona.email);
      await page.fill('[data-testid="name-input"]', persona.name);
      await page.fill('[data-testid="password-input"]', persona.password);
      await page.fill('[data-testid="confirm-password-input"]', persona.password);

      // 3. Select persona
      await page.click(`[data-testid="persona-${persona.persona}"]`);

      // 4. Complete onboarding specifics
      if (personaName === 'alex') {
        await page.fill('[data-testid="job-title"]', 'Senior Product Manager');
        await page.fill('[data-testid="company-size"]', '50-200');
      } else if (personaName === 'maria') {
        await page.fill('[data-testid="monthly-income"]', '8500');
        await page.selectOption('[data-testid="savings-goal"]', 'emergency-fund');
      } else if (personaName === 'ben') {
        await page.fill('[data-testid="business-name"]', 'InnovateTech');
        await page.selectOption('[data-testid="business-type"]', 'SaaS');
      }

      // 5. Complete signup
      await page.click('[data-testid="complete-signup"]');

      // 6. Verify successful onboarding
      await expect(page).toHaveURL(/dashboard/);
      await expect(page.locator(`[data-testid="welcome-${personaName}"]`)).toContainText(`Welcome, ${persona.name}!`);
    });

    test(`Complete ${personaName.toUpperCase()} - Core Workflow Creation`, async ({ page }) => {
      // 1. Login
      await page.goto('http://localhost:3000/login');
      await page.fill('[data-testid="email-input"]', persona.email);
      await page.fill('[data-testid="password-input"]', persona.password);
      await page.click('[data-testid="login-button"]');

      await page.waitForURL(/dashboard/);

      // 2. Create persona-specific workflow
      await page.click('[data-testid="nav-workflows"]');
      await page.click('[data-testid="create-workflow"]');

      if (personaName === 'alex') {
        // Productivity workflow
        await page.fill('[data-testid="workflow-name"]', 'Daily Standup Automation');
        await page.selectOption('[data-testid="trigger-type"]', 'schedule');
        await page.fill('[data-testid="trigger-time"]', '09:00');
        await page.click('[data-testid="add-notion-action"]');
      } else if (personaName === 'maria') {
        // Budget tracking workflow
        await page.fill('[data-testid="workflow-name"]', 'Spending Alert Monitor');
        await page.selectOption('[data-testid="trigger-type"]', 'threshold');
        await page.fill('[data-testid="alert-amount"]', '200');
        await page.selectOption('[data-testid="alert-category"]', 'dining');
      } else if
