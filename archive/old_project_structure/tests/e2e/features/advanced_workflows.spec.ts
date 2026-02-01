import { test, expect } from '@playwright/test';

test.describe('Advanced Workflow Features', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/workflows');
  });

  test('Create workflow with branching logic', async ({ page }) => {
    await page.click('[data-testid="create-workflow"]');
    await page.fill('[data-testid="workflow-name"]', 'Branching Test');

    // Add trigger
    await page.click('[data-testid="add-trigger"]');
    await page.selectOption('[data-testid="trigger-select"]', 'webhook');

    // Add Condition
    await page.click('[data-testid="add-step"]');
    await page.selectOption('[data-testid="step-type"]', 'condition');
    await page.fill('[data-testid="condition-logic"]', 'value > 100');

    // True Branch
    await page.click('[data-testid="branch-true-add-step"]');
    await page.selectOption('[data-testid="step-type"]', 'email');
    await page.fill('[data-testid="email-subject"]', 'High Value');

    // False Branch
    await page.click('[data-testid="branch-false-add-step"]');
    await page.selectOption('[data-testid="step-type"]', 'slack');
    await page.fill('[data-testid="slack-message"]', 'Low Value');

    await page.click('[data-testid="save-workflow"]');
    await expect(page.locator('[data-testid="success-message"]')).toContainText('Workflow saved');
  });

  test('Create workflow with looping', async ({ page }) => {
    await page.click('[data-testid="create-workflow"]');

    await page.click('[data-testid="add-step"]');
    await page.selectOption('[data-testid="step-type"]', 'loop');
    await page.fill('[data-testid="loop-collection"]', 'items');

    await page.click('[data-testid="loop-body-add-step"]');
    await page.selectOption('[data-testid="step-type"]', 'process_item');

    await page.click('[data-testid="save-workflow"]');
    await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
  });

  test('Handle workflow errors gracefully', async ({ page }) => {
    await page.goto('http://localhost:3000/workflows/history');

    // Click on a failed workflow run (assuming one exists or we mock it)
    // Here we might need to mock the backend response to show a failed run
    await page.route('**/api/workflows/history', async route => {
        const json = {
            runs: [{ id: '1', status: 'failed', error: 'API Timeout', name: 'Test Run' }]
        };
        await route.fulfill({ json });
    });

    await page.reload();
    await page.click('[data-testid="workflow-run-1"]');

    await expect(page.locator('[data-testid="error-details"]')).toContainText('API Timeout');
    await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();

    await page.click('[data-testid="retry-button"]');
    await expect(page.locator('[data-testid="retry-started"]')).toBeVisible();
  });

  test('Workflow versioning', async ({ page }) => {
    await page.click('[data-testid="workflow-1"]');
    await page.click('[data-testid="version-history"]');

    await expect(page.locator('[data-testid="version-list"]')).toBeVisible();
    await page.click('[data-testid="restore-version"]');
    await expect(page.locator('[data-testid="restore-success"]')).toBeVisible();
  });

  test('Workflow variable usage', async ({ page }) => {
    await page.click('[data-testid="create-workflow"]');

    await page.click('[data-testid="variables-panel"]');
    await page.click('[data-testid="add-variable"]');
    await page.fill('[data-testid="var-name"]', 'API_KEY');
    await page.fill('[data-testid="var-value"]', '12345');
    await page.click('[data-testid="save-variable"]');

    await expect(page.locator('[data-testid="var-list"]')).toContainText('API_KEY');
  });

  test('Parallel execution configuration', async ({ page }) => {
    await page.click('[data-testid="create-workflow"]');
    await page.click('[data-testid="workflow-settings"]');

    await page.tick('[data-testid="enable-parallel"]');
    await page.fill('[data-testid="max-concurrency"]', '5');
    await page.click('[data-testid="save-settings"]');

    await expect(page.locator('[data-testid="settings-saved"]')).toBeVisible();
  });

  test('Workflow template usage', async ({ page }) => {
    await page.click('[data-testid="use-template"]');
    await page.click('[data-testid="template-onboarding"]');
    await page.click('[data-testid="apply-template"]');

    await expect(page.locator('[data-testid="workflow-canvas"]')).not.toBeEmpty();
    await expect(page.locator('[data-testid="workflow-name"]')).toHaveValue(/Onboarding/);
  });

  test('Scheduled workflow setup', async ({ page }) => {
      await page.click('[data-testid="create-workflow"]');
      await page.click('[data-testid="add-trigger"]');
      await page.selectOption('[data-testid="trigger-select"]', 'schedule');
      await page.fill('[data-testid="cron-expression"]', '0 9 * * 1-5'); // Mon-Fri 9am
      await page.click('[data-testid="save-workflow"]');
      await expect(page.locator('[data-testid="cron-readable"]')).toContainText('At 09:00 AM, Monday through Friday');
  });

  test('Workflow drag and drop', async ({ page }) => {
      await page.click('[data-testid="create-workflow"]');

      const source = page.locator('[data-testid="node-action"]');
      const target = page.locator('[data-testid="canvas-drop-zone"]');

      await source.dragTo(target);

      await expect(page.locator('[data-testid="canvas-node"]')).toBeVisible();
  });

  test('Workflow validation errors', async ({ page }) => {
      await page.click('[data-testid="create-workflow"]');
      // Try to save empty workflow
      await page.click('[data-testid="save-workflow"]');

      await expect(page.locator('[data-testid="validation-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="validation-error"]')).toContainText('Trigger is required');
  });
});
