/**
 * Trust API client tests (lib/trust-api.ts)
 *
 * Mocks apiClient.fetch and asserts URL/method contract for the
 * /api/v1/trust-calibration/* admin surface (P0–P3).
 */

const mockFetch = jest.fn();

jest.mock('../../api-client', () => ({
  __esModule: true,
  apiClient: {
    fetch: (...args: unknown[]) => mockFetch(...args),
  },
}));

import {
  assessAction,
  getTrustStats,
  getAutomation,
  setAutomation,
  runCertificationNow,
} from '../../trust-api';

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body };
}

beforeEach(() => mockFetch.mockReset());

describe('trust-api assess + stats', () => {
  test('assessAction builds query and returns assessment', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        action_type: 'send_email',
        p_approve: 0.42,
        uncertainty: 0.05,
        recommendation: 'ask',
        n_obs: 40,
        sources: { hitl: 30, proposal: 10 },
        thresholds: { tau_low: 0.35, tau_uncertain: 0.15 },
        min_observations: 10,
      })
    );

    const out = await assessAction({
      actionType: 'send_email',
      platform: 'gmail',
      agentId: 'ag-1',
    });

    expect(out.recommendation).toBe('ask');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/v1/trust-calibration/assess');
    expect(url).toContain('action_type=send_email');
    expect(url).toContain('platform=gmail');
    expect(url).toContain('agent_id=ag-1');
  });

  test('getTrustStats unwraps calibration block', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        enabled: true,
        shadow_only: true,
        observations: { total: 18, by_source: { hitl: 12 }, approved: 12, rejected: 6 },
        calibration: { assessments_total: 18, resolved: 10, pending: 8, brier: 0.02, ece_10bin: 0.04, recommendation_outcome_matrix: {} },
        kernel: { half_life_days: 30, max_obs: 400 },
        thresholds: { tau_low: 0.35, tau_uncertain: 0.15, min_observations: 10 },
      })
    );

    const out = await getTrustStats();
    expect(out.calibration.brier).toBe(0.02);
    expect(mockFetch.mock.calls[0][0]).toBe('/api/v1/trust-calibration/stats');
  });
});

describe('trust-api automation', () => {
  test('setAutomation posts query params', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ mode: 'auto', interval_min: 60 }));

    const out = await setAutomation({ mode: 'auto', intervalMin: 60 });

    expect(out.mode).toBe('auto');
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/v1/trust-calibration/automation');
    expect(url).toContain('mode=auto');
    expect(url).toContain('interval_min=60');
    expect((init as RequestInit).method).toBe('POST');
  });

  test('runCertificationNow posts to run-now', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ ran: true }));
    const out = await runCertificationNow();
    expect(out).toEqual({ ran: true });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain('/run-now');
    expect((init as RequestInit).method).toBe('POST');
  });

  test('errors surface with status', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}, false, 503));
    await expect(getTrustStats()).rejects.toThrow('503');
  });
});
