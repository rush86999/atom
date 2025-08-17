import { test, expect, Page } from '@playwright/test';

test.describe('Alex Chen - Working Professional Test Suite', () => {
  let page: Page;

  test.beforeEach(async ({ page: newPage }) => {
    page = newPage;
    await page.goto('http://localhost:3000');
  });

  test('Alex completes onboarding flow', async () => {
    await page.goto('http://localhost:3000/signup');

    await page.fill('[data-testid="email-input"]', 'alex.test@example.com');
    await page.fill('[data-testid="name-input"]', 'Alex Chen');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="submit-register"]');

    await page.click('[data-testid="persona-alex"]');
    await page.fill('[data-testid="job-title"]', 'Senior Product Manager');
    await page.fill('[data-testid="company"]', 'TechCorp');
    await page.click('[data-testid="complete-onboarding"]');

    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('h1')).toContainText(/Welcome, Alex!/);
  });

  test('Alex creates automation workflow', async () => {
    await page.goto('http://localhost:3000/login');
    await page.fill('[data-testid="email-input"]', 'alex.test@example.com');
    await page.fill('[data-testid="password-input"]', 'TestPass123!');
    await page.click('[data-testid="login-button"]');

    await page.waitForURL(/dashboard/);

    await page.click('[data-testid="nav-dashboard"]');
    await page.click('[data-testid="create-workflow"]');

    await page.fill('[data-testid="workflow-name"]', 'Daily Standup Automation');
    await page.selectOption('[data-testid="trigger-type"]', 'daily');
    await page.tick('[data-testid="include-calendar-events"]');
    await page.click('[data-testid="save-workflow"]');

    await expect(page.locator('[data-testid="success-message"]')).toContainText('Workflow created');
  });

  test('Alex uses productivity insights', async () => {
    await page.goto('http://localhost:3000/insights');
    await page.click('[data-testid="get-ai-insights"]');

    await expect(page.locator('[data-testid="productivity-score"]')).toBeVisible();
    await expect(page.locator('[data-testid="daily-recommendations"]')).toBeVisible();
  });

  test('Alex schedules meeting with AI', async () => {
    await page.goto('http://localhost:3000/calendar');
    await page.click('[data-testid="new-meeting"]');

    await page.fill('[data-testid="meeting-title"]', 'Q2 Planning Review');
    await page.fill('[data-testid="meeting-attendees"]', 'team@company.com');
    await page.fill('[data-testid="meeting-duration"]', '60');
    await page.click('[data-testid="schedule-with-ai"]');

    await expect(page.locator('[data-testid="meeting-scheduled"]')).toContainText('Meeting scheduled');
  });

  test('Alex manages tasks with voice commands', async () => {
    await page.goto('http://localhost:3000/tasks');
    await page.click('[data-testid="voice-command"]');
    await page.fill('[data-testid="voice-input"]', 'Create task: Send Q1 report by Friday');
    await page.click('[data-testid="process-voice"]');

    await expect(page.locator('[data-testid="task-created-notification"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-list"]')).toContainText('Q1 report');
  });
});
