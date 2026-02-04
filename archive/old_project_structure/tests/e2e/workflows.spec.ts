import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Workflows UI', () => {

    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });

        // Mock endpoints BEFORE navigation
        await page.route('**/api/workflows/definitions', async route => {
            await route.fulfill({
                json: {
                    success: true,
                    workflows: [
                        { id: '1', name: 'Test Workflow 1', description: 'Desc 1', created_at: new Date().toISOString() },
                        { id: '2', name: 'Test Workflow 2', description: 'Desc 2', created_at: new Date().toISOString() }
                    ]
                }
            });
        });
        await page.route('**/api/workflows/templates', async route => {
            await route.fulfill({ json: { success: true, templates: [] } });
        });
        await page.route('**/api/workflows/executions', async route => {
            await route.fulfill({ json: { success: true, executions: [] } });
        });
        await page.route('**/api/workflows/services', async route => {
             await route.fulfill({ json: { success: true, services: {} } });
        });

        await page.goto(`${FRONTEND_URL}/workflows`);
    });

    test('workflow list displayed', async ({ page }) => {
        // Wait for loading to finish
        await expect(page.locator('text=Loading workflow automation...')).not.toBeVisible({ timeout: 10000 });

        // Click on "My Workflows" tab to see workflows
        await page.getByRole('tab', { name: 'My Workflows' }).click();

        await expect(page.locator('text=Test Workflow 1')).toBeVisible();
        await expect(page.locator('text=Test Workflow 2')).toBeVisible();
    });

    test('create workflow button exists', async ({ page }) => {
        // Look for "Create Workflow"
        await expect(page.getByRole('button', { name: 'Create Workflow' })).toBeVisible();
    });

    test('can enter create workflow modal', async ({ page }) => {
        await page.getByRole('button', { name: 'Create Workflow' }).click();
        await expect(page.getByRole('dialog')).toBeVisible();
    });
});
