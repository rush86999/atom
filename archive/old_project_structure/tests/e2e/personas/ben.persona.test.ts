import { test, expect, Page } from '@playwright/test';

test.describe('Ben Carter - Solopreneur Test Suite', () => {
  let page: Page;

  test.beforeEach(async ({ page: newPage }) => {
    page = newPage;
    await page.goto('http://localhost:3000');
  });

  test('Ben completes business onboarding', async () => {
    await page.goto('http://localhost:3000/signup');
    await page.fill('[data-testid="email-input"]', 'ben.business@example.com');
    await page.fill('[data-testid="name-input"]', 'Ben Carter');
    await page.fill('[data-testid="password-input"]', 'GrowthMindset1!');
    await page.click('[data-testid="submit-register"]');

    await page.click('[data-testid="persona-ben"]');
    await page.fill('[data-testid="business-name"]', 'Carter Consulting');
    await page.fill('[data-testid="industry"]', 'Consulting');
    await page.click('[data-testid="complete-onboarding"]');

    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('h1')).toContainText(/Welcome, Ben!/);
  });

  test('Ben runs competitor analysis', async () => {
    await page.goto('http://localhost:3000/business/analysis');
    await page.fill('[data-testid="competitor-url"]', 'example-competitor.com');
    await page.click('[data-testid="run-analysis"]');

    await expect(page.locator('[data-testid="analysis-loading"]')).toBeVisible();
    await expect(page.locator('[data-testid="analysis-results"]')).toBeVisible({ timeout: 15000 });

    await expect(page.locator('[data-testid="swot-analysis"]')).toBeVisible();
    await expect(page.locator('[data-testid="pricing-comparison"]')).toBeVisible();
  });

  test('Ben automates social media content', async () => {
    await page.goto('http://localhost:3000/marketing/social');
    await page.click('[data-testid="create-campaign"]');

    await page.fill('[data-testid="campaign-topic"]', 'Productivity Tips');
    await page.selectOption('[data-testid="platform-select"]', 'linkedin');
    await page.click('[data-testid="generate-content"]');

    await expect(page.locator('[data-testid="generated-post"]')).toBeVisible();
    await page.click('[data-testid="schedule-post"]');
    await expect(page.locator('[data-testid="success-message"]')).toContainText('Post scheduled');
  });

  test('Ben reviews legal documents', async () => {
    await page.goto('http://localhost:3000/legal/review');

    // Simulate file upload
    await page.setInputFiles('input[type="file"]', {
        name: 'contract.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from('fake pdf content')
    });

    await page.click('[data-testid="analyze-document"]');

    await expect(page.locator('[data-testid="risk-assessment"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="key-clauses"]')).toBeVisible();
  });

  test('Ben sets up customer support workflow', async () => {
    await page.goto('http://localhost:3000/workflows/create');

    await page.fill('[data-testid="workflow-name"]', 'Support Auto-Reply');
    await page.selectOption('[data-testid="trigger-type"]', 'email_received');
    await page.fill('[data-testid="filter-subject"]', 'Support');

    await page.click('[data-testid="add-action"]');
    await page.selectOption('[data-testid="action-type"]', 'generate_reply');
    await page.click('[data-testid="save-workflow"]');

    await expect(page.locator('[data-testid="workflow-active-badge"]')).toBeVisible();
  });

  test('Ben manages leads in CRM', async () => {
    await page.goto('http://localhost:3000/crm/leads');
    await page.click('[data-testid="add-lead"]');

    await page.fill('[data-testid="lead-name"]', 'Acme Corp');
    await page.fill('[data-testid="lead-email"]', 'contact@acme.com');
    await page.selectOption('[data-testid="lead-status"]', 'new');
    await page.click('[data-testid="save-lead"]');

    await expect(page.locator('[data-testid="lead-row-acme-corp"]')).toBeVisible();
  });

  test('Ben generates invoice', async () => {
    await page.goto('http://localhost:3000/finance/invoices');
    await page.click('[data-testid="create-invoice"]');

    await page.selectOption('[data-testid="client-select"]', 'Acme Corp');
    await page.fill('[data-testid="invoice-item"]', 'Consulting Services');
    await page.fill('[data-testid="invoice-amount"]', '2000');
    await page.click('[data-testid="send-invoice"]');

    await expect(page.locator('[data-testid="invoice-sent-success"]')).toBeVisible();
  });

  test('Ben checks analytics dashboard', async () => {
    await page.goto('http://localhost:3000/dashboard');

    await expect(page.locator('[data-testid="revenue-chart"]')).toBeVisible();
    await expect(page.locator('[data-testid="lead-conversion-rate"]')).toBeVisible();
  });
});
