import { test, expect } from '@playwright/test';

test.describe('Workflow Builder UI Tests', () => {

    test.beforeEach(async ({ page }) => {
        // Mock ALL API routes before navigation to prevent auth redirects
        await page.route('**/api/**', async route => {
            const url = route.request().url();

            // Auth session mock
            if (url.includes('/api/auth/session')) {
                return route.fulfill({
                    json: {
                        user: { id: 'test-user', email: 'test@example.com', name: 'Test User' },
                        expires: new Date(Date.now() + 86400000).toISOString()
                    }
                });
            }

            // Workflow API mocks
            if (url.includes('/api/workflows/templates')) {
                return route.fulfill({ json: { success: true, templates: [] } });
            }
            if (url.includes('/api/workflows/definitions')) {
                return route.fulfill({ json: { success: true, workflows: [] } });
            }
            if (url.includes('/api/workflows/executions')) {
                return route.fulfill({ json: { success: true, executions: [] } });
            }
            if (url.includes('/api/workflows/services')) {
                return route.fulfill({ json: { success: true, services: {} } });
            }

            // Default: continue with actual request
            return route.continue();
        });

        // Set auth cookies
        await page.context().addCookies([{
            name: 'next-auth.session-token',
            value: 'mock-session-token-valid',
            domain: 'localhost',
            path: '/'
        }]);

        // Navigate with networkidle wait strategy
        await page.goto('/automations', { waitUntil: 'networkidle', timeout: 30000 });

        // Wait for page to load content
        await expect(page.locator('body')).toBeVisible({ timeout: 10000 });

        // Either loading is gone OR page content is visible
        try {
            await expect(page.getByText('Loading workflow automation...')).not.toBeVisible({ timeout: 5000 });
        } catch {
            // Loading might have already finished
        }
        await expect(page.locator('h1')).toContainText('Workflow Automation', { timeout: 15000 });
    });

    test('TC101: Should switch to Visual Builder view', async ({ page }) => {
        // Initial state: Classic View
        await expect(page.getByRole('tab', { name: 'Templates' })).toBeVisible();

        // Check for header buttons
        await expect(page.getByRole('button', { name: 'Create Workflow' })).toBeVisible();
        const builderBtn = page.getByRole('button', { name: 'Visual Builder' });
        await expect(builderBtn).toBeVisible();
        await builderBtn.click();

        // Check for ReactFlow canvas
        await expect(page.locator('.react-flow')).toBeVisible();
        await expect(page.getByText('Workflow Builder')).toBeVisible();
    });

    test('TC102: Should render initial nodes (Trigger, Condition, AI)', async ({ page }) => {
        await page.getByRole('button', { name: 'Visual Builder' }).click();

        // Check for Trigger Node
        await expect(page.getByText('Webhook Start')).toBeVisible();
        await expect(page.getByText('Input Schema:')).toBeVisible();

        // Check for Condition Node (and handles)
        await expect(page.getByText('userId exists?')).toBeVisible();

        // Check for AI Node
        await expect(page.getByText('AI Processing')).toBeVisible();
        await expect(page.getByText('Analyze Intent')).toBeVisible();
        await expect(page.getByText('GPT-4')).toBeVisible();
    });

    test('TC103: Should add new nodes via toolbar', async ({ page }) => {
        await page.getByRole('button', { name: 'Visual Builder' }).click();

        // Add Condition Node
        await page.getByRole('button', { name: 'Add Condition' }).click();
        // Since positions are random, we just check count or existence of new generic label
        // The default label in AddNode is "condition node" or "action node"
        await expect(page.getByText('condition node')).toBeVisible();

        // Add Action Node
        // await page.getByRole('button', { name: 'Add Action' }).click();
        // await expect(page.getByText('action node')).toBeVisible();
    });

    test('TC104: Should toggle back to Classic View', async ({ page }) => {
        await page.getByRole('button', { name: 'Visual Builder' }).click();
        await expect(page.locator('.react-flow')).toBeVisible();

        await page.getByRole('button', { name: 'Classic View' }).click();
        await expect(page.locator('.react-flow')).not.toBeVisible();
        await expect(page.getByRole('tab', { name: 'Templates' })).toBeVisible();
    });

});
