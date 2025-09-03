"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.BaseE2ETest = exports.AuthPage = exports.PageObject = exports.TestHelpers = void 0;
const fs_1 = require("fs");
const path_1 = require("path");
class TestHelpers {
    static async loadTestUsers() {
        const testUsersPath = (0, path_1.join)(__dirname, '../../fixtures/test-users.json');
        try {
            const users = JSON.parse((0, fs_1.readFileSync)(testUsersPath, 'utf-8'));
            return users;
        }
        catch (error) {
            return {
                alex: { id: 'test-alex-001', name: 'Alex Chen', email: 'alex.test@example.com', persona: 'busy_professional' },
                maria: { id: 'test-maria-001', name: 'Maria Rodriguez', email: 'maria.test@example.com', persona: 'financial_optimizer' },
                ben: { id: 'test-ben-001', name: 'Ben Carter', email: 'ben.test@example.com', persona: 'solopreneur' }
            };
        }
    }
    static async waitForSelectorWithRetry(page, selector, timeout = 10000, retries = 3) {
        for (let i = 0; i < retries; i++) {
            try {
                await page.waitForSelector(selector, { timeout: timeout / retries });
                return true;
            }
            catch (error) {
                if (i === retries - 1)
                    throw error;
                await page.waitForTimeout(1000);
            }
        }
    }
    static async generateScreenshot(page, testName) {
        const screenshotsDir = (0, path_1.join)(__dirname, '../../screenshots');
        if (!(0, fs_1.existsSync)(screenshotsDir)) {
            (0, fs_1.mkdirSync)(screenshotsDir, { recursive: true });
        }
        const screenshotPath = (0, path_1.join)(screenshotsDir, `${testName}-${Date.now()}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true });
        return screenshotPath;
    }
    static async mockOAuthFlows(page) {
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
    static async mockFinancialData(page) {
        await page.route('**/plaid/**', async (route) => {
            const url = route.request().url();
            if (url.includes('accounts')) {
                return route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        accounts: [
                            {
                                account_id: 'acc_123',
                                name: 'Checking Account',
                                type: 'checking',
                                balance: 5234.56,
                                currency: 'USD'
                            },
                            {
                                account_id: 'acc_456',
                                name: 'Savings Account',
                                type: 'savings',
                                balance: 15000.00,
                                currency: 'USD'
                            }
                        ]
                    })
                });
            }
            if (url.includes('transactions')) {
                return route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        transactions: [
                            {
                                transaction_id: 'txn_001',
                                amount: -45.67,
                                name: 'Starbucks',
                                date: new Date().toISOString().split('T')[0],
                                category: ['Food and Drink', 'Coffee Shops']
                            },
                            {
                                transaction_id: 'txn_002',
                                amount: -125.00,
                                name: 'Amazon',
                                date: new Date(Date.now() - 86400000).toISOString().split('T')[0],
                                category: ['Shopping', 'Online']
                            }
                        ]
                    })
                });
            }
            return route.continue();
        });
    }
    static async mockCalendarData(page) {
        await page.route('**/googleapis.com/calendar/**', async (route) => {
            const url = route.request().url();
            if (url.includes('events')) {
                return route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        items: [
                            {
                                id: 'event_001',
                                summary: 'Q3 Roadmap Sync',
                                start: { dateTime: new Date().toISOString() },
                                end: { dateTime: new Date(Date.now() + 3600000).toISOString() },
                                location: 'Conference Room A'
                            },
                            {
                                id: 'event_002',
                                summary: 'Team Standup',
                                start: { dateTime: new Date(Date.now() + 86400000).toISOString() },
                                end: { dateTime: new Date(Date.now() + 86400000 + 1800000).toISOString() },
                                location: 'Virtual'
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
    static async mockNotionData(page) {
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
        +;
    }
}
exports.TestHelpers = TestHelpers;
+;
+ +;
class PageObject {
}
exports.PageObject = PageObject;
+protected;
page: test_1.Page;
+ +constructor(page, test_1.Page);
{
    +this.page;
    page;
    +;
}
+ +async;
waitForPageLoad();
{
    +await this.page.waitForLoadState('networkidle');
    +await this.page.waitForLoadState('domcontentloaded');
    +;
}
+ +async;
getCurrentUrl();
Promise < string > {}
    + ;
return this.page.url();
+;
+ +async;
takeScreenshot(name, string);
{
    +;
    return await TestHelpers.generateScreenshot(this.page, name);
    +;
}
+;
+ +;
class AuthPage extends PageObject {
}
exports.AuthPage = AuthPage;
+async;
navigateTo(url, string);
{
    +await this.page.goto(url);
    +await this.waitForPageLoad();
    +;
}
+ +async;
loginWithGoogle(email, string);
{
    +await TestHelpers.mockOAuthFlows(this.page);
    +await this.page.click('[data-testid="google-auth-button"]');
    +await this.page.waitForSelector('[data-testid="dashboard"]', { timeout: 10000 });
    +;
}
+ +async;
selectPersona(personaName, string);
{
    +await this.page.click(`[data-testid="persona-${personaName}"]`);
    +await this.page.waitForSelector(`[data-testid="${personaName}-dashboard"]`, { timeout: 10000 });
    +;
}
+ +async;
completeOnboarding(personaName, string);
{
    +await this.page.fill('[data-testid="user-name"]', `Test ${personaName}`);
    +await this.page.fill('[data-testid="user-email"]', `${personaName}.test@example.com`);
    +await this.page.click('[data-testid="continue-button"]');
    +await this.page.waitForSelector('[data-testid="integration-setup"]', { timeout: 10000 });
    +;
}
+;
+ +;
class BaseE2ETest {
}
exports.BaseE2ETest = BaseE2ETest;
+protected;
testUser: TestUser;
+protected;
page: test_1.Page;
+ +constructor(page, test_1.Page, user, TestUser);
{
    +this.page;
    page;
    +this.testUser;
    user;
    +;
}
+ +async;
setupTestEnvironment();
{
    +await TestHelpers.mockOAuthFlows(this.page);
    +await TestHelpers.mockFinancialData(this.page);
    +await TestHelpers.mockCalendarData(this.page);
    +await TestHelpers.mockNotionData(this.page);
    +;
}
+ +async;
captureInitialState();
{
    +;
    return;
}
//# sourceMappingURL=test-utils.js.map