import { Page, expect } from '@playwright/test';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';

export interface TestUser {
  id: string;
  name: string;
  email: string;
  persona: string;
}

export class TestHelpers {
  static async loadTestUsers(): Promise<Record<string, TestUser>> {
    const testUsersPath = join(__dirname, '../../fixtures/test-users.json');
    try {
      const users = JSON.parse(readFileSync(testUsersPath, 'utf-8'));
      return users;
    } catch (error) {
      return {
        alex: { id: 'test-alex-001', name: 'Alex Chen', email: 'alex.test@example.com', persona: 'busy_professional' },
        maria: { id: 'test-maria-001', name: 'Maria Rodriguez', email: 'maria.test@example.com', persona: 'financial_optimizer' },
        ben: { id: 'test-ben-001', name: 'Ben Carter', email: 'ben.test@example.com', persona: 'solopreneur' }
      };
    }
  }

  static async waitForSelectorWithRetry(page: Page, selector: string, timeout = 10000, retries = 3) {
    for (let i = 0; i < retries; i++) {
      try {
        await page.waitForSelector(selector, { timeout: timeout / retries });
        return true;
      } catch (error) {
        if (i === retries - 1) throw error;
        await page.waitForTimeout(1000);
      }
    }
  }

  static async generateScreenshot(page: Page, testName: string) {
    const screenshotsDir = join(__dirname, '../../screenshots');
    if (!existsSync(screenshotsDir)) {
      mkdirSync(screenshotsDir, { recursive: true });
    }
    const screenshotPath = join(screenshotsDir, `${testName}-${Date.now()}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    return screenshotPath;
  }

  static async mockOAuthFlows(page: Page) {
    await page.route('**/oauth/**', async (route) => {
      const url = route.request().url();

      // Mock Google OAuth
      if (url.includes('google') && url.includes('oauth')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            access_token: 'mock-google-token',
            refresh_token: 'mock-refresh-token',
            scope: 'email profile https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/drive'
          })
        });
      }

      // Mock Plaid
      if (url.includes('plaid')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            access_token: 'mock-plaid-token',
            item_id: 'mock-item-id'
          })
        });
      }

      return route.continue();
    });
  }

  static async setupFinancialTestData(page: Page) {
    // Test data for E2E financial integration testing
    // This simulates realistic banking data for testing the financial dashboard
    await page.route('**/plaid/**', async (route) => {
      const url = route.request().url();

      if (url.includes('accounts')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            accounts: [
              {
                account_id: 'test_checking_001',
                name: 'Primary Checking Account',
                type: 'checking',
                subtype: 'checking',
                balance: 5234.56,
                available_balance: 5234.56,
                currency: 'USD',
                iso_currency_code: 'USD',
                mask: '0000',
                institution_id: 'ins_1'
              },
              {
                account_id: 'test_savings_001',
                name: 'Emergency Savings',
                type: 'savings',
                subtype: 'savings',
                balance: 15000.00,
                available_balance: 15000.00,
                currency: 'USD',
                iso_currency_code: 'USD',
                mask: '1111',
                institution_id: 'ins_1'
              },
              {
                account_id: 'test_credit_001',
                name: 'Rewards Credit Card',
                type: 'credit',
                subtype: 'credit card',
                balance: -2340.89,
                available_balance: 17659.11,
                currency: 'USD',
                iso_currency_code: 'USD',
                mask: '2222',
                institution_id: 'ins_2'
              }
            ]
          })
        });
      }

      if (url.includes('transactions')) {
        const today = new Date().toISOString().split('T')[0];
        const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];
        const lastWeek = new Date(Date.now() - 604800000).toISOString().split('T')[0];

        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            transactions: [
              {
                transaction_id: 'test_txn_001',
                amount: -45.67,
                name: 'Starbucks Coffee',
                date: today,
                category: ['Food and Drink', 'Coffee Shops'],
                pending: false
              },
              {
                transaction_id: 'test_txn_002',
                amount: -125.43,
                name: 'Amazon.com',
                date: yesterday,
                category: ['Shopping', 'Online Marketplace'],
                pending: false
              },
              {
                transaction_id: 'test_txn_003',
                amount: -2100.00,
                name: 'Monthly Rent Payment',
                date: lastWeek,
                category: ['Transfer', 'Rent'],
                pending: false
              },
              {
                transaction_id: 'test_txn_004',
                amount: 3500.00,
                name: 'Salary Deposit',
                date: lastWeek,
                category: ['Transfer', 'Payroll'],
                pending: false
              }
            ]
          })
        });
      }

      return route.continue();
    });
  }

  static async setupCalendarTestData(page: Page) {
    // Test data for E2E calendar integration testing
    // This simulates realistic calendar events for testing calendar features
    await page.route('**/googleapis.com/calendar/**', async (route) => {
      const url = route.request().url();

      if (url.includes('events')) {
        const now = new Date();
        const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
        const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: 'test_event_001',
                summary: 'Team Standup Meeting',
                description: 'Daily sync with the development team',
                start: {
                  dateTime: new Date(now.getTime() + 2 * 60 * 60 * 1000).toISOString(),
                  timeZone: 'America/Los_Angeles'
                },
                end: {
                  dateTime: new Date(now.getTime() + 2.5 * 60 * 60 * 1000).toISOString(),
                  timeZone: 'America/Los_Angeles'
                },
                location: 'Virtual - Google Meet',
                attendees: [
                  { email: 'team-lead@company.com', displayName: 'Team Lead' },
                  { email: 'dev@company.com', displayName: 'Developer' }
                ]
              },
              {
                id: 'test_event_002',
                summary: 'Client Presentation',
                description: 'Q4 results presentation to key stakeholders',
                start: {
                  dateTime: tomorrow.toISOString(),
                  timeZone: 'America/Los_Angeles'
                },
                end: {
                  dateTime: new Date(tomorrow.getTime() + 60 * 60 * 1000).toISOString(),
                  timeZone: 'America/Los_Angeles'
                },
                location: 'Conference Room B',
                attendees: [
                  { email: 'client@external.com', displayName: 'Client Representative' },
                  { email: 'manager@company.com', displayName: 'Account Manager' }
                ]
              },
              {
                id: 'test_event_003',
                summary: 'Sprint Planning',
                description: 'Planning session for next development sprint',
                start: {
                  dateTime: nextWeek.toISOString(),
                  timeZone: 'America/Los_Angeles'
                },
                end: {
                  dateTime: new Date(nextWeek.getTime() + 2 * 60 * 60 * 1000).toISOString(),
                  timeZone: 'America/Los_Angeles'
                },
                location: 'Main Office - Room 101'
              }
            ]
          })
        });
      }

      if (url.includes('calendarList')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: 'primary',
                summary: 'Primary Calendar'
              }
            ]
          })
        });
      }
    });
  }

  static async mockNotionData(page: Page) {
    await page.route('**/api.notion.com/**', async (route) => {
      const url = route.request().url();

      if (url.includes('v1/search')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            results: [
              {
                object: 'page',
                id: 'test-page-001',
                properties: {
                  title: {
                    title: [
                      {
                        text: {
                          content: 'Q3 Product Roadmap'
                        }
                      }
                    ]
                  }
                }
              }
            ]
          })
        });
      }
    });
+  }
+}
+
+export class PageObject {
+  protected page: Page;
+
+  constructor(page: Page) {
+    this.page = page;
+  }
+
+  async waitForPageLoad() {
+    await this.page.waitForLoadState('networkidle');
+    await this.page.waitForLoadState('domcontentloaded');
+  }
+
+  async getCurrentUrl(): Promise<string> {
+    return this.page.url();
+  }
+
+  async takeScreenshot(name: string) {
+    return await TestHelpers.generateScreenshot(this.page, name);
+  }
+}
+
+export class AuthPage extends PageObject {
+  async navigateTo(url: string) {
+    await this.page.goto(url);
+    await this.waitForPageLoad();
+  }
+
+  async loginWithGoogle(email: string) {
+    await TestHelpers.mockOAuthFlows(this.page);
+    await this.page.click('[data-testid="google-auth-button"]');
+    await this.page.waitForSelector('[data-testid="dashboard"]', { timeout: 10000 });
+  }
+
+  async selectPersona(personaName: string) {
+    await this.page.click(`[data-testid="persona-${personaName}"]`);
+    await this.page.waitForSelector(`[data-testid="${personaName}-dashboard"]`, { timeout: 10000 });
+  }
+
+  async completeOnboarding(personaName: string) {
+    await this.page.fill('[data-testid="user-name"]', `Test ${personaName}`);
+    await this.page.fill('[data-testid="user-email"]', `${personaName}.test@example.com`);
+    await this.page.click('[data-testid="continue-button"]');
+    await this.page.waitForSelector('[data-testid="integration-setup"]', { timeout: 10000 });
+  }
+}
+
+export class BaseE2ETest {
+  protected testUser: TestUser;
+  protected page: Page;
+
+  constructor(page: Page, user: TestUser) {
+    this.page = page;
+    this.testUser = user;
+  }
+
+  async setupTestEnvironment() {
+    await TestHelpers.mockOAuthFlows(this.page);
+    await TestHelpers.setupFinancialTestData(this.page);
+    await TestHelpers.setupCalendarTestData(this.page);
+    await TestHelpers.setupNotionTestData(this.page);
+  }
+
+  async captureInitialState() {
+    return
