/** Real MSW node interception; no backend or device is started. */
import http from 'http';
import { rest } from 'msw';
import { mockServer, overrideHandlers, resetMockHandlers } from '../mockHandlers';
import { mockAgents } from '../mockData';

const apiUrlKey = 'EXPO_PUBLIC_API_URL';
const base = process.env[apiUrlKey] || 'http://localhost:8000';

function get(path: string): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const request = http.get(base + path, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk: Buffer) => chunks.push(chunk));
      response.on('end', () => {
        try {
          resolve({ status: response.statusCode ?? 0, body: JSON.parse(Buffer.concat(chunks).toString()) });
        } catch (error) {
          reject(error);
        }
      });
    });
    request.on('error', reject);
  });
}

beforeAll(() => mockServer.listen({ onUnhandledRequest: 'error' }));
afterEach(() => resetMockHandlers());
afterAll(() => mockServer.close());

test('real list handler returns the fixture records', async () => {
  const result = await get('/api/agents');
  expect(result.status).toBe(200);
  expect(result.body).toEqual({ success: true, data: mockAgents });
});

test('an explicit error override wins and reset restores the default', async () => {
  overrideHandlers(rest.get(base + '/api/agents', (_request, response, context) =>
    response(context.status(503), context.json({ success: false, error: 'controlled unavailable' }))
  ));
  expect(await get('/api/agents')).toEqual({
    status: 503,
    body: { success: false, error: 'controlled unavailable' },
  });
  resetMockHandlers();
  expect((await get('/api/agents')).status).toBe(200);
});

test('unknown agent remains a genuine not-found response', async () => {
  const result = await get('/api/agents/not-a-fixture-agent');
  expect(result.status).toBe(404);
  expect(result.body).toEqual({ success: false, error: 'Agent not found' });
});
