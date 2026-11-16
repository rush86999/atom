/**
 * goal-run-api — the shared error-body reader behind every exported refusal.
 *
 * Root cause: production installs core.error_handler.http_exception_handler,
 * which returns `HTTPException.detail` DIRECTLY as the response body. A
 * structured goal-run refusal (`detail={"error": {"code", "message"}, ...}`)
 * is therefore TOP-LEVEL in production, while a bare FastAPI app (no custom
 * handler) nests the same detail under `detail`. The shared reader only knew
 * the nested/string forms, so a real server refusal became a generic status
 * fallback in the UI.
 *
 * These tests drive the existing exported readers and pin both wire shapes to
 * the same human message, status and a single request. Non-string/malformed
 * envelopes must fall back — never a JSON object dump.
 */
jest.mock('../api-client', () => ({
  apiClient: { fetch: jest.fn() },
}));

import { apiClient } from '../api-client';
import {
  clearGoalUtility,
  createGoal,
  setGoalUtility,
  type UtilityTarget,
} from '../goal-run-api';

const mockFetch = apiClient.fetch as jest.Mock;

const errorResponse = (status: number, body: unknown) => ({
  ok: false,
  status,
  json: jest.fn().mockResolvedValue(body),
});

const TARGET: UtilityTarget = {
  metric: 'steps_executed',
  direction: 'maximize',
  source: 'goal_run',
};

const REFUSAL = {
  error: {
    code: 'AUTHORITY_REQUIRED',
    message: 'Only a supervisor may set a utility target.',
  },
  field: 'utility_target',
  verification: { status: 'refused' },
};

describe('goal-run-api shared error reader', () => {
  it.each([
    ['production top-level', REFUSAL],
    ['bare-FastAPI nested', { detail: REFUSAL }],
  ])('surfaces the same refusal for the %s wire shape', async (_label, body) => {
    mockFetch.mockResolvedValue(errorResponse(403, body));

    const error = await setGoalUtility('goal-1', TARGET).catch((err) => err);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(error.message).toBe(REFUSAL.error.message);
    expect(error.status).toBe(403);
  });

  it('reads the nested bare-FastAPI shape through another exported caller', async () => {
    mockFetch.mockResolvedValue(errorResponse(409, { detail: REFUSAL }));

    const error = await clearGoalUtility('goal-1').catch((err) => err);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(error.message).toBe(REFUSAL.error.message);
    expect(error.status).toBe(409);
  });

  it.each([
    ['detail string', { detail: 'Goal not found' }, 'Goal not found'],
    [
      'detail.error string',
      { detail: { error: 'decision_review_required' } },
      'decision_review_required',
    ],
    [
      'detail.message string',
      { detail: { message: 'Refresh the run and review the pending decision.' } },
      'Refresh the run and review the pending decision.',
    ],
    ['top-level message', { message: 'Request refused by policy.' }, 'Request refused by policy.'],
  ])('keeps the existing %s form', async (_label, body, expected) => {
    mockFetch.mockResolvedValue(errorResponse(400, body));

    await expect(createGoal({ title: 'Test goal' })).rejects.toThrow(expected);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['null body', 500, null],
    ['array body', 500, []],
    [
      'object-valued message',
      409,
      { detail: { error: { code: 'STALE_TARGET', message: { en: 'not a string' } } } },
    ],
    [
      'object-valued top-level message',
      503,
      { error: { code: 'GOAL_RUN_EFFECT_UNKNOWN', message: 42 } },
    ],
    ['malformed detail envelope', 422, { detail: { error: ['not', 'a', 'message'] } }],
  ])('falls back without dumping JSON for %s', async (_label, status, body) => {
    mockFetch.mockResolvedValue(errorResponse(status, body));

    const error = await createGoal({ title: 'Test goal' }).catch((err) => err);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(error.message).toBe(`Failed to create goal (${status})`);
    expect(error.message).not.toContain('{');
  });

  it('falls back when the error body is not JSON', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: jest.fn().mockRejectedValue(new SyntaxError('Unexpected token <')),
    });

    await expect(createGoal({ title: 'Test goal' })).rejects.toThrow(
      'Failed to create goal (500)',
    );
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});
