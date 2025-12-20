import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Atom E2E tests.
 */
export default defineConfig({
    testDir: './tests/e2e',
    fullyParallel: false, // Run tests serially to avoid port conflicts
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 1,
    workers: 1, // Single worker to avoid conflicts
    reporter: 'html',

    use: {
        baseURL: 'http://localhost:3000',
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },

    /* Configure timeouts */
    timeout: 60000, // 60 second test timeout
    expect: {
        timeout: 10000, // 10 second assertion timeout
    },

    /* Configure projects for major browsers */
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],

    /* Run local dev server before tests if not already running */
    webServer: {
        command: 'npm run dev',
        url: 'http://localhost:3000',
        reuseExistingServer: true, // Reuse if already running
        timeout: 120000,
    },
});
