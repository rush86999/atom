
import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Chat Auth Flow', () => {

    test('should show connect calendar card when scheduling without auth', async ({ page }) => {
        // 1. Navigate to chat
        await page.goto(`${FRONTEND_URL}/chat`);

        // 2. Wait for input
        const input = page.locator('input[placeholder*="Type"]');
        await expect(input).toBeVisible({ timeout: 30000 });

        // 3. Send scheduling message
        await input.fill('Schedule a team meeting for tomorrow');
        await input.press('Enter');

        // 4. Wait for response
        // We look for the "Connect Google Calendar" text which should be in the new Card
        const connectCard = page.locator('text=Connect Google Calendar');
        await expect(connectCard).toBeVisible({ timeout: 15000 });

        // 5. Verify it's clickable (or inside a card)
        // The text might be in the button or the card title. 
        // Based on my code: Button has "Connect" text, Card has "Connect Google Calendar" title.

        // Check for the "Connect" button specifically inside the card
        const connectButton = page.locator('button:has-text("Connect")');
        await expect(connectButton).toBeVisible();

        // Optional: Click and verify it tries to open URL
        // Since it might open a new tab, we need to handle that, but for now just existence proves the UI rendered the Action Card correctly.
    });

});
