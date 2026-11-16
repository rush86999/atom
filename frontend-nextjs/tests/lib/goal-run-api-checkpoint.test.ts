import { resolveCheckpoint } from '@/lib/goal-run-api';
import { apiClient } from '@/lib/api-client';

jest.mock('@/lib/api-client', () => ({
  apiClient: { fetch: jest.fn() },
}));

const fetchMock = apiClient.fetch as jest.Mock;

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

beforeEach(() => {
  fetchMock.mockReset();
});

it('returns the verified resumed outcome and posts the exact decision', async () => {
  fetchMock.mockResolvedValue(response(200, {
    success: true,
    resumed: true,
    checkpoint: { id: 'hitl-1', status: 'approved' },
  }));

  const result = await resolveCheckpoint('run-1', 'hitl-1', true, 'looks right');

  expect(result.resumed).toBe(true);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe('/api/goal-runs/run-1/checkpoints/hitl-1/resolve');
  expect(init).toMatchObject({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  expect(JSON.parse(init.body)).toEqual({
    approved: true,
    guidance: 'looks right',
  });
});

it('surfaces the structured stale-checkpoint refusal with its status', async () => {
  fetchMock.mockResolvedValue(response(409, {
    detail: {
      error: {
        code: 'CHECKPOINT_STALE',
        message: 'This checkpoint is no longer the run’s current wait.',
      },
    },
  }));

  await expect(resolveCheckpoint('run-1', 'hitl-1', true))
    .rejects.toMatchObject({
      message: expect.stringContaining('no longer'),
      status: 409,
    });
});

it.each([
  { resumed: false, reason: 'run is cancelled, not waiting' },
  { success: true, reason: 'wait already consumed' },
  { success: true },
])('does not announce a resume for a 200 body without resumed=true %#', async (body) => {
  fetchMock.mockResolvedValue(response(200, body));

  await expect(resolveCheckpoint('run-1', 'hitl-1', true))
    .rejects.toMatchObject({
      message: expect.stringContaining(body.reason || 'no longer current'),
      status: 409,
    });
});
