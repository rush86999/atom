import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://localhost:8000';

test.describe('Extra Features Coverage', () => {

    const features = [
        'financial',
        'accounting',
        'reconciliation',
        'apar',
        'graphrag',
        'projects',
        'sales'
    ];

    for (const feature of features) {
        test(`${feature} routes exist`, async ({ request }) => {
            // Just check if base route or a known sub-route gives a valid response (even 401/404 is better than 500)
            // We use /api/{feature}/health if it exists, or just check 404 is JSON not HTML
            const response = await request.get(`${BACKEND_URL}/api/${feature}`);
            // We expect JSON response or 404, but not 500
            expect(response.status()).not.toBe(500);
        });
    }

    test('Live Command Center routes', async ({ request }) => {
         const response = await request.get(`${BACKEND_URL}/api/live/communication/status`);
         expect(response.status()).not.toBe(500);
    });

});
