import { test, expect } from '@playwright/test';
import { personas } from '../core/personas';
import { TestConfig, BaseE2ETest } from '../core/test-framework';

const alex = personas.alex;

test.describe('Alex Chen - Growth-Oriented Professional Core Journey', () => {
  let config: TestConfig;

  test.beforeEach(async ({ page }) => {
    config = new TestConfig();

    // Ensure we're starting fresh
    await page.goto(`${config.baseUrl}`);
    await page.evaluate(() => localStorage.clear());
    await page.evaluate(() => sessionStorage.clear());
  });

  test('Alex signs up and completes onboarding', async ({ page }) => {
    await page.goto(`${config.baseUrl}/signup`);

    // Fill registration form
    await page.fill('[data-testid="email-input"]', alex.email);
    await page.fill('[data-testid="name-input"]', alex.name);
    await page.fill('[data-testid="password-input"]', `TestPass123!_${alex.id}`);
    await page.fill('[data-testid="confirm-password-input"]', `TestPass123!_${alex.id}`);

    // Select persona
    await page.click('[data-testid="persona-growth-professional"]');
    await page.click('[data-testid="continue-button"]');

    // Onboarding workflow questions
    await page.fill('#current-job-title', 'Senior Product Manager');
    await page.fill('#company-size', '50-200');

    // Goals selection
    await page.click('[data-testid="goal-productivity"]');
    await page.click('[data-testid="goal-automation"]');
    await page.click('[data-testid="goal-team-collaboration"]');

    // Integration selection
    await page.click('[data-testid="integration-notion"]');
    await page.click('[data-testid="integration-google-calendar"]');
    await page.click('[data-testid="integration-github"]');

    // Complete onboarding
    await page.click('[data-testid="complete-setup"]');

    // Verify dashboard loaded
    await expect(page).toHaveURL(`${config.baseUrl}/dashboard`);
    await expect(page.locator('[data-testid="welcome-header"]')).toContainText(`Welcome back, ${alex.name}!`);
  });

  test('Alex creates productivity workflow', async ({ page }) => {
    // First login
    await page.goto(`${config.baseUrl}/login`);
    await page.fill('[data-testid="email-input"]', alex.email);
    await page.fill('[data-testid="password-input"]', `TestPass123!_${alex.id}`);
    await page.click('[data-testid="login-button"]');
    await page.waitForURL(`${config.baseUrl}/dashboard`);

    // Navigate to workflows
    await page.click('[data-testid="workflows-menu"]');
    await page.click('[data-testid="create-workflow-button"]');

    // Define workflow
    await page.fill('[data-testid="workflow-name"]', 'Daily Standup Automation');
    await page.fill('[data-testid="workflow-description"]', 'Automate daily standup updates from Notion tasks');

    // Add trigger
    await page.selectOption('[data-testid="trigger-type"]', 'scheduled');
    await page.fill('[data-testid="trigger-schedule"]', 'daily 9:00');

    // Add action
    await page.click('[data-testid="add-action-button"]');
    await page.selectOption('[data-testid="action-type"]', 'api-call');
    await page.selectOption('[data-testid="integration-select"]', 'notion');

    // Save workflow
    await page.click('[data-testid="save-workflow"]');
    await expect(page.locator('[data-testid="success-toast"]')).toContainText('Workflow created successfully');
  });

  test('Alex manages team tasks with AI insights', async ({ page }) => {
    await page.goto(`${config.baseUrl}/login`);
    await page.fill('[data-testid="email-input"]', alex.email);
    await page.fill('[data-testid="password-input"]', `TestPass123!_${alex.id}`);
    await page.click('[data-testid="login-button"]`);
+    await page.waitForURL(`${config.baseUrl}/dashboard`);

    // Navigate to tasks view
    await page.click('[data-testid="tasks-menu"]');
    await page.waitForURL(`${config.baseUrl}/tasks`);

    // Create new task with AI suggestions
    await page.click('[data-testid="new-task-button"]');
    await page.fill('[data-testid="task-title"]', 'Prepare Q1 roadmap presentation');
    await page.click('[data-testid="get-ai-suggestions"]');

    // Verify AI suggestions appear
    await expect(page.locator('[data-testid="ai-suggestions"]')).toBeVisible();
    await expect(page.locator('[data-testid="suggested-tags"]')).
