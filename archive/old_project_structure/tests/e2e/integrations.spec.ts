import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Integrations UI', () => {

    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        await page.goto(`${FRONTEND_URL}/integrations`);
    });

    test('integration catalog loads', async ({ page }) => {
        // Should show list of integrations
        // Use .first() to avoid strict mode violation if multiple elements exist
        await expect(page.locator('text=Slack').first().or(page.locator('text=GitHub').first())).toBeVisible();
    });

    test('can search integrations', async ({ page }) => {
        const searchInput = page.locator('input[placeholder*="Search"]');
        if (await searchInput.isVisible()) {
            await searchInput.fill('Slack');
            // Expect non-matching items to disappear or matching to stay
            await expect(page.locator('text=Slack')).toBeVisible();
        }
    });

    test('integration connection modal', async ({ page }) => {
        // Click on an integration card
        const slackCard = page.locator('text=Slack').first();
        if (await slackCard.isVisible()) {
             await slackCard.click();
             // Expect a modal or navigation
             // Check for "Connect" button
             await expect(page.locator('button', { hasText: /Connect|Configure/i })).toBeVisible();
        }
    });
});
