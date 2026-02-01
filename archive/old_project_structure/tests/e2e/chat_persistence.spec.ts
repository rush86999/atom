import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Chat Persistence (Full Stack)', () => {

    test('messages persist after reload', async ({ page }) => {
        // 1. Go to chat (using real backend)
        await page.goto(`${FRONTEND_URL}/chat`);
        await page.waitForLoadState('domcontentloaded');

        // 2. Type a unique message
        const timestamp = Date.now();
        const uniqueMessage = `Persistence Check ${timestamp}`;
        const input = page.locator('input[placeholder*="Type"]');

        await expect(input).toBeVisible({ timeout: 15000 });
        await input.fill(uniqueMessage);
        await input.press('Enter');

        // 3. Wait for it to appear in the chat stream
        // (Real backend might take a moment to "think" if AI is connected, 
        //  but the user message usually appears instantly or optimistically)
        await expect(page.locator(`text=${uniqueMessage}`)).toBeVisible({ timeout: 10000 });

        // 4. Reload the page
        await page.reload();
        await page.waitForLoadState('domcontentloaded');

        // 4a. Wait for sidebar to load and SEARCH for our specific session
        // Data pollution (shared default_user) makes "click first" flaky.
        // Search filters by message preview, guaranteeing we find ours.
        const searchInput = page.locator('input[placeholder="Search chats..."]');
        await expect(searchInput).toBeVisible({ timeout: 10000 });
        await searchInput.fill(uniqueMessage);

        // Wait for filter to apply
        const sessionItem = page.getByTestId('session-item').first();
        await expect(sessionItem).toBeVisible({ timeout: 60000 });
        await sessionItem.click();

        // 5. Verify the message is still there (fetched from backend JSON)
        await expect(page.locator(`text=${uniqueMessage}`)).toBeVisible({ timeout: 15000 });
    });

    test('smart response works', async ({ page }) => {
        // 1. Go to chat
        await page.goto(`${FRONTEND_URL}/chat`);
        await page.waitForLoadState('domcontentloaded');

        // 2. Type "Hello"
        const input = page.locator('input[placeholder*="Type"]');
        await expect(input).toBeVisible({ timeout: 15000 });
        await input.fill('Hello');
        await input.press('Enter');

        // 3. Verify the "Smart" Response (The fix)
        // Expecting the greeting we configured in ChatOrchestrator
        await expect(page.locator('text=Hello! I\'m Atom')).toBeVisible({ timeout: 10000 });
    });
});
