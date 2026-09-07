/**
 * AutonomyPanel tests (canvas right-panel Autonomy tab)
 *
 * The panel is the tenant's per-topic autonomy control surface. This covers
 * the three-mode contract (human_always / auto_if_mature /
 * auto_until_corrected — the 2026-09-04 third choice) and that the live
 * gate, including the correction-cycle line, is rendered.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockApi = {
  get: jest.fn(),
  put: jest.fn(),
};

jest.mock('@/lib/api-client', () => ({
  apiClient: mockApi,
}));

import { AutonomyPanel } from '../AutonomyPanel';

const TOPICS = [
  {
    topic: 'send_email',
    label: 'Send email',
    description: 'Sending emails on your behalf (external, irreversible)',
    default_mode: 'human_always',
    mode: 'human_always',
    canvas_relevant: true,
    gate: {
      outcome: 'propose',
      reason: 'You asked to approve every send email — the hire proposes only.',
      maturity: { known: true, maturity_level: 'supervised', required: 'supervised', ok: true },
      trust: { enabled: false, trust: null, threshold: 0.6, cold_start: null, ok: true },
      cycle: null,
    },
  },
  {
    topic: 'canvas_edit',
    label: 'Canvas edits',
    description: 'Editing drafts and documents on canvases',
    default_mode: 'auto_if_mature',
    mode: 'auto_until_corrected',
    canvas_relevant: false,
    gate: {
      outcome: 'propose',
      reason: 'A human correction reset the canvas edits autonomy cycle — re-earned capability tier student so far, needs intern again (verified work re-graduates it).',
      maturity: { known: true, maturity_level: 'supervised', required: 'intern', ok: true },
      trust: { enabled: false, trust: null, threshold: 0.6, cold_start: null, ok: true },
      cycle: { reset: true, tier: 'student', required: 'intern', ok: false, reason: null },
    },
  },
];

beforeEach(() => {
  jest.resetAllMocks();
  mockApi.get.mockResolvedValue({ data: { topics: TOPICS } });
  mockApi.put.mockResolvedValue({});
});

describe('AutonomyPanel', () => {
  test('renders the three tenant-selectable modes per topic', async () => {
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-send_email'));
    expect(screen.getByTestId('autonomy-send_email-hitl')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-send_email-auto')).toBeInTheDocument();
    expect(screen.getByTestId('autonomy-send_email-cycle')).toBeInTheDocument();
  });

  test('selecting auto-until-corrected PUTs the new mode and refreshes', async () => {
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByTestId('autonomy-send_email-cycle'));
    fireEvent.click(screen.getByTestId('autonomy-send_email-cycle'));

    await waitFor(() =>
      expect(mockApi.put).toHaveBeenCalledWith('/api/autonomy/topics/send_email', {
        mode: 'auto_until_corrected',
      })
    );
    // Silent gate refresh after the mode change.
    await waitFor(() => expect(mockApi.get).toHaveBeenCalledTimes(2));
  });

  test('a reset cycle is visible in the gate detail', async () => {
    render(<AutonomyPanel canvasId="c-1" agentId="hire-1" />);

    await waitFor(() => screen.getByText(/cycle student/i));
    expect(screen.getByText(/reset by a correction/i)).toBeInTheDocument();
  });
});
