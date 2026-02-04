import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://localhost:8000';

test.describe('Comprehensive Backend API Coverage', () => {

    test.describe('Authentication & User Management', () => {
        test('GET /health returns 200', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/health`);
            expect(response.ok()).toBeTruthy();
        });

        test('GET /api/v1/auth/status (unauthorized)', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/v1/auth/status`);
            // Expect 401 or similar if not logged in, or 200 with null user
            expect(response.status()).toBeLessThan(500);
        });
    });

    test.describe('Integrations Catalog', () => {
        test('GET /api/v1/integrations/catalog returns list', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/v1/integrations/catalog`);
            expect(response.ok()).toBeTruthy();
            const data = await response.json();
            expect(Array.isArray(data)).toBeTruthy();
        });

        test('GET /api/v1/integrations/catalog with search', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/v1/integrations/catalog?search=slack`);
            expect(response.ok()).toBeTruthy();
        });
    });

    test.describe('Workflows API', () => {
        test('GET /api/v1/workflow-ui/workflows returns list', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/v1/workflow-ui/workflows`);
            expect(response.ok()).toBeTruthy();
        });

        test('POST /api/v1/workflow-ui/workflows validation', async ({ request }) => {
            const response = await request.post(`${BACKEND_URL}/api/v1/workflow-ui/workflows`, {
                data: {} // Empty body
            });
            // If API is permissive, it might create an empty workflow.
            // If it returns 200, check if we got a valid workflow object back.
            if (response.status() === 200) {
                 const data = await response.json();
                 expect(data.workflow).toBeDefined();
                 expect(data.workflow.id).toBeDefined();
            } else {
                 expect(response.status()).toBeLessThan(500);
            }
        });
    });

    test.describe('AI & Intelligence', () => {
        test('GET /api/ai-workflows/providers', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/ai-workflows/providers`);
            expect(response.ok()).toBeTruthy();
        });

        test('POST /api/ai-workflows/nlu/parse validation', async ({ request }) => {
            const response = await request.post(`${BACKEND_URL}/api/ai-workflows/nlu/parse`, {
                data: { text: '' }
            });
            expect(response.status()).not.toBe(500);
        });
    });

    test.describe('Memory & Documents', () => {
        test('POST /api/v1/memory store', async ({ request }) => {
            const response = await request.post(`${BACKEND_URL}/api/v1/memory`, {
                data: { key: 'test-key', value: { foo: 'bar' } }
            });
            expect(response.ok()).toBeTruthy();
        });

        test('GET /api/v1/memory retrieve', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/v1/memory/test-key`);
            expect(response.ok()).toBeTruthy();
        });

        test('GET /api/documents/search empty', async ({ request }) => {
             const response = await request.get(`${BACKEND_URL}/api/documents/search`);
             expect(response.status()).toBeLessThan(500);
        });
    });

    test.describe('System & Health', () => {
        test('GET /api/integrations/stats', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/integrations/stats`);
            expect(response.ok()).toBeTruthy();
        });

        test('GET /api/voice/status', async ({ request }) => {
            const response = await request.get(`${BACKEND_URL}/api/voice/status`);
            expect(response.ok()).toBeTruthy();
        });
    });
});
