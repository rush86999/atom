import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Verticals - Communication', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        await page.goto(`${FRONTEND_URL}/communication`);
    });

    test('communication hub loads', async ({ page }) => {
        await expect(page).toHaveURL(/communication/);
        // Expect email or message related UI
        await expect(page.locator('text=Inbox').first().or(page.locator('text=Messages').first())).toBeVisible();
    });
});
