import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Performance', () => {
    test('homepage load time', async ({ page }) => {
        const start = Date.now();
        await page.goto(FRONTEND_URL);
        const end = Date.now();
        expect(end - start).toBeLessThan(5000); // Should load under 5s
    });

    test('dashboard load time', async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        const start = Date.now();
        await page.goto(`${FRONTEND_URL}/dashboard`);
        const end = Date.now();
        expect(end - start).toBeLessThan(5000);
    });
});
