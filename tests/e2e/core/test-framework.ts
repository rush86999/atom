import { Browser, Page, test as playwrightTest } from '@playwright/test';
import { TestConfig } from './test-config';

export interface TestContext {
  browser: Browser;
  page: Page;
  config: TestConfig;
  authToken?: string;
  userId?: string;
}

export interface Persona {
  id: string;
  name: string;
  email: string;
  characteristics: string[];
  goals: string[];
  integrations: string[];
}

export class BaseE2ETest {
  protected context: TestContext;
  protected config: TestConfig;

  constructor(config: TestConfig) {
    this.config = config;
  }

  async initializeTest(browser: Browser, testName: string): Promise<TestContext> {
    const context = await browser.newContext({
      locale: 'en-US',
      timezoneId: 'America/New_York',
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

  private async setupBrowserDefaults(page: Page) {
    await page.setViewportSize({ width: 1280, height: 720 });

    // Set up console logging for debugging
    page.on('console', (msg) => {
      if (process.env.DEBUG === 'e2e:*') {
        console.log(`[${msg.type()}] ${msg.text()}`);
      }
    });

    // Handle potential errors
    page.on('pageerror', (error) => {
      console.error('Page error:', error);
    });
  }

  async cleanupTest() {
    if (this.context?.page) {
      await this.context.page.close();
    }
  }

  async login(persona: Persona) {
    const { page } = this.context;

    await page.goto(`${this.config.baseUrl}/login`);
    await page.fill('[data-testid="email-input"]', persona.email);
    await page.fill('[data-testid="password-input"]', `TestPass123!_${persona.id}`);
    await page.click('[data-testid="login-button"]');

    // Wait for navigation or dashboard
    await page.waitForURL(`${this.config.baseUrl}/dashboard`, { timeout: 10000 });

    // Get auth token from localStorage
    const token = await page.evaluate(() => localStorage.getItem('authToken'));
    if (token) {
      this.context.authToken = token;
    }
  }

  async waitForElement(selector: string, timeout: number = 5000) {
    const element = await this.context.page.waitForSelector(selector, { timeout });
    return element;
  }

  async takeScreenshot(name: string) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    await this.context.page.screenshot({
      path: `tests/results/screenshots/${name}_${timestamp}.png`,
      fullPage: true
    });
  }
}

// Export the test function with context
export const test = playwrightTest.extend<{
  testContext: TestContext;
  persona: Persona;
}>({
  testContext: async ({ browser }, use) => {
    const config = new TestConfig();
    const baseTest = new BaseE2ETest(config);
    const context = await baseTest.initializeTest(browser, test.info().title);

    await use(context);

    await baseTest.cleanupTest();
  },
});
