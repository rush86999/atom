import { test, expect, _electron as electron } from '@playwright/test';

test.describe('Alex - Desktop Growth Professional', () => {
  let electronApp: any;
  let window: any;

  test.beforeAll(async () => {
    electronApp = await electron.launch({
      args: ['./desktop-app'],
      cwd: './atomic-desktop'
    });
    window = await electronApp.firstWindow();
  });

  test.afterAll(async () => {
    await electronApp.close();
  });

  test('Alex completes desktop onboarding', async () => {
    await window.click('[data-testid="persona-alex-professional"]');
    await window.fill('[data-testid="profile-name"]', 'Alex Chen');
    await window.selectOption('[data-testid="profile-industry"]', 'Technology');
    await window.fill('[data-testid="profile-title"]', 'Senior Product Manager');
    await window.click('[data-testid="continue-desktop-setup"]');

    await window.waitForSelector('[data-testid="alex-dashboard-desktop"]');
  });

  test('Alex creates productivity dashboard widget', async () => {
    await window.click('[data-testid="add-widget-button"]');
    await window.click('[data-testid="widget-productivity"]');
    await window.fill('[data-testid="widget-name"]', 'Daily Focus Metrics');
    await window.selectOption('[data-testid="metric-type"]', 'tasks_completed');
    await window.click('[data-testid="save-widget"]');

    await window.waitForSelector('[data-testid="productivity-widget-active"]');
  });

  test('Alex sets up desktop voice commands', async () => {
    await window.click('[data-testid="voice-settings"]');
    await window.check('[data-testid="enable-voice-commands"]');
    await window.selectOption('[data-testid="voice-hotkey"]', 'Cmd+Shift+Space');

    // Test voice activation
    await window.keyboard.press('Meta+Shift+Space');
    await window.waitForSelector('[data-testid="voice-input-active"]');
  });

  test('Alex configures calendar integration', async () => {
    await window.click('[data-testid="integrate-calendar"]');
    await window.click('[data-testid="auth-google-calendar"]');

    // Mock OAuth flow
    await window.fill('[data-testid="mock-google-email"]', 'alex@company.com');
    await window.click('[data-testid="grant-permissions"]');

    await window.waitForSelector('[data-testid="calendar-sync-complete"]');
  });

  test('Alex creates automated workflow', async () => {
    await window.click('[data-testid="automation-center"]');
    await window.click('[data-testid="create-workflow"]');

    // Configure workflow trigger
    await window.fill('[data-testid="workflow-name"]', 'Morning Routine');
    await window.selectOption('[data-testid="trigger-time"]', '08:00');

    // Add actions
    await window.click('[data-testid="add-action-media"]');
    await window.click('[data-testid="action-start-notion"]');
    await window.click('[data-testid="action-open-calendar"]');

    await window.click('[data-testid="save-workflow"]');
    await window.waitForSelector('[data-testid="workflow-active-desktop"]');
  });
  +
    test('Alex uses quick actions', async () => {
      // Global keyboard shortcut
      await window.keyboard.press('Meta+Shift+A');
      await window.waitForSelector('[data-testid="quick-add-modal"]');

      await window.type('[data-testid="quick-note-input"]', 'Schedule Q2 review meeting');
      await window.click('[data-testid="quick-add-task"]');

      await window.waitForSelector('[data-testid="task-created-notification"]');
    });

  test('Alex views productivity insights', async () => {
    await window.click('[data-testid="insight-center"]');

    // Check daily insights
    const productivityScore = await window.textContent('[data-testid="productivity-score"]');
    expect(productivityScore).toMatch(/\d{1,3}%/);

    // View weekly trends
    await window.click('[data-testid="weekly-insights"]');
    const trendChart = await window.textContent('[data-testid="trend-chart"]');
    expect(trendChart).toContain('|');

    // Get AI recommendations
    await window.click('[data-testid="ai-recommendation"]');
    const recs = await window.textContent('[data-testid="recommendation-list"]');
    expect(recs).toContain('optimize');
  });
});
