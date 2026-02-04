import { test, expect } from '@playwright/test';

test.describe('New Workflow Nodes Verification', () => {
    test.beforeEach(async ({ page }) => {
        // Mock API routes
        await page.route('**/api/**', async route => {
            const url = route.request().url();
            if (url.includes('/api/auth/session')) {
                return route.fulfill({
                    json: { user: { id: 'test', name: 'Test' }, expires: new Date(Date.now() + 86400000).toISOString() }
                });
            }
            return route.fulfill({ json: { success: true, items: [] } });
        });

        // Add auth cookie
        await page.context().addCookies([{
            name: 'next-auth.session-token',
            value: 'mock-token',
            domain: 'localhost',
            path: '/'
        }]);

        await page.goto('/automations', { waitUntil: 'domcontentloaded' });
        await page.getByRole('button', { name: 'Visual Builder' }).click();
    });

    test('Should add Email Node', async ({ page }) => {
        await page.getByRole('button', { name: 'Email' }).click();
        await expect(page.getByText('Send Email')).toBeVisible();
        await expect(page.getByText('recipient@email.com')).toBeVisible();
    });

    test('Should add HTTP Node', async ({ page }) => {
        await page.getByRole('button', { name: 'HTTP' }).click();
        await expect(page.getByText('HTTP Request')).toBeVisible();
        await expect(page.getByText('GET')).toBeVisible();
    });

    test('Should add Timer Node', async ({ page }) => {
        await page.getByRole('button', { name: 'Delay' }).click();
        await expect(page.getByText('Delay')).toBeVisible();
        await expect(page.getByText('5')).toBeVisible();
        await expect(page.getByText('minutes')).toBeVisible();
    });
});
