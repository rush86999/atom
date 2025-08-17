import { test, expect, type Page } from '@playwright/test';
import { TestHelpers, AuthPage, BaseE2ETest, type TestUser } from '../utils/test-utils';

class BenPersonaTest extends BaseE2ETest {
  private authPage: AuthPage;

  constructor(page: Page, user: TestUser) {
    super(page, user);
    this.authPage = new AuthPage(page);
  }

  async loadPersona() {
    await this.authPage.navigateTo('http://localhost:3000');
    await this.authPage.loginWithGoogle('ben.test@example.com');
    await this.authPage.selectPersona('ben');
    await this.authPage.completeOnboarding('ben');
  }

  async performCompetitorAnalysis() {
    await this.page.click('[data-testid="market-intel-tab"]');
    await this.page.waitForSelector('[data-testid="competitor-analysis"]', { timeout: 10000 });

    await this.page.click('[data-testid="request-competitor-analysis"]');
    await this.page.waitForSelector('[data-testid="analysis-results"]', { timeout: 15000 });

    const analysis = await this.page.textContent('[data-testid="competitor-findings"]');
    expect(analysis).toContain('ShopifyPro');
    expect(analysis).toContain('CartEasy');
    expect(analysis).toContain('negative mentions');
  }

  async createSocialMediaContent() {
    await this.page.click('[data-testid="content-tab"]');
    await this.page.waitForSelector('[data-testid="content-creator"]');

    await this.page.fill('[data-testid="content-prompt"]', 'Write two tweets about our new free shipping offer');
    await this.page.click('[data-testid="generate-content"]');

    await this.page.waitForSelector('[data-testid="content-output"]', { timeout: 10000 });

    const content = await this.page.textContent('[data-testid="generated-tweets"]');
    expect(content).toContain('free shipping');
    expect(content).toContain('limited time');

    await this.page.click('[data-testid="schedule-tweets"]');
    const confirmation = await this.page.textContent('[data-testid="scheduling-confirmation"]');
    expect(confirmation).toContain('scheduled for 1 PM and 4 PM');
  }

  async analyzeLegalDocument() {
    await this.page.click('[data-testid="documents-tab"]');
    await this.page.click('[data-testid="analyze-document"]');

    await this.page.fill('[data-testid="document-url"]', 'https://example.com/partnership-agreement.pdf');
    await this.page.click('[data-testid="start-analysis"]');

    await this.page.waitForSelector('[data-testid="legal-analysis"]', { timeout: 15000 });

    const analysis = await this.page.textContent('[data-testid="analysis-summary"]');
    expect(analysis).toContain('Section 5');
    expect(analysis).toContain('Indemnification');
    expect(analysis).toContain('heavily one-sided');

    const recommendations = await this.page.textContent('[data-testid="recommendations"]');
    expect(recommendations).toContain('detailed comments');
  }

  async setupCustomerSupportWorkflow() {
    await this.page.click('[data-testid="workflows-tab"]');
    await this.page.click('[data-testid="create-workflow"]');

    await this.page.fill('[data-testid="workflow-name"]', 'Refund Request Handler');
    await this.page.fill('[data-testid="trigger-condition"]', 'Subject contains "refund"');
    await this.page.click('[data-testid="add-action"]');
    await this.page.selectOption('[data-testid="action-type"]', 'create-trello-card');
    await this.page.fill('[data-testid="card-title"]', 'Refund Request - Priority');
    await this.page.fill('[data-testid="card-assignee"]', 'ben@example.com');

    await this.page.click('[data-testid="save-workflow"]');

    const confirmation = await this.page.textContent('[data-testid="workflow-confirmation"]');
    expect(confirmation).toContain('workflow enabled');

    // Test triggering the workflow
    await this.page.fill('[data-testid="test-subject"]', 'Urgent refund needed for order #123');
    await this.page.click('[data-testid="test-trigger"]');

    await this.page.waitForSelector('[data-testid="test-results"]', { timeout: 5000 });
    const results = await this.page.textContent('[data-testid="test-results"]');
    expect(results).toContain('Trello card created');
  }
}

test.describe('Ben Carter - Solopreneur Persona', () => {
  let page: Page;
  let benTest: BenPersonaTest;

  test.beforeEach(async ({ page: newPage }) => {
