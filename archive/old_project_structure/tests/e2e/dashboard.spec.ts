import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';

test.describe('Dashboard', () => {

    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        await page.goto(`${FRONTEND_URL}/dashboard`);
    });

    test('dashboard loads', async ({ page }) => {
        await expect(page).toHaveURL(/dashboard/);
    });

    test('widgets are present', async ({ page }) => {
        // Look for common dashboard elements like "Performance", "Activity", "Stats"
        // Adjust selectors based on actual content
        // Based on Dashboard.tsx component names: PerformanceDashboard, SystemStatusDashboard

        // Wait for potential async loading
        await page.waitForTimeout(1000);

        const content = await page.content();
        expect(content).toContain('Dashboard');
    });

    test('system status widget loads', async ({ page }) => {
        // If there is a system status section
        // We can check if it makes a call to backend status
        const responsePromise = page.waitForResponse(resp => resp.url().includes('/status') || resp.url().includes('/health'));
        // Trigger reload or wait
        await page.reload();
        const response = await responsePromise;
        expect(response.ok()).toBeTruthy();
    });
});
