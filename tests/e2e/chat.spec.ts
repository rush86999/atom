import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Chat UI', () => {

    test.beforeEach(async ({ page }) => {
        await page.addInitScript(() => {
            localStorage.setItem('auth_token', 'fake-token');
        });
        await page.goto(`${FRONTEND_URL}/chat`);
    });

    test('chat interface loads', async ({ page }) => {
        await expect(page.locator('input[placeholder*="Type"]')).toBeVisible();
    });

    test('can send message', async ({ page }) => {
        // Mock backend response
        await page.route('**/api/ai/chat', async route => {
            await route.fulfill({ json: { response: 'Hello from AI' } });
        });

        const input = page.locator('input[placeholder*="Type"]');
        await input.fill('Hello AI');
        await input.press('Enter');

        // Check for user message
        await expect(page.locator('text=Hello AI')).toBeVisible();
        // Check for AI response (if UI updates optimistically or waits for response)
        // Note: The UI might use WebSocket or SSE.
    });

    test('history loads', async ({ page }) => {
        // Mock history BEFORE navigation
         await page.route('**/api/chat/history', async route => {
            await route.fulfill({ json: { messages: [{ role: 'user', content: 'Old msg' }] } });
        });

        await page.goto(`${FRONTEND_URL}/chat`);
        await expect(page.locator('text=Old msg')).toBeVisible();
    });
});
