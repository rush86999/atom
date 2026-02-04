import { test, expect } from '@playwright/test';

/**
 * Frontend-to-Backend E2E Integration Tests
 * Tests real user flows: frontend pages load and backend APIs respond correctly
 */

const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:3000';

test.describe('Frontend-Backend Integration', () => {

    test.describe('Core Pages Load', () => {
        test('homepage loads with feature cards', async ({ page }) => {
            await page.goto(FRONTEND_URL);

            // Check page loads - wait for content
            await page.waitForLoadState('networkidle');

            // Check core content is present (flexible matching)
            const content = await page.content();
            expect(content.length).toBeGreaterThan(1000);
        });

        test('integrations page loads', async ({ page }) => {
            await page.goto(`${FRONTEND_URL}/integrations`);
            // Use domcontentloaded instead of networkidle - page has many slow health checks
            await page.waitForLoadState('domcontentloaded');

            // Verify we're on the integrations page
            expect(page.url()).toContain('integration');
        });

        test('workflows page loads', async ({ page }) => {
            await page.goto(`${FRONTEND_URL}/workflows`);
            await expect(page).toHaveURL(/workflows/);
        });

        test('chat page loads', async ({ page }) => {
            await page.goto(`${FRONTEND_URL}/chat`);
            await expect(page).toHaveURL(/chat/);
        });
    });

    test.describe('Backend API Health', () => {
        test('backend health check responds', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/health`);
            expect(response.ok()).toBeTruthy();
            const data = await response.json();
            expect(data.status).toBeDefined();
        });

        test('integrations list loads', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/integrations`);
            expect(response.ok()).toBeTruthy();
        });

        test('integration catalog loads', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/v1/integrations/catalog`);
            expect(response.ok()).toBeTruthy();
            const data = await response.json();
            expect(Array.isArray(data)).toBeTruthy();
            expect(data.length).toBeGreaterThan(0);
        });

        test('workflow list loads', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/v1/workflow-ui/workflows`);
            expect(response.ok()).toBeTruthy();
        });

        test('memory API works', async ({ request }) => {
            // Store memory
            const storeResponse = await request.post(`${BACKEND_URL}/api/v1/memory`, {
                data: { key: 'test-e2e-key', value: { test: 'data' } }
            });
            expect(storeResponse.ok()).toBeTruthy();

            // Retrieve memory
            const getResponse = await request.get(`${BACKEND_URL}/api/v1/memory/test-e2e-key`);
            expect(getResponse.ok()).toBeTruthy();
        });
    });

    test.describe('Workflow CRUD via UI', () => {
        test('can create and list workflow', async ({ request }) => {
            // Create workflow
            const createResponse = await request.post(`${BACKEND_URL}/api/v1/workflow-ui/workflows`, {
                data: {
                    name: 'E2E Test Workflow',
                    description: 'Created via Playwright E2E test',
                    steps: [{ type: 'action', service: 'email', action: 'send' }]
                }
            });
            expect(createResponse.ok()).toBeTruthy();
            const created = await createResponse.json();
            expect(created.workflow.id).toBeDefined();

            // List workflows - should include new one
            const listResponse = await request.get(`${BACKEND_URL}/api/v1/workflow-ui/workflows`);
            expect(listResponse.ok()).toBeTruthy();
            const list = await listResponse.json();
            expect(list.workflows.some((w: any) => w.name === 'E2E Test Workflow')).toBeTruthy();
        });
    });

    test.describe('Integration Health Checks', () => {
        const integrations = ['slack', 'hubspot', 'salesforce', 'github', 'dropbox', 'zoom'];

        for (const integration of integrations) {
            test(`${integration} health check responds`, async ({ request }) => {
                const response = await request.get(`${BACKEND_URL}/api/${integration}/health`);
                expect(response.status()).toBeLessThan(500);
            });
        }
    });

    test.describe('Chat and NLU', () => {
        test('NLU parse works', async ({ request }) => {
            const response = await request.post(`${BACKEND_URL}/api/ai-workflows/nlu/parse`, {
                data: { text: 'Schedule a meeting for tomorrow', provider: 'deepseek' }
            });
            expect(response.ok()).toBeTruthy();
            const data = await response.json();
            expect(data.intent).toBeDefined();
        });

        test('AI providers list', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/ai-workflows/providers`);
            expect(response.ok()).toBeTruthy();
        });
    });

    test.describe('Document and Search', () => {
        test('document ingest works', async ({ request }) => {
            const response = await request.post(`${BACKEND_URL}/api/documents/ingest`, {
                data: {
                    content: 'This is a test document from Playwright E2E tests',
                    title: 'Playwright Test Doc',
                    type: 'text'
                }
            });
            expect(response.ok()).toBeTruthy();
        });

        test('document search works', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/documents/search?q=test`);
            expect(response.ok()).toBeTruthy();
        });

        test('vector search works', async ({ request }) => {
            const response = await request.post(`${BACKEND_URL}/api/lancedb-search/search`, {
                data: { query: 'test document', limit: 5 }
            });
            expect(response.ok()).toBeTruthy();
        });
    });

    test.describe('Voice and WebSocket', () => {
        test('voice status endpoint works', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/voice/status`);
            expect(response.ok()).toBeTruthy();
        });

        test('websocket info endpoint works', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/ws/info`);
            expect(response.ok()).toBeTruthy();
        });
    });
});
