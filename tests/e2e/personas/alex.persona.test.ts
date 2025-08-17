import { test, expect, type Page } from '@playwright/test';
import { TestHelpers, AuthPage, BaseE2ETest, type TestUser } from '../utils/test-utils';

class AlexPersonaTest extends BaseE2ETest {
  private authPage: AuthPage;

  constructor(page: Page, user: TestUser) {
    super(page, user);
    this.authPage = new AuthPage(page);
  }

  async loadPersona() {
    await this.authPage.navigateTo('http://localhost:3000');
    await this.authPage.loginWithGoogle('alex.test@example.com');
    await this.authPage.selectPersona('alex');
    await this.authPage.completeOnboarding('alex');
  }

  async checkMorningBriefing() {
    await this.page.click('[data-testid="voice-command-button"]');
    await this.page.fill('[data-testid="voice-input"]', 'Good morning Atom, what\'s my agenda today?');
    await this.page.click('[data-testid="send-command"]');

    await this.page.waitForSelector('[data-testid="morning-summary"]', { timeout: 10000 });

    const summary = await this.page.textContent('[data-testid="morning-summary"]');
    expect(summary).toContain('meetings');
    expect(summary).toMatch(/\d+\s+meetings?/);
    expect(summary).toMatch(/high.*priority.*task/i);
  }

  async prepareForMeeting() {
    await this.page.click('[data-testid="meeting-prep-button"]');
    await this.page.waitForSelector('[data-testid="meeting-selector"]');

    await this.page.click('[data-testid="meeting-q3-roadmap-sync"]');
    await this.page.click('[data-testid="prepare-meeting"]');

    await this.page.waitForSelector('[data-testid="prep-results"]', { timeout: 15000 });

    const prepContent = await this.page.textContent('[data-testid="prep-results"]');
    expect(prepContent).toContain('roadmap');
    expect(prepContent).toContain('notes');
    expect(prepContent).toContain('context');
  }

  async createTaskInMeeting() {
    await this.page.click('[data-testid="voice-command-button"]');
    await this.page.fill('[data-testid="voice-input"]', 'Create task: Follow up with marketing on launch campaign assets by end of week');
    await this.page.click('[data-testid="send-command"]');

    await this.page.waitForSelector('[data-testid="task-confirmation"]', { timeout: 10000 });

    const confirmation = await this.page.textContent('[data-testid="task-confirmation"]');
    expect(confirmation).toContain('task created');

    await this.page.click('[data-testid="tasks-tab"]');
    await this.page.waitForSelector('[data-testid="tasks-list"]');
    const tasksList = await this.page.textContent('[data-testid="tasks-list"]');
    expect(tasksList).toContain('Follow up with marketing');
  }

  async scheduleMeeting() {
    await this.page.click('[data-testid="schedule-meeting-button"]');
    await this.page.waitForSelector('[data-testid="meeting-scheduler"]');

    await this.page.fill('[data-testid="meeting-title"]', 'UI review');
    await this.page.fill('[data-testid="attendees"]', 'Sarah, design lead');
    await this.page.fill('[data-testid="duration"]', '30');

    await this.page.click('[data-testid="find-available-slot"]');
    await this.page.waitForSelector('[data-testid="available-slots"]', { timeout: 10000 });

    await this.page.click('[data-testid="select-slot-3:30-PM"]');
    await this.page.click('[data-testid="send-invitation"]');

    const confirmation = await this.page.textContent('[data-testid="meeting-scheduled"]');
    expect(confirmation).toContain('meeting scheduled');
    expect(confirmation).toContain('3:30 PM');
  }

  async searchInformation() {
    await this.page.click('[data-testid="search-button"]');
    await this.page.waitForSelector('[data-testid="search-input"]');

    await this.page.fill('[data-testid="search-box"]', 'payment gateway decision');
    await this.page.click('[data-testid="search-all"]');

    await this.page.waitForSelector('[data-testid="search-results"]', { timeout: 10000 });

    const results = await this.page.textContent('[data-testid="search-results"]');
    expect(results).toContain('Stripe');
    expect(results).toContain('Product Sync');
  }
+}

test.describe('Alex Chen - Busy Professional Persona', () => {
  let page: Page;
  let alexTest: AlexPersonaTest;

  test.beforeEach(async
