import { test, expect, type Page } from '@playwright/test';
import { TestHelpers, AuthPage, BaseE2ETest, type TestUser } from '../utils/test-utils';

class CrossPlatformWorkflowTest extends BaseE2ETest {
  private authPage: AuthPage;

  constructor(page: Page) {
    super(page, { id: 'test-cross', name: 'Cross Platform', email: 'cross@test.com', persona: 'workflow' });
    this.authPage = new AuthPage(page);
  }

  async setupMultiPersonaEnvironment() {
    await this.setupTestEnvironment();
    TestHelpers.mockOAuthFlows(this.page);
    TestHelpers.mockFinancialData(this.page);
    TestHelpers.mockCalendarData(this.page);
    TestHelpers.mockNotionData(this.page);
  }

  async testAlexCrossPlatform() {
    // Navigate and login
    await this.authPage.navigateTo('http://localhost:3000');
    await this.authPage.loginWithGoogle('alex.test@example.com');

    // Enter Alex workflow
    await this.authPage.selectPersona('alex');

    // Test cross-platform integration
    await this.page.click('[data-testid="integrations-tab"]');

    // Link Google Calendar
    await this.page.click('[data-testid="link-calendar"]');
    await this.page.waitForSelector('[data-testid="calendar-connected"]', { timeout: 10000 });

    // Test calendar sync
    await this.page.click('[data-testid="test-calendar-sync"]');
    const calendarEvents = await this.page.textContent('[data-testid="synced-events"]');
    expect(calendarEvents).toContain('Q3 Roadmap Sync');

    // Test Notion integration
    await this.page.click('[data-testid="link-notion"]');
    await this.page.waitForSelector('[data-testid="notion-connected"]');

    // Create meeting that creates Notion task
    await this.page.click('[data-testid="voice-command-button"]');
    await this.page.fill('[data-testid="voice-input"]', 'Schedule 30 min meeting with Sarah tomorrow at 3pm and create follow-up task');
    await this.page.click('[data-testid="send-command"]');

    await this.page.waitForSelector('[data-testid="meeting-and-task-created"]', { timeout: 10000 });

    // Verify both calendar and task created
    const meetingCreated = await this.page.textContent('[data-testid="meeting-status"]');
    expect(meetingCreated).toContain('Meeting scheduled for 3:00 PM');

    const taskCreated = await this.page.textContent('[data-testid="task-status"]');
    expect(taskCreated).toContain('Follow-up task added to Notion');
  }

  async testMariaCrossPlatform() {
    await this.authPage.navigateTo('http://localhost:3000');
    await this.authPage.loginWithGoogle('maria.test@example.com');
    await this.authPage.selectPersona('maria');

    // Test bank transaction to business tracking
    await this.page.click('[data-testid="integrations-tab"]');

    // Connect Plaid for banking
    await this.page.click('[data-testid="connect-banks"]');
    await this.page.waitForSelector('[data-testid="banking-connected"]', { timeout: 10000 });

    // Test automatic expense categorization
    await this.page.click('[data-testid="voice-command-button"]');
    await this.page.fill('[data-testid="voice-input"]', 'Find Figma subscription in my transactions and categorize as business expense');
    await this.page.click('[data-testid="send-command"]');

    await this.page.waitForSelector('[data-testid="expense-processed"]', { timeout: 10000 });

    // Verify it appears in business expense tracking
    await this.page.click('[data-testid="integrations-tab"]');

    // Test e-commerce platform integration
    await this.page.click('[data-testid="connect-shopify"]');
    await this.page.waitForSelector('[data-testid="shopify-connected"]', { timeout: 10000 });

    // Test automated product update workflow
    await this.page.click('[data-testid="voice-command-button"]');
    await this.page.fill('[data-testid="voice-input"]', 'Update inventory levels for laptop sales and send customer notifications');
    await this.page.click('[data-testid="send-command"]');

    await this.page.waitForSelector('[data-testid="workflow-completed"]', { timeout: 10000 });

    // Verify cross-platform notifications work
    const notificationStatus = await this.page.textContent('[data-testid="notification-status"]');
    expect(notificationStatus).toContain('Customer notifications sent');
    expect(notificationStatus).toContain('Inventory updated');
  }

  async testAuthenticationConsistency() {
    // Test switching between personas
    await this.authPage.navigateTo('http://localhost:3000');
    await this.authPage.loginWithGoogle('alex.test@example.com');

    // Switch to Alex, use features
    await this.authPage.selectPersona('alex');
    await this.page.waitForSelector('[data-testid="alex-dashboard"]');

    // Test navigation persists
    await this.page.click('[data-testid="calendar-view"]');
    const calendarView = await this.page.textContent('[data-testid="calendar-events"]');
    expect(calendarView).toContain('Q3 Roadmap Sync');

    // Logout and verify clean session
    await this.page.click('[data-testid="logout-button"]');
    await this.page.waitForSelector('[data-testid="login-button"]');

    // Login should offer persona selection again
    await this.authPage.loginWithGoogle('maria.test@example.com');
    await this.page.waitForSelector('[data-testid="persona-selection"]');
  }
}

test.describe('Cross-Platform User Journey Tests', () => {
  let page: Page;
  let crossTest: CrossPlatformWorkflowTest;

  test.beforeEach(async ({ page: newPage }) => {
    page = newPage;
    crossTest = new CrossPlatformWorkflowTest(page);
    await crossTest.setupMultiPersonaEnvironment();
  });

  test('Alex workflow integrates Google Calendar and Notion', async () => {
    await crossTest.testAlexCrossPlatform();
  });

  test('Maria workflow integrates banking and business expense tracking', async () => {
    await crossTest.testMariaCrossPlatform();
  });

  test('Ben workflow integrates social media and e-commerce', async () => {
    await crossTest.testBenCrossPlatform();
  });

  test('Authentication and session management works consistently', async () => {
    await crossTest.testAuthenticationConsistency();
  });
});
    const categorizedExpense = await this.page.textContent('[data-testid="business-expenses"]');
    expect(categorizedExpense).toContain('Figma');
+    expect(categorizedExpense).toContain('Software & Tools');
+
+    // Test tax preparation export
+    await this.page.click('[data-testid="export-tax-data"]');
+    await this.page.waitForSelector('[data-testid="export-ready"]');
+
+    const exportStatus = await this.page.textContent('[data-testid="export-status"]');
+    expect(exportStatus).toContain('Tax export ready');
+  }
+
+  async testBenCrossPlatform() {
+    await this.authPage.navigateTo('http://localhost:3000');
+    await this.authPage.loginWithGoogle('ben.test@example.com');
+    await this.authPage.selectPersona('ben');
+
+    // Test social media to CRM integration
+    await this.page.click('[data-testid="integrations-tab"]
