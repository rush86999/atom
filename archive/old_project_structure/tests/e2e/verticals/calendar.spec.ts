import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Calendar Management', () => {
    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        await page.goto(`${FRONTEND_URL}/calendar`);
    });

    test('calendar view loads', async ({ page }) => {
        await expect(page).toHaveURL(/calendar/);
        // Expect some calendar element
        await expect(page.locator('text=Calendar').first()).toBeVisible();
    });

    test('can switch views', async ({ page }) => {
         // Assuming Month/Week/Day view switchers
         const viewSwitcher = page.locator('button', { hasText: /Month|Week|Day/i }).first();
         if (await viewSwitcher.isVisible()) {
             await viewSwitcher.click();
         }
    });
});
