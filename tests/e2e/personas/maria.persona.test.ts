import { test, expect, type Page } from '@playwright/test';
import { TestHelpers, AuthPage, BaseE2ETest, type TestUser } from '../utils/test-utils';

class MariaPersonaTest extends BaseE2ETest {
  private authPage: AuthPage;

  constructor(page: Page, user: TestUser) {
    super(page, user);
    this.authPage = new AuthPage(page);
  }

  async loadPersona() {
    await this.authPage.navigateTo('http://localhost:3000');
    await this.authPage.loginWithGoogle('maria.test@example.com');
    await this.authPage.selectPersona('maria');
    await this.authPage.completeOnboarding('maria');
  }

  async checkBudgetOverview() {
    await this.page.click('[data-testid="financial-overview-tab"]');
    await this.page.waitForSelector('[data-testid="budget-dashboard"]', { timeout: 10000 });

    const budgetStatus = await this.page.textContent('[data-testid="budget-summary"]');
    expect(budgetStatus).toContain('$');
    expect(budgetStatus).toMatch(/\$\d+,?(\d{3})?(\.\d{2})?/);
  }

  async analyzeMonthlyExpenses() {
    await this.page.click('[data-testid="expense-analysis"]');
    await this.page.waitForSelector('[data-testid="expense-breakdown"]', { timeout: 10000 });

    await this.page.click('[data-testid="month-selector"]');
    await this.page.selectOption('[data-testid="month-selector"]', 'current-month');

    const expenseDetails = await this.page.textContent('[data-testid="top-expenses"]');
    expect(expenseDetails).toContain('Software');
    expect(expenseDetails).toContain('Tools');

    const budgetStatus = await this.page.textContent('[data-testid="budget-status"]');
    expect(budgetStatus).toMatch(/60%|Software.*60%/);
  }

  async setUpSpendingAlert() {
    await this.page.click('[data-testid="alerts-tab"]');
    await this.page.waitForSelector('[data-testid="alert-setup"]');

    await this.page.fill('[data-testid="alert-threshold"]', '1000');
    await this.page.selectOption('[data-testid="alert-category"]', 'dining');
    await this.page.click('[data-testid="enable-alert"]');

    const confirmation = await this.page.textContent('[data-testid="alert-confirmation"]');
    expect(confirmation).toContain('alert configured');
  }

  async createSavingsGoals() {
    await this.page.click('[data-testid="goals-tab"]');
    await this.page.click('[data-testid="add-goal"]');

    await this.page.fill('[data-testid="goal-title"]', 'Emergency Fund');
    await this.page.fill('[data-testid="goal-amount"]', '5000');
    await this.page.fill('[data-testid="goal-timeline"]', '12');
    await this.page.click('[data-testid="create-goal"]');

    await this.page.waitForSelector('[data-testid="goal-created"]', { timeout: 5000 });
    const confirmation = await this.page.textContent('[data-testid="goal-progress"]');
    expect(confirmation).toContain('$0 / $5,000');
  }

  async scheduleBillReminders() {
    await this.page.click('[data-testid="reminders-tab"]');
    await this.page.click('[data-testid="create-reminder"]');

    await this.page.fill('[data-testid="bill-name"]', 'Credit Card Payment');
    await this.page.fill('[data-testid="reminder-date"]', '15');
    await this.page.selectOption('[data-testid="reminder-frequency"]', 'monthly');
    await this.page.click('[data-testid="save-reminder"]');

    const confirmation = await this.page.textContent('[data-testid="reminder-confirmation"]');
    expect(confirmation).toContain('reminder saved');
  }
}

test.describe('Maria Rodriguez - Financial Optimizer Persona', () => {
  let page: Page;
  let mariaTest: MariaPersonaTest;

  test.beforeEach(async ({ page: newPage }) => {
    page = newPage;
    mariaTest = new MariaPersonaTest(page, {
      id: 'test-maria-001',
      name: 'Maria Rodriguez',
      email: 'maria.test@example.com',
      persona: 'financial_optimizer'
    });

    await mariaTest.setupTestEnvironment();
    await mariaTest.loadPersona();
  });

  test('Budget overview displays financial health', async () => {
    await mariaTest.checkBudgetOverview();
  });

  test('Expense categorization and analysis works correctly', async () => {
    await mariaTest.analyzeMonthlyExpenses
