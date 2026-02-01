import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Chat UI', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(`${FRONTEND_URL}/chat`, { timeout: 30000 });
        await page.waitForLoadState('domcontentloaded');
    });

    test('chat interface loads', async ({ page }) => {
        await expect(page.locator('input[placeholder*="Type"]')).toBeVisible({ timeout: 15000 });
    });

    test('can send message', async ({ page }) => {
        // Mock backend response
        await page.route('**/api/chat/message', async route => {
            await route.fulfill({
                json: {
                    success: true,
                    message: 'Hello from AI',
                    session_id: 'test_session',
                    intent: 'chat',
                    confidence: 1.0,
                    suggested_actions: [],
                    requires_confirmation: false,
                    next_steps: [],
                    timestamp: new Date().toISOString()
                }
            });
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
        await page.route('**/api/chat/sessions*', async route => {
            await route.fulfill({
                json: {
                    sessions: {
                        'session_1': {
                            id: 'session_1',
                            title: 'Test Session',
                            last_updated: new Date().toISOString(),
                            last_message: 'Old msg'
                        }
                    }
                }
            });
        });

        await page.goto(`${FRONTEND_URL}/chat`);
        await expect(page.locator('text=Old msg')).toBeVisible();
    });
});
