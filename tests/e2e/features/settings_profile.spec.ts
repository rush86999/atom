import { test, expect } from '@playwright/test';

test.describe('Settings and Profile Features', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/settings');
  });

  test('Update user profile information', async ({ page }) => {
    await page.click('[data-testid="profile-section"]');
    await page.fill('[data-testid="display-name"]', 'Updated Name');
    await page.fill('[data-testid="bio"]', 'New bio information');
    await page.click('[data-testid="save-profile"]');

    await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
    await page.reload();
    await expect(page.locator('[data-testid="display-name"]')).toHaveValue('Updated Name');
  });

  test('Change password flow', async ({ page }) => {
    await page.click('[data-testid="security-section"]');
    await page.click('[data-testid="change-password"]');

    await page.fill('[data-testid="current-password"]', 'OldPass123!');
    await page.fill('[data-testid="new-password"]', 'NewPass456!');
    await page.fill('[data-testid="confirm-password"]', 'NewPass456!');
    await page.click('[data-testid="submit-password-change"]');

    await expect(page.locator('[data-testid="password-updated"]')).toBeVisible();
  });

  test('Notification preferences', async ({ page }) => {
    await page.click('[data-testid="notifications-section"]');

    // Toggle switches
    await page.click('[data-testid="email-notifications-toggle"]');
    await page.click('[data-testid="push-notifications-toggle"]');
    await page.click('[data-testid="save-preferences"]');

    await expect(page.locator('[data-testid="preferences-saved"]')).toBeVisible();
  });

  test('Theme switching (Dark/Light)', async ({ page }) => {
    await page.click('[data-testid="appearance-section"]');

    await page.click('[data-testid="theme-dark"]');
    await expect(page.locator('html')).toHaveAttribute('class', /dark/);

    await page.click('[data-testid="theme-light"]');
    await expect(page.locator('html')).not.toHaveAttribute('class', /dark/);
  });

  test('Language selection', async ({ page }) => {
    await page.click('[data-testid="preferences-section"]');
    await page.selectOption('[data-testid="language-select"]', 'es'); // Spanish
    await page.click('[data-testid="save-language"]');

    await expect(page.locator('h1')).toHaveAttribute('lang', 'es');
  });

  test('Data export request', async ({ page }) => {
    await page.click('[data-testid="privacy-section"]');
    await page.click('[data-testid="request-export"]');

    await expect(page.locator('[data-testid="export-pending"]')).toBeVisible();
  });

  test('Delete account flow (initiate)', async ({ page }) => {
    await page.click('[data-testid="danger-zone"]');
    await page.click('[data-testid="delete-account-btn"]');

    await expect(page.locator('[data-testid="delete-confirmation-modal"]')).toBeVisible();
    await page.fill('[data-testid="confirm-delete-input"]', 'DELETE');
    // We won't actually click delete in the test to avoid destroying state, or we mock it
    await expect(page.locator('[data-testid="confirm-delete-final"]')).toBeEnabled();
  });
});
