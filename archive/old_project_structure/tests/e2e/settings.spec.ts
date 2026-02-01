import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Settings', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        await page.goto(`${FRONTEND_URL}/settings`);
    });

    test('settings page loads', async ({ page }) => {
        await expect(page).toHaveURL(/settings/);
    });

    test('profile section exists', async ({ page }) => {
        await expect(page.locator('text=Profile').first().or(page.locator('text=Account').first())).toBeVisible();
    });

    test('API keys section exists', async ({ page }) => {
         await expect(page.locator('text=API Key').first().or(page.locator('text=Security').first())).toBeVisible();
    });
});
