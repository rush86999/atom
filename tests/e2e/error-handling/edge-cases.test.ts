import { test, expect } from '@playwright/test';
import { TestHelpers } from '../utils/test-utils';

test.describe('Edge Cases & Error Handling', () => {
  test('handles invalid OAuth callback gracefully', async ({ page }) => {
    await page.goto('http://localhost:3000/auth/google/callback?error=access_denied');

    await expect(page.locator('[data-testid="login-error"]')).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test('network timeout recovery', async ({ page }) => {
    await TestHelpers.mockNetworkRrror(page);
    await page.goto('http://localhost:3000/dashboard');

    await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();
    await page.click('[data-testid="retry-button"]');

    await expect(page.locator('[data-testid="dashboard-loaded"]')).toBeVisible();
  });

  test('handles invalid persona selection', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await TestHelpers.mockInvalidPersona(page);

    const response = await page.request.post('http://localhost:3000/api/persona/select', {
      data: { persona: 'invalid_persona_type' }
    });

    expect(response.status()).toBe(400);
    const error = await response.json();
    expect(error.message).toContain('Invalid persona');
  });

  test('data validation on task creation', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Attempt to create task with no title
    await page.click('[data-testid="create-task-button"]');
    await page.click('[data-testid="save-task"]');

    await expect(page.locator('[data-testid="validation-errors"]')).toContainText('Title is required');
  });

  test('concurrent API calls handling', async ({ page }) => {
    await page.goto('http://localhost:3000/dashboard');

    // Trigger multiple API calls simultaneously
    await Promise.all([
      page.click('[data-testid="refresh-calendar"]'),
      page.click('[data-testid="refresh-tasks"]'),
      page.click('[data-testid="refresh-integrations"]')
    ]);

    await expect(page.locator('[data-testid="loading-spinner"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-loaded"]')).toBeVisible({ timeout: 10000 });
  });

  test('handles API rate limiting', async ({ page }) => {
    await TestHelpers.mockRateLimit(page);
    await page.goto('http://localhost:3000/integrations/notion');

    // Attempt to fetch data
    await page.click('[data-testid="sync-notion"]');
    await expect(page.locator('[data-testid="rate-limit-message"]')).toContainText('Please try again in');
  });

  test('offline mode failover', async ({ page }) => {
    await TestHelpers.mockOffline(page);
    await page.goto('http://localhost:3000/tasks');

    await expect(page.locator('[data-testid="offline-badge"]')).toBeVisible();
    await expect(page.locator('[data-testid="cached-content-message"]')).toBeVisible();
  });

  test('large data set handling', async ({ page }) => {
    await TestHelpers.mockLargeDataSet(page);
    await page.goto('http://localhost:3000/calendar/2024');

    // Validate pagination or virtual scrolling
    await expect(page.locator('[data-testid="event-count"]')).toContainText('100+ events');
    await expect(page.locator('[data-testid="pagination-controls"]')).toBeVisible();
  });

  test('handles special characters in inputs', async ({ page }) => {
    await page.goto('http://localhost:3000/tasks/create');

    await page.fill('[data-testid="task-title"]', 'Meeting with "<script>alert()"</script>');
    await page.fill('[data-testid="task-description"]', 'Call @company & discuss Q1/2024');

    await page.click('[data-testid="save-task"]');

    // Verify no XSS issues and data is preserved
    await expect(page.locator('[data-testid="task-display"]')).toContainText('Meeting with');
    await expect(page.locator('[data-testid="task-display"]')).toContainText('@company');
  });

  test('session timeout handling', async ({ page }) => {
    await page.goto('http://localhost:3000/dashboard');

    await TestHelpers.mockSessionTimeout(page);

    // Attempt protected action
    await page.click('[data-testid="start-workflow"]');

    await expect(page.locator('[data-testid="session-expired-modal"]')).toBeVisible();
    await expect(page).toHaveURL(/\/login\
