import { test, expect } from '@playwright/test';

const FRONTEND_URL = 'http://localhost:3000';

test.describe('Authentication', () => {

    test('login page loads', async ({ page }) => {
        await page.goto(`${FRONTEND_URL}/login`);
        await expect(page).toHaveURL(/login/);
        await expect(page.locator('text=Welcome back!')).toBeVisible();
    });

    test('can toggle between login and register', async ({ page }) => {
        await page.goto(`${FRONTEND_URL}/login`);
        await page.click('text=Sign up');
        await expect(page.locator('text=Create your account')).toBeVisible();
        await expect(page.locator('input[placeholder="John"]')).toBeVisible();
        await page.click('text=Sign in');
        await expect(page.locator('text=Welcome back!')).toBeVisible();
        await expect(page.locator('input[placeholder="John"]')).not.toBeVisible();
    });

    // Mock login since we don't have a guaranteed test user and don't want to create one every time if not needed
    test('successful login redirects to team-chat', async ({ page }) => {
         await page.route('**/api/auth/login', async route => {
            const json = { access_token: 'fake-token' };
            await route.fulfill({ json });
        });

        await page.goto(`${FRONTEND_URL}/login`);
        await page.fill('input[type="email"]', 'test@example.com');
        await page.fill('input[type="password"]', 'password');
        await page.click('button:has-text("Sign In")');

        await expect(page).toHaveURL(/team-chat/);
    });

    test('invalid login shows error', async ({ page }) => {
        await page.route('**/api/auth/login', async route => {
             await route.fulfill({ status: 401, json: { detail: 'Invalid credentials' } });
        });

        await page.goto(`${FRONTEND_URL}/login`);
        await page.fill('input[type="email"]', 'wrong@example.com');
        await page.fill('input[type="password"]', 'wrongpass');
        await page.click('button:has-text("Sign In")');

        await expect(page.locator('text=Invalid credentials')).toBeVisible();
    });

    test('successful registration redirects to team-chat', async ({ page }) => {
        await page.route('**/api/auth/register', async route => {
            const json = { access_token: 'fake-token' };
            await route.fulfill({ json });
        });

        await page.goto(`${FRONTEND_URL}/login`);
        await page.click('text=Sign up');
        await page.fill('input[placeholder="John"]', 'Test');
        await page.fill('input[placeholder="Doe"]', 'User');
        await page.fill('input[type="email"]', 'new@example.com');
        await page.fill('input[type="password"]', 'password');
        await page.click('button:has-text("Create Account")');

        await expect(page).toHaveURL(/team-chat/);
    });
});
