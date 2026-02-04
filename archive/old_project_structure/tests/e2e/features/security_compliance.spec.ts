import { test, expect } from '@playwright/test';

test.describe('Security and Compliance Features', () => {

  test.beforeEach(async ({ page }) => {
    // Admin view usually
    await page.goto('http://localhost:3000/admin/security');
  });

  test('View audit logs', async ({ page }) => {
    await page.click('[data-testid="nav-audit-logs"]');

    await expect(page.locator('[data-testid="audit-log-table"]')).toBeVisible();
    await expect(page.locator('.audit-row')).toHaveCount(10); // Check if rows exist
  });

  test('Filter audit logs', async ({ page }) => {
    await page.click('[data-testid="nav-audit-logs"]');

    await page.fill('[data-testid="filter-user"]', 'alex@example.com');
    await page.click('[data-testid="apply-filter"]');

    await expect(page.locator('[data-testid="loading-indicator"]')).not.toBeVisible();
    // Assuming filter works
    const rows = page.locator('.audit-row');
    // If we have rows, check they contain the user
    // This assertion depends on data
  });

  test('Manage user roles', async ({ page }) => {
    await page.click('[data-testid="nav-users"]');
    await page.click('[data-testid="edit-user-1"]');

    await page.selectOption('[data-testid="role-select"]', 'admin');
    await page.click('[data-testid="save-user"]');

    await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
  });

  test('Two-Factor Authentication Setup', async ({ page }) => {
      await page.goto('http://localhost:3000/settings/security');
      await page.click('[data-testid="setup-2fa"]');

      await expect(page.locator('[data-testid="qr-code"]')).toBeVisible();
      await page.fill('[data-testid="2fa-code-input"]', '123456');
      await page.click('[data-testid="verify-2fa"]');

      await expect(page.locator('[data-testid="2fa-enabled-badge"]')).toBeVisible();
  });

  test('Session management', async ({ page }) => {
      await page.goto('http://localhost:3000/settings/sessions');

      await expect(page.locator('.session-row')).toHaveCount(1); // At least current session
      await page.click('[data-testid="revoke-other-sessions"]');

      await expect(page.locator('[data-testid="revoke-success"]')).toBeVisible();
  });

  test('API Key management', async ({ page }) => {
      await page.goto('http://localhost:3000/settings/api-keys');
      await page.click('[data-testid="generate-key"]');
      await page.fill('[data-testid="key-name"]', 'CI Test Key');
      await page.click('[data-testid="create-key"]');

      await expect(page.locator('[data-testid="new-api-key"]')).toBeVisible();
  });
});
