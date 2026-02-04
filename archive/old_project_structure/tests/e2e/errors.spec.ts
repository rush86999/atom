import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Error Handling', () => {
    test('404 Page', async ({ page }) => {
        await page.goto(`${FRONTEND_URL}/non-existent-page-xyz`);
        await expect(page.locator('text=404').or(page.locator('text=could not be found'))).toBeVisible();
    });

    test('API Error Handling in Dashboard', async ({ page }) => {
        // Mock 500 error for status
        await page.route('**/api/status', async route => {
            await route.fulfill({ status: 500 });
        });

        await page.goto(`${FRONTEND_URL}/dashboard`);
        // The dashboard should still load, maybe with error state or empty widgets
        // It shouldn't crash the whole app
        await expect(page).toHaveURL(/dashboard/);
        await expect(page.locator('text=Dashboard').first()).toBeVisible();
    });
});
