import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Verticals - Finance', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        await page.goto(`${FRONTEND_URL}/finance`);
    });

    test('finance dashboard loads', async ({ page }) => {
        await expect(page).toHaveURL(/finance/);
        // Expect financial terms
        await expect(page.locator('text=Revenue').first().or(page.locator('text=Expenses').first())).toBeVisible();
    });
});
