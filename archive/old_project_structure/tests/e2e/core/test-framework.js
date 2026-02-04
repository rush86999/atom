"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.test = exports.BaseE2ETest = void 0;
const test_1 = require("@playwright/test");
const test_config_1 = require("./test-config");
class BaseE2ETest {
  constructor(config) {
    this.config = config;
  }
  async initializeTest(browser, testName) {
    const context = await browser.newContext({
      locale: "en-US",
      timezoneId: "America/New_York",
    });
    const page = await context.newPage();
    this.context = {
      browser,
      page,
      config: this.config,
    };
    await this.setupBrowserDefaults(page);
    return this.context;
  }
  async setupBrowserDefaults(page) {
    await page.setViewportSize({ width: 1280, height: 720 });
    // Set up console logging for debugging
    page.on("console", (msg) => {
      if (process.env.DEBUG === "e2e:*") {
        console.log(`[${msg.type()}] ${msg.text()}`);
      }
    });
    // Handle potential errors
    page.on("pageerror", (error) => {
      console.error("Page error:", error);
    });
  }
  async cleanupTest() {
    if (this.context?.page) {
      await this.context.page.close();
    }
  }
  async login(persona) {
    const { page } = this.context;
    await page.goto(`${this.config.baseUrl}/login`);
    await page.fill('[data-testid="email-input"]', persona.email);
    await page.fill(
      '[data-testid="password-input"]',
      `TestPass123!_${persona.id}`,
    );
    await page.click('[data-testid="login-button"]');
    // Wait for navigation or dashboard
    await page.waitForURL(`${this.config.baseUrl}/dashboard`, {
      timeout: 10000,
    });
    // Get auth token from localStorage
    const token = await page.evaluate(() => localStorage.getItem("authToken"));
    if (token) {
      this.context.authToken = token;
    }
  }
  async waitForElement(selector, timeout = 5000) {
    const element = await this.context.page.waitForSelector(selector, {
      timeout,
    });
    return element;
  }
  async takeScreenshot(name) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    await this.context.page.screenshot({
      path: `tests/results/screenshots/${name}_${timestamp}.png`,
      fullPage: true,
    });
  }
}
exports.BaseE2ETest = BaseE2ETest;
// Export the test function with context
exports.test = test_1.test.extend({
  testContext: async ({ browser }, use) => {
    const config = new test_config_1.TestConfig();
    const baseTest = new BaseE2ETest(config);
    const context = await baseTest.initializeTest(
      browser,
      exports.test.info().title,
    );
    await use(context);
    await baseTest.cleanupTest();
  },
});
//# sourceMappingURL=test-framework.js.map
