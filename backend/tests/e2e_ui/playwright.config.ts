import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for E2E UI tests.
 *
 * Configuration:
 * - Base URL: http://localhost:3001 (non-conflicting with dev frontend on port 3000)
 * - Browsers: Chromium only (Firefox and Safari deferred to v3.2)
 * - Timeout: 30 seconds for action timeout
 * - Retries: 0 (local), 2 (CI environment)
 * - Workers: 2 (CI), 4 (local) for parallel execution
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : 4,

  // Reporter configuration
  reporter: [
    ["html", { outputFolder: "reports/html-report" }],
    ["json", { outputFile: "reports/test-results.json" }],
    ["junit", { outputFile: "reports/junit-results.xml" }],
    ["list"],
  ],

  // Shared settings for all tests
  use: {
    // Base URL for all tests (non-conflicting with dev frontend)
    baseURL: "http://localhost:3001",

    // Collect trace on failure
    trace: "retain-on-failure",

    // Screenshot configuration
    screenshot: "only-on-failure",

    // Video configuration
    video: "retain-on-failure",

    // Action timeout (30 seconds)
    actionTimeout: 30000,

    // Navigation timeout (30 seconds)
    navigationTimeout: 30000,

    // Ignore HTTPS errors for testing
    ignoreHTTPSErrors: true,

    // Bypass CSP for testing
    bypassCSP: true,

    // Accept downloads
    acceptDownloads: true,
  },

  // Projects define browser and context configurations
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },

    // Firefox and Safari (WebKit) deferred to v3.2
    // Uncomment when cross-browser testing is needed:
    //
    // {
    //   name: "firefox",
    //   use: { ...devices["Desktop Firefox"] },
    // },
    //
    // {
    //   name: "webkit",
    //   use: { ...devices["Desktop Safari"] },
    // },
  ],

  // Run your local dev server before starting the tests
  webServer: {
    command: "npm run test:start",
    url: "http://localhost:3001",
    reuseExistingServer: !process.env.CI,
    timeout: 120000, // 2 minutes
  },
});
